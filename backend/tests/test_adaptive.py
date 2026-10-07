"""Адаптивный тест — чистые функции выбора и остановки (mechanics.md, §6) и их поведение на
симулированных кандидатах."""

import itertools
import random
from dataclasses import replace
from datetime import UTC, datetime

from app.adapter.adaptive import choose, information
from app.config import Mechanics, Settings
from app.domain.adaptive import Blueprint, Exposure, Option, selection_prior, should_stop
from app.domain.skill import Normal, Observation, Prior
from app.skills.irt import Estimate, initial, update
from tests.simulation import Candidate, market, median

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
TOPICS = ("t.one", "t.two")
PRIOR = Prior.equal_weights(TOPICS, theta_sd=1.0, deviation_sd=0.6)
OPEN = Exposure(attempts=0, max_rate=1.0, top_k=1)


BLUEPRINT = Blueprint(
    topics=TOPICS,
    weights=(0.5, 0.5),
    min_items=4,
    max_items=10,
    min_per_topic=1,
    max_topic_share=0.6,
    stop_sd=0.35,
)


def option(
    code: str, difficulty: float, topic: str = "t.one", seen_at: datetime | None = None
) -> Option:
    return Option(code, topic, 1.2, difficulty, shown=0, seen_at=seen_at)


def pick(
    options: list[Option],
    *,
    counts: dict[str, int] | None = None,
    estimate: Estimate | None = None,
    exposure: Exposure = OPEN,
    seed: int = 0,
) -> tuple[str, bool]:
    choice = choose(
        BLUEPRINT,
        counts or {},
        estimate or initial(PRIOR),
        options,
        exposure,
        random.Random(seed),
    )
    assert choice is not None
    return choice.code, choice.capped


def test_information_peaks_where_difficulty_meets_level() -> None:
    assert information(1.2, 0.0, 0.0) > information(1.2, 1.0, 0.0) > information(1.2, 2.0, 0.0)
    assert information(2.0, 0.0, 0.0) > information(1.2, 0.0, 0.0)


def test_choice_is_random_among_top_k_most_informative() -> None:
    options = [option(f"f{b}", b) for b in (0.0, 0.3, -0.4, 1.0, 2.0, -2.0)]
    exposure = Exposure(attempts=0, max_rate=1.0, top_k=3)

    picked = {pick(options, exposure=exposure, seed=s)[0] for s in range(200)}

    assert picked == {"f0.0", "f0.3", "f-0.4"}


def test_family_over_exposure_cap_is_not_offered() -> None:
    # Окно из 9 попыток и текущая: потолок 0,5 допускает показ в 5 из 10.
    exposure = Exposure(attempts=9, max_rate=0.5, top_k=1)
    best = replace(option("best", 0.0), shown=5)
    next_best = replace(option("next", 0.5), shown=4)

    assert pick([best, next_best], exposure=exposure) == ("next", False)


def test_capped_topic_takes_least_shown_family() -> None:
    exposure = Exposure(attempts=9, max_rate=0.5, top_k=1)
    options = [replace(option("best", 0.0), shown=7), replace(option("worse", 1.0), shown=6)]

    assert pick(options, exposure=exposure) == ("worse", True)


def test_unseen_families_go_first_then_seen_longest_ago() -> None:
    long_ago, recently = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
    seen = option("seen", 0.0, seen_at=recently)
    unseen = option("unseen", 2.0)
    old = option("old", 2.0, seen_at=long_ago)

    assert pick([seen, unseen])[0] == "unseen"
    assert pick([seen, old])[0] == "old"


def test_topic_below_minimum_coverage_goes_first() -> None:
    options = [option("one", 0.0), option("two", 0.0, topic="t.two")]

    assert pick(options, counts={"t.one": 3})[0] == "two"


def test_topic_with_larger_error_contribution_goes_next() -> None:
    # По второй теме уже два ответа — её погрешность меньше.
    estimate = initial(PRIOR)
    for correct in (True, False):
        estimate = update(estimate, Observation("t.two", correct, 1.2, 0.0))
    options = [option("one", 0.0), option("two", 0.0, topic="t.two")]

    assert pick(options, counts={"t.one": 2, "t.two": 2}, estimate=estimate)[0] == "one"


def test_topic_at_share_cap_yields_to_others() -> None:
    estimate = initial(PRIOR)
    for _ in range(4):
        estimate = update(estimate, Observation("t.two", True, 1.2, 0.0))
    options = [option("one", 0.0), option("two", 0.0, topic="t.two")]

    # Тема с наибольшей погрешностью уже на потолке доли 0,6: седьмое задание из семи в ней —
    # 6 > 0,6 · 7.
    assert pick(options, counts={"t.one": 5, "t.two": 1}, estimate=estimate)[0] == "two"


def test_topic_without_families_yields_and_nothing_left_is_none() -> None:
    assert pick([option("two", 0.0, topic="t.two")])[0] == "two"
    assert choose(BLUEPRINT, {}, initial(PRIOR), [], OPEN, random.Random(0)) is None


def test_stop_needs_precision_coverage_and_minimum_length() -> None:
    precise, vague = Normal(0.0, 0.3), Normal(0.0, 0.5)

    assert should_stop(BLUEPRINT, {"t.one": 2, "t.two": 2}, precise)
    assert not should_stop(BLUEPRINT, {"t.one": 2, "t.two": 2}, vague)
    assert not should_stop(BLUEPRINT, {"t.one": 4}, precise)
    assert not should_stop(BLUEPRINT, {"t.one": 1, "t.two": 1}, precise)
    # Лимит заданий останавливает и без точности.
    assert should_stop(BLUEPRINT, {"t.one": 5, "t.two": 5}, vague)


def test_selection_prior_moves_only_the_mean() -> None:
    """Априорное для выбора заданий — общее со средним в пороге грейда: темы, их веса и
    поправка погрешности те же."""
    prior = replace(PRIOR, sd_inflation=1.15)

    assert selection_prior(prior, 0.5) == replace(prior, mean=0.5)


def test_candidates_with_same_answers_get_different_sets() -> None:
    m = market("qa", MECHANICS)
    m.calibrate = False
    same = Candidate({t: 0.5 for t in m.prior.topics}, "middle")

    sets = [frozenset(m.adaptive(same).shown) for _ in range(30)]

    assert len(set(sets)) == len(sets)
    overlap = [len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2)]
    assert sum(overlap) / len(overlap) < 0.5


def test_family_exposure_stays_under_cap() -> None:
    """Доля попыток окна, где показано семейство, не выше потолка. Сверх потолка семейство
    берётся только запасным выбором — когда под потолком в теме ничего не осталось (§6): в первых
    попытках, где окно почти пусто, и в редких длинных тестах, выбравших почти всю тему."""
    mechanics = MECHANICS.model_copy(update={"exposure_window_attempts": 40})
    m = market("qa", mechanics)
    m.calibrate = False
    cold_start = 5
    picks = fallbacks = 0

    for attempt in range(300):
        before = list(m.window)
        run = m.adaptive(m.candidate())
        if attempt < cold_start:
            continue
        window = [*before, set(run.shown)]
        for code in set(run.shown) - set(run.capped):
            shown = sum(code in a for a in window)
            assert shown <= mechanics.exposure_max_rate * len(window), (attempt, code)
        picks += len(run.shown)
        fallbacks += len(run.capped)

    assert fallbacks / picks < 0.01


def test_adaptive_reaches_target_precision_in_fewer_items_than_fixed_blueprint() -> None:
    """Банк с известными параметрами, без лимита заданий у обоих: медиана числа заданий до
    σ̄ ≤ `test_stop_sd` у адаптивного меньше, чем у общего фиксированного бланка с тем же
    покрытием тем (схема S2 плана валидации)."""
    m = market("backend", MECHANICS)
    m.calibrate = False
    for item in m.items.values():
        item.params = item.truth
    bank = len(m.items)
    m.blueprint = replace(m.blueprint, max_items=bank)
    adaptive, fixed = [], []

    for _ in range(150):
        c = m.candidate()
        adaptive.append(m.adaptive(c).items_to(MECHANICS.test_stop_sd) or bank + 1)
        fixed.append(m.fixed(c, bank, target=0.0).items_to(MECHANICS.test_stop_sd) or bank + 1)

    assert median(adaptive) < median(fixed)
