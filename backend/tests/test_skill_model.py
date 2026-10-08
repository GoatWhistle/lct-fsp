"""Модель навыка — чистая функция (docs/mechanics.md, §3–4): юнит-тесты и проверки свойств."""

import itertools
import math
import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter import irt
from app.adapter.irt import estimate
from app.domain.skill import LevelBand, Normal, Observation, Prior, SkillProfileLevels, level_band
from app.usecase.interface import SkillModel

TOPICS = ("sql", "api", "algorithms", "testing")
THRESHOLDS = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}
CONFIDENCE = 0.8


def prior(mean: float = 0.0) -> Prior:
    return Prior.equal_weights(TOPICS, theta_sd=1.0, deviation_sd=0.6, mean=mean)


def item(topic: str, correct: bool, difficulty: float = 0.0, weight: float = 1.0) -> Observation:
    return Observation(
        topic=topic, correct=correct, discrimination=1.2, difficulty=difficulty, weight=weight
    )


def random_items(rng: random.Random, n: int) -> list[Observation]:
    return [
        item(rng.choice(TOPICS), rng.random() < 0.5, difficulty=rng.uniform(-1.0, 2.0))
        for _ in range(n)
    ]


def test_without_observations_estimate_is_the_prior() -> None:
    result = estimate(prior(), [])

    for topic in TOPICS:
        assert result.topic(topic).mean == 0.0
        assert result.topic(topic).sd == pytest.approx(math.sqrt(1.0 + 0.36))
    # θ̄ = θ_s + Σ w_t δ_t: дисперсия s_θ² + s_δ² Σ w_t²
    assert result.overall().sd == pytest.approx(math.sqrt(1.0 + 0.36 * 4 * 0.25**2))


def test_more_correct_answers_give_higher_level() -> None:
    items = [("sql", 0.0), ("api", 0.5), ("algorithms", 1.0), ("testing", 0.0)] * 3
    overall = []
    for correct_count in range(len(items) + 1):
        observations = [
            item(topic, i < correct_count, difficulty)
            for i, (topic, difficulty) in enumerate(items)
        ]
        overall.append(estimate(prior(), observations).overall().mean)

    assert overall == sorted(overall)
    assert len(set(overall)) == len(overall)


def test_flipping_any_answer_to_correct_raises_level() -> None:
    rng = random.Random(4)
    for _ in range(200):
        observations = random_items(rng, rng.randint(1, 20))
        wrong = [i for i, obs in enumerate(observations) if not obs.correct]
        if not wrong:
            continue
        i = rng.choice(wrong)
        flipped = list(observations)
        flipped[i] = item(observations[i].topic, True, observations[i].difficulty)

        before, after = estimate(prior(), observations), estimate(prior(), flipped)

        assert after.overall().mean > before.overall().mean
        assert after.topic(observations[i].topic).mean > before.topic(observations[i].topic).mean


def test_more_items_give_smaller_uncertainty() -> None:
    rng = random.Random(7)
    for _ in range(50):
        observations = random_items(rng, 25)
        sds = [estimate(prior(), observations[:n]).overall().sd for n in range(26)]
        assert all(later < earlier for earlier, later in itertools.pairwise(sds))


def test_topic_uncertainty_shrinks_most_where_items_were_asked() -> None:
    result = estimate(prior(), [item("sql", True), item("sql", False)] * 3)

    assert result.topic("sql").sd < result.topic("api").sd < estimate(prior(), []).topic("api").sd


def test_topics_borrow_strength_through_common_part() -> None:
    """Ответы по SQL кое-что говорят и о других темах: общая часть уровня θ_s."""
    result = estimate(prior(), [item("sql", True, difficulty=1.0)] * 4)

    assert result.topic("sql").mean > result.topic("api").mean > 0.0


def test_overall_level_is_weighted_mean_of_topic_levels() -> None:
    rng = random.Random(11)
    result = estimate(prior(), random_items(rng, 15))

    mean_of_topics = sum(result.topic(t).mean for t in TOPICS) / len(TOPICS)
    assert result.overall().mean == pytest.approx(mean_of_topics)


def test_weight_scales_information() -> None:
    observations = [item("sql", True), item("api", False)] * 4
    lighter = [item(o.topic, o.correct, weight=0.7) for o in observations]
    ignored = [item(o.topic, o.correct, weight=0.0) for o in observations]

    full, partial, none = (estimate(prior(), obs) for obs in (observations, lighter, ignored))

    assert full.overall().sd < partial.overall().sd < none.overall().sd
    assert none.overall() == estimate(prior(), []).overall()


def test_estimate_is_deterministic_and_order_of_input_is_respected() -> None:
    rng = random.Random(3)
    observations = random_items(rng, 12)

    assert estimate(prior(), observations) == estimate(prior(), list(observations))


def test_prior_mean_shifts_estimate_but_not_uncertainty_without_data() -> None:
    shifted = estimate(prior(mean=0.5), [])

    assert shifted.overall().mean == pytest.approx(0.5)
    assert shifted.overall().sd == pytest.approx(estimate(prior(), []).overall().sd)


def test_inflation_scales_reported_uncertainty_and_keeps_level() -> None:
    """Поправка погрешности κ (§3): уровень по теме и общий уровень сообщаются с погрешностью
    κ σ модели, а среднее и шаг по наблюдениям — те же, что без поправки."""
    rng = random.Random(5)
    observations = random_items(rng, 12)

    plain = estimate(prior(), observations)
    inflated = estimate(replace(prior(), sd_inflation=1.15), observations)

    assert (inflated.mean, inflated.cov) == (plain.mean, plain.cov)
    for topic in TOPICS:
        assert inflated.topic(topic).mean == plain.topic(topic).mean
        assert inflated.topic(topic).sd == pytest.approx(1.15 * plain.topic(topic).sd)
    assert inflated.overall().mean == plain.overall().mean
    assert inflated.overall().sd == pytest.approx(1.15 * plain.overall().sd)


def test_probability_at_least_threshold_is_normal_tail() -> None:
    overall = Normal(mean=1.0, sd=0.4)

    assert overall.prob_at_least(THRESHOLDS["middle"]) == pytest.approx(0.8943502)
    assert Normal(0.5, 0.3).prob_at_least(0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("level", "band"),
    [
        (Normal(1.0, 0.1), LevelBand("middle", "middle")),
        (Normal(0.45, 0.3), LevelBand("junior", "middle")),
        (Normal(0.55, 0.3), LevelBand("junior", "middle")),
        (Normal(1.45, 0.3), LevelBand("middle", "senior")),
        (Normal(3.0, 0.3), LevelBand("senior", "senior")),
        (Normal(-3.0, 0.3), LevelBand(None, None)),
        (Normal(-1.5, 0.3), LevelBand(None, "intern")),
    ],
)
def test_level_band_words(level: Normal, band: LevelBand) -> None:
    assert level_band(level, THRESHOLDS, CONFIDENCE) == band


def test_level_band_is_confident_only_with_confidence_threshold() -> None:
    # π_middle = Φ(0.5/σ) − Φ(−0.5/σ): при σ = 0.39 — около 0.8
    assert level_band(Normal(1.0, 0.38), THRESHOLDS, CONFIDENCE).confident
    assert not level_band(Normal(1.0, 0.40), THRESHOLDS, CONFIDENCE).confident


def test_irt_module_is_the_skill_model_port() -> None:
    # Модуль на чистых функциях подставляется за порт как есть; соответствие проверяет и mypy.
    model: SkillModel = irt
    observations = [item("sql", True), item("api", False)]

    assert model.initial(prior()) == irt.initial(prior())
    assert model.estimate(prior(), observations) == estimate(prior(), observations)
    assert model.estimate(prior(), observations).topic("sql").mean > 0
    saved = SkillProfileLevels(Normal(0, 1), {"sql": Normal(0, 1)}, 1, None)
    assert model.advance(prior(), saved, datetime(2026, 1, 1, tzinfo=UTC)) == saved


# Свежесть (§11): шум Q Δt по общей части уровня между наблюдениями и доворот до «сейчас».

T0 = datetime(2026, 1, 1, tzinfo=UTC)
YEAR = timedelta(days=365.25)


def decaying(sd_per_year: float = 0.4, inflation: float = 1.0) -> Prior:
    return replace(prior(), decay_sd_per_year=sd_per_year, sd_inflation=inflation)


def at(observation: Observation, moment: datetime) -> Observation:
    return replace(observation, at=moment)


def test_without_decay_time_between_observations_changes_nothing() -> None:
    timed = [at(item("sql", True), T0), at(item("api", False), T0 + 3 * YEAR)]

    assert estimate(prior(), timed) == estimate(prior(), [item("sql", True), item("api", False)])


def test_gap_between_observations_widens_uncertainty_by_decay_variance() -> None:
    """Год без сигналов прибавляет к дисперсии уровня каждой темы и общего уровня sd_год²."""
    first = [at(item(t, True), T0) for t in TOPICS for _ in range(3)]
    before = estimate(decaying(0.4, inflation=1.2), first)
    after = irt.diffuse(before, decaying(0.4, inflation=1.2), YEAR)

    for topic in TOPICS:
        assert after.topic(topic).mean == before.topic(topic).mean
        assert after.topic(topic).sd ** 2 == pytest.approx(before.topic(topic).sd ** 2 + 0.16)
    assert after.overall().sd ** 2 == pytest.approx(before.overall().sd ** 2 + 0.16)


def test_decay_is_applied_between_timed_observations_in_estimate() -> None:
    early = [at(item("sql", True), T0)] * 4
    late = at(item("api", True), T0 + 2 * YEAR)
    same_day = at(item("api", True), T0)

    spread = estimate(decaying(), [*early, late])
    together = estimate(decaying(), [*early, same_day])

    assert spread.topic("sql").sd > together.topic("sql").sd


def test_decay_never_exceeds_prior_uncertainty() -> None:
    observed = estimate(decaying(), [at(item("sql", True), T0)] * 6)
    initial = estimate(decaying(), [])

    far = irt.diffuse(observed, decaying(), 100 * YEAR)

    for topic in TOPICS:
        assert far.topic(topic).sd <= initial.topic(topic).sd + 1e-12
    assert far.overall().sd <= initial.overall().sd + 1e-12
    assert far.topic("sql").sd > observed.topic("sql").sd


def test_advance_of_saved_profile_equals_estimate_diffused_to_now() -> None:
    """Сохранённый профиль — на момент последнего сигнала; доворот по его уровням до «сейчас» даёт
    то же, что оценка с затуханием до «сейчас»."""
    model = decaying(0.4, inflation=1.15)
    rng = random.Random(9)
    observations = [at(o, T0 + timedelta(days=10 * i)) for i, o in enumerate(random_items(rng, 12))]
    last = observations[-1].at
    assert last is not None
    result = estimate(model, observations)
    saved = SkillProfileLevels(
        overall=result.overall(),
        topics={t: result.topic(t) for t in TOPICS},
        observations=len(observations),
        last_signal_at=last,
    )

    for gap in (timedelta(0), YEAR / 2, 3 * YEAR, 50 * YEAR):
        advanced = irt.advance(model, saved, last + gap)
        diffused = irt.diffuse(result, model, gap)
        assert advanced.overall.mean == saved.overall.mean
        assert advanced.overall.sd == pytest.approx(diffused.overall().sd)
        for topic in TOPICS:
            assert advanced.topics[topic].sd == pytest.approx(diffused.topic(topic).sd)
        assert (advanced.observations, advanced.last_signal_at) == (12, last)


def test_advance_without_signals_or_decay_keeps_profile() -> None:
    result = estimate(decaying(), [])
    empty = SkillProfileLevels(result.overall(), {t: result.topic(t) for t in TOPICS}, 0, None)
    saved = replace(empty, observations=1, last_signal_at=T0)

    assert irt.advance(decaying(), empty, T0 + YEAR) == empty
    assert irt.advance(prior(), saved, T0 + YEAR) == saved
    # Часы позади сигнала — затухания нет, а не «отрицательное».
    assert irt.advance(decaying(), saved, T0 - YEAR) == saved


def test_decaying_estimate_needs_moments_of_observations() -> None:
    with pytest.raises(ValueError, match="момент"):
        estimate(decaying(), [at(item("sql", True), T0), item("api", True)])


def strong(topic: str, correct: bool, difficulty: float) -> Observation:
    """Наблюдение с большой разделяющей силой — как достижение ФСП."""
    return Observation(topic=topic, correct=correct, discrimination=2.0, difficulty=difficulty)


@pytest.mark.parametrize(("correct", "difficulty"), [(True, 1.0), (False, -0.5), (True, -2.0)])
def test_to_mode_lands_on_the_posterior_mode(correct: bool, difficulty: float) -> None:
    """В моде градиент лог-апостериорного — ноль: μ' − μ = w a (u − p(hᵀμ')) Σh (§3)."""
    obs = strong("sql", correct, difficulty)
    start = irt.initial(prior())

    result = irt.update(start, obs, to_mode=True)

    sigma_h = [row[0] + row[1] for row in start.cov]
    p = irt.sigmoid(obs.discrimination * (result.mean[0] + result.mean[1] - obs.difficulty))
    gradient = obs.discrimination * (float(obs.correct) - p)
    for m, m0, s in zip(result.mean, start.mean, sigma_h, strict=True):
        assert m - m0 == pytest.approx(gradient * s, abs=1e-9)


def test_one_step_falls_short_of_the_mode_on_a_strong_observation() -> None:
    """Один шаг из априорного недолетает до моды: поэтому профиль навыков итерирует (§3)."""
    obs = strong("sql", True, 1.0)

    one_step = estimate(prior(), [obs]).topic("sql").mean
    mode = estimate(prior(), [obs], to_mode=True).topic("sql").mean

    assert one_step != pytest.approx(mode, abs=1e-3)
    assert estimate(prior(), [obs], to_mode=True).topic("sql").sd < prior_sd("sql")


def prior_sd(topic: str) -> float:
    return irt.initial(prior()).topic(topic).sd


def test_strong_result_below_the_level_barely_moves_it() -> None:
    """Одностороннее свидетельство (§11): решённое задание ниже уровня почти не сдвигает его."""
    high = prior(mean=2.0)

    moved = estimate(high, [strong("sql", True, 0.0)], to_mode=True).topic("sql").mean

    assert 2.0 <= moved < 2.05
