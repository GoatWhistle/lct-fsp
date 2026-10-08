"""Обратная связь кандидату в домене (mechanics.md, §15): порог k по компаниям, агрегаты,
подсказки «что поднимет выше» той же функцией скора, что и подборка, и действия."""

import dataclasses
import math
import random
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter import irt
from app.domain.catalog import CatalogRef
from app.domain.feedback import (
    RAISE_STEP,
    ActionKind,
    CandidateSelection,
    Feedback,
    FeedbackRules,
    Scenario,
    feedback,
    latest_per_need,
)
from app.domain.importance import TopicImportance
from app.domain.match import Requirement, match_score
from app.domain.selection import NeedRequirement, NeedSnapshot, SelectionBlock
from app.domain.skill import Normal, Observation, Prior
from app.domain.work import WorkFormat

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TOPICS = (
    CatalogRef("qa.theory", "Теория тестирования"),
    CatalogRef("qa.api", "API"),
    CatalogRef("qa.databases", "Базы данных"),
)
CODES = tuple(t.code for t in TOPICS)
RULES = FeedbackRules(
    min_companies=3,
    period_days=30,
    hints_max=3,
    min_gain=0.01,
    missing_level=Normal(0.0, 1.0),
)
MIDDLE = 0.5
STACK_CAP = 0.1


def snapshot(
    weights: Sequence[float] = (0.5, 0.3, 0.2),
    *,
    requirement: float = MIDDLE,
    stack: Sequence[str] = ("pytest", "postgresql"),
    specialization: str = "qa",
) -> NeedSnapshot:
    return NeedSnapshot(
        title="Потребность",
        specialization=CatalogRef(specialization, specialization),
        grade=CatalogRef("middle", "Middle"),
        stack=tuple(CatalogRef(code, code) for code in stack),
        work_format=WorkFormat.remote,
        city=None,
        salary=None,
        topics=tuple(
            NeedRequirement(topic, TopicImportance.important, False, weight, requirement)
            for topic, weight in zip(TOPICS, weights, strict=True)
        ),
        updated_at=T0,
    )


def selection(
    *,
    owner: uuid.UUID | None = None,
    need_id: uuid.UUID | None = None,
    need: NeedSnapshot | None = None,
    position: int = 1,
    block: SelectionBlock = SelectionBlock.exact,
    neighbors: Sequence[float] = (),
    created_at: datetime = T0,
) -> CandidateSelection:
    return CandidateSelection(
        selection_id=uuid.uuid4(),
        owner=owner or uuid.uuid4(),
        need_id=need_id,
        need=need or snapshot(),
        stack_cap=STACK_CAP,
        created_at=created_at,
        position=position,
        block=block,
        neighbors=tuple(neighbors),
    )


def levels(*pairs: tuple[float, float]) -> dict[str, Normal]:
    return {code: Normal(mean, sd) for code, (mean, sd) in zip(CODES, pairs, strict=True)}


LEVELS = levels((0.4, 0.5), (0.9, 0.3), (0.1, 0.9))


@dataclasses.dataclass
class Narrower:
    """Прогноз сужения в тестах: та же μ, погрешность × `factor`; запоминает, что спрашивали."""

    current: dict[str, Normal]
    factor: float
    asked: list[str] = dataclasses.field(default_factory=list)

    def __call__(self, topic: str) -> Normal | None:
        self.asked.append(topic)
        level = self.current[topic]
        return Normal(level.mean, level.sd * self.factor)


def run(
    selections: Sequence[CandidateSelection],
    *,
    current: dict[str, Normal] | None = None,
    narrowed: Narrower | None = None,
    task_topics: frozenset[str] = frozenset(),
    fsp_linked: bool = True,
    categorized: bool = True,
    candidate_stack: frozenset[str] = frozenset({"pytest"}),
    rules: FeedbackRules = RULES,
) -> Feedback:
    current = current or LEVELS
    return feedback(
        selections,
        specialization="qa" if categorized else None,
        topics=TOPICS if categorized else (),
        levels=current if categorized else {},
        candidate_stack=candidate_stack,
        narrowed=narrowed or Narrower(current, 0.5),
        task_topics=task_topics,
        fsp_linked=fsp_linked,
        rules=rules,
    )


def score(need: NeedSnapshot, current: dict[str, Normal], stack: frozenset[str]) -> float:
    reqs = [Requirement(t.topic.code, t.weight, t.requirement) for t in need.topics]
    return match_score(
        reqs, current, [t.code for t in need.stack], stack, stack_cap=STACK_CAP
    ).score


# Порог k по компаниям.


def test_below_k_companies_shows_neither_placement_nor_need_hints_but_general_hint() -> None:
    selections = [selection() for _ in range(RULES.min_companies - 1)]

    result = run(selections)

    assert result.period_days == RULES.period_days
    assert not result.enough
    assert result.placement is None
    assert [(h.topic, h.scenario, h.gain) for h in result.hints] == [
        # Наибольшая погрешность — у баз данных.
        (TOPICS[2], None, None)
    ]
    assert result.hints[0].action.kind is ActionKind.topic_block


def test_exactly_k_companies_shows_placement_and_need_hints() -> None:
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(selections)

    assert result.enough
    assert result.placement is not None
    assert result.hints and all(h.gain is not None for h in result.hints)


def test_five_selections_of_one_company_do_not_reach_k() -> None:
    company = uuid.uuid4()
    selections = [selection(owner=company, need_id=uuid.uuid4()) for _ in range(5)]

    result = run(selections, rules=dataclasses.replace(RULES, min_companies=2))

    assert not result.enough
    assert result.placement is None


def test_without_selections_feedback_is_few_with_general_hint() -> None:
    result = run([])

    assert not result.enough
    assert [h.topic for h in result.hints] == [TOPICS[2]]


def test_without_category_there_are_no_topic_hints() -> None:
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(selections, categorized=False, fsp_linked=False)

    assert not result.enough
    assert result.placement is None
    assert [h.action.kind for h in result.hints] == [ActionKind.link_fsp]


# Агрегаты.


def test_placement_matches_manual_median_and_exact_share() -> None:
    rows = [
        (3, SelectionBlock.exact),
        (1, SelectionBlock.exact),
        (7, SelectionBlock.nearby),
        (2, SelectionBlock.exact),
    ]
    selections = [selection(position=p, block=b) for p, b in rows]

    result = run(selections)

    assert result.placement is not None
    assert result.placement.selections == 4
    # Места 1, 2, 3, 7 — медиана посередине между 2 и 3.
    assert result.placement.median_position == 2.5
    assert result.placement.exact_share == 0.75


# Подсказки.


def test_gain_is_match_score_difference_on_changed_level_averaged_over_needs() -> None:
    needs = [snapshot((0.5, 0.3, 0.2)), snapshot((0.2, 0.2, 0.6)), snapshot((0.6, 0.4, 0.0))]
    selections = [selection(need=n, need_id=uuid.uuid4()) for n in needs]
    stack = frozenset({"pytest"})

    result = run(selections, candidate_stack=stack)

    assert result.hints
    for hint in result.hints:
        assert hint.topic is not None and hint.gain is not None
        code = hint.topic.code
        level = LEVELS[code]
        changed = (
            Normal(level.mean + RAISE_STEP, level.sd)
            if hint.scenario is Scenario.raise_
            else Normal(level.mean, level.sd * 0.5)
        )
        deltas = [
            score(n, LEVELS | {code: changed}, stack) - score(n, LEVELS, stack) for n in needs
        ]
        assert hint.gain == pytest.approx(sum(deltas) / len(deltas), abs=1e-12)


def test_hints_are_ordered_by_gain_and_capped() -> None:
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(selections, rules=dataclasses.replace(RULES, hints_max=2, min_gain=0.0))

    gains = [h.gain for h in result.hints]
    assert len(gains) == 2
    assert gains == sorted(gains, reverse=True)  # type: ignore[type-var]


def test_topic_below_requirement_gets_raise_and_no_gain_is_negative() -> None:
    """Уровень ниже требования: сужение погрешности опускает P(θ ≥ req) — подсказка говорит о
    росте уровня, а не обещает его за блок."""
    current = levels((-0.5, 0.8), (-0.3, 0.9), (-0.8, 0.7))
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(selections, current=current, narrowed=Narrower(current, 0.3))

    assert result.hints
    assert {h.scenario for h in result.hints} == {Scenario.raise_}
    assert all(h.gain is not None and h.gain >= RULES.min_gain for h in result.hints)


def test_narrowing_wins_above_requirement() -> None:
    # Уровень выше требования и широкая погрешность: сужение даёт больше, чем полоса вверх.
    current = levels((1.3, 1.5), (0.9, 0.3), (0.5, 0.2))
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(selections, current=current, narrowed=Narrower(current, 0.1))

    first = result.hints[0]
    assert first.topic == TOPICS[0]
    assert first.scenario is Scenario.narrow


def test_topic_without_narrowing_forecast_gets_raise_only() -> None:
    selections = [selection() for _ in range(RULES.min_companies)]

    def no_forecast(topic: str) -> Normal | None:
        return None

    result = feedback(
        selections,
        specialization="qa",
        topics=TOPICS,
        levels=LEVELS,
        candidate_stack=frozenset(),
        narrowed=no_forecast,
        task_topics=frozenset(),
        fsp_linked=True,
        rules=RULES,
    )

    assert result.hints
    assert {h.scenario for h in result.hints} == {Scenario.raise_}


def test_each_need_counts_once_by_its_latest_snapshot() -> None:
    need_id = uuid.uuid4()
    old = selection(need_id=need_id, need=snapshot((0.0, 0.0, 1.0)), created_at=T0)
    new = selection(need_id=need_id, need=snapshot((1.0, 0.0, 0.0)), created_at=T0 + timedelta(1))
    lone = selection(need=snapshot((0.0, 1.0, 0.0)))
    other = selection(need=snapshot((0.0, 1.0, 0.0)))

    assert latest_per_need([old, new, lone, other]) == [new, lone, other]

    stack = frozenset({"pytest"})
    result = run(
        [old, new, lone, other], candidate_stack=stack, rules=dataclasses.replace(RULES, min_gain=0)
    )
    hint = next(h for h in result.hints if h.topic == TOPICS[0])
    level = LEVELS["qa.theory"]
    changed = (
        Normal(level.mean + RAISE_STEP, level.sd)
        if hint.scenario is Scenario.raise_
        else Normal(level.mean, level.sd * 0.5)
    )
    needs = [new.need, lone.need, other.need]
    deltas = [
        score(n, LEVELS | {"qa.theory": changed}, stack) - score(n, LEVELS, stack) for n in needs
    ]
    assert hint.gain == pytest.approx(sum(deltas) / 3)


def test_selections_of_other_specialization_do_not_count_towards_k() -> None:
    """После смены категории подборки прежней специализации не в счёт: иначе подсказки по
    текущей могли бы опереться на одну компанию."""
    other = [selection(need=snapshot(specialization="backend")) for _ in range(RULES.min_companies)]
    own = selection()

    below = run([*other, own])
    at = run([*other, own, *(selection() for _ in range(RULES.min_companies - 1))])

    assert (below.enough, below.placement) == (False, None)
    assert at.enough
    assert at.placement is not None and at.placement.selections == RULES.min_companies


def test_places_are_counted_against_saved_neighbor_scores() -> None:
    need = snapshot((1.0, 0.0, 0.0))
    stack = frozenset({"pytest"})
    current = score(need, LEVELS, stack)
    raised = score(need, LEVELS | {"qa.theory": Normal(LEVELS["qa.theory"].mean + 1, 0.5)}, stack)
    # Двое между текущим и новым скором, один выше нового, один ниже текущего.
    neighbors = [current + (raised - current) / 3, current + 2 * (raised - current) / 3]
    neighbors += [raised + 0.01, current - 0.01]
    selections = [selection(need=need, neighbors=neighbors) for _ in range(RULES.min_companies)]

    def no_forecast(topic: str) -> Normal | None:
        return None

    result = feedback(
        selections,
        specialization="qa",
        topics=TOPICS,
        levels=LEVELS,
        candidate_stack=stack,
        narrowed=no_forecast,
        task_topics=frozenset(),
        fsp_linked=True,
        rules=RULES,
    )

    hint = next(h for h in result.hints if h.topic == TOPICS[0])
    assert hint.places == 2


def test_narrowing_forecast_is_asked_once_per_topic() -> None:
    selections = [selection(need_id=uuid.uuid4()) for _ in range(RULES.min_companies)]
    narrower = Narrower(LEVELS, 0.5)

    run(selections, narrowed=narrower)

    assert sorted(narrower.asked) == sorted(CODES)


# Действия.


def test_regular_task_action_when_task_on_topic_else_unavailable_topic_block() -> None:
    selections = [selection() for _ in range(RULES.min_companies)]

    result = run(
        selections,
        task_topics=frozenset({"qa.theory"}),
        rules=dataclasses.replace(RULES, min_gain=0),
    )

    actions = {h.topic.code: h.action for h in result.hints if h.topic is not None}
    assert actions["qa.theory"].kind is ActionKind.regular_task
    assert actions["qa.theory"].available
    others = [a for code, a in actions.items() if code != "qa.theory"]
    assert others and all(a.kind is ActionKind.topic_block and not a.available for a in others)


@pytest.mark.parametrize("enough", [True, False])
def test_link_fsp_hint_only_without_fsp_and_without_gain(enough: bool) -> None:
    selections = [selection() for _ in range(RULES.min_companies if enough else 0)]

    linked = run(selections, fsp_linked=True)
    unlinked = run(selections, fsp_linked=False)

    assert ActionKind.link_fsp not in {h.action.kind for h in linked.hints}
    (fsp,) = [h for h in unlinked.hints if h.action.kind is ActionKind.link_fsp]
    assert (fsp.topic, fsp.gain, fsp.places, fsp.scenario) == (None, None, None, None)
    assert fsp.action.available


# Симуляция: выполнение топ-подсказки.


def block_answers(
    topic: str, theta: float, level: Normal, n: int, rng: random.Random, at: datetime
) -> list[Observation]:
    """Блок по теме: задания около текущего уровня, ответы — из истинного θ."""
    a = 1.2
    return [
        Observation(
            topic,
            rng.random() < 1 / (1 + math.exp(-a * (theta - level.mean))),
            a,
            level.mean,
            weight=0.7,
            at=at,
        )
        for _ in range(n)
    ]


def follow_top_hint(seed: int) -> tuple[float, float] | None:
    """Синтетический кандидат с истинным уровнем выше требования: подсказки по текущему профилю,
    затем блок по теме топ-подсказки с ответами из истинного θ через ту же модель навыка.
    Изменение среднего скора по потребностям и суммы мест; None — подсказок нет."""
    rng = random.Random(seed)
    prior = Prior.equal_weights(CODES, theta_sd=1.0, deviation_sd=0.5, sd_inflation=1.0)
    truth = {code: MIDDLE + rng.uniform(0.3, 1.5) for code in CODES}
    history = [
        o
        for _ in range(3)
        for code in CODES
        for o in block_answers(code, truth[code], Normal(MIDDLE, 1.0), 1, rng, T0)
    ]
    estimate = irt.estimate(prior, history, to_mode=True)
    current = {code: estimate.topic(code) for code in CODES}

    def narrowed(topic: str) -> Normal | None:
        level = current[topic]
        block = [
            Observation(topic, correct, 1.2, level.mean, weight=0.35, at=T0)
            for _ in range(6)
            for correct in (True, False)
        ]
        return Normal(
            level.mean, irt.estimate(prior, history + block, to_mode=True).topic(topic).sd
        )

    needs = [snapshot(tuple(w / sum(ws) for w in ws)) for ws in ((3, 2, 1), (1, 3, 2), (2, 1, 3))]
    stack = frozenset({"pytest"})
    neighbors = [rng.uniform(0.2, 0.9) for _ in range(10)]
    selections = [selection(need=n, need_id=uuid.uuid4(), neighbors=neighbors) for n in needs]
    result = feedback(
        selections,
        specialization="qa",
        topics=TOPICS,
        levels=current,
        candidate_stack=stack,
        narrowed=narrowed,
        task_topics=frozenset(),
        fsp_linked=True,
        rules=RULES,
    )
    top = next((h.topic for h in result.hints if h.topic is not None), None)
    if top is None:
        return None
    block = block_answers(top.code, truth[top.code], current[top.code], 6, rng, T0)
    after_estimate = irt.estimate(prior, history + block, to_mode=True)
    after = {code: after_estimate.topic(code) for code in CODES}

    before_scores = [score(n, current, stack) for n in needs]
    after_scores = [score(n, after, stack) for n in needs]
    places = sum(sum(v < s for v in neighbors) for s in after_scores) - sum(
        sum(v < s for v in neighbors) for s in before_scores
    )
    return (sum(after_scores) - sum(before_scores)) / len(needs), places


def test_following_top_hint_does_not_lower_mean_score_or_places() -> None:
    runs = [r for seed in range(200) if (r := follow_top_hint(seed)) is not None]

    assert len(runs) > 100
    assert sum(score for score, _ in runs) / len(runs) >= 0
    assert sum(places for _, places in runs) / len(runs) >= 0


def test_topic_without_weight_in_every_need_is_not_forecast() -> None:
    selections = [selection(need=snapshot((0.7, 0.3, 0.0))) for _ in range(RULES.min_companies)]
    narrower = Narrower(LEVELS, 0.5)

    result = run(selections, narrowed=narrower, rules=dataclasses.replace(RULES, min_gain=0))

    assert "qa.databases" not in narrower.asked
    assert TOPICS[2] not in [h.topic for h in result.hints]
