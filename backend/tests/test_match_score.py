"""Скор соответствия и порядок подборки — чистые функции (mechanics.md, §12): юнит-тесты и
проверки свойств — сумма вкладов, обнуление фактора, потолок самоописания, монотонность."""

import math
import random
import uuid

import pytest

from app.domain.skill import Normal
from app.matching.importance import TopicImportance
from app.matching.score import (
    Requirement,
    Verdict,
    match_score,
    ranking,
    requirements,
    verdict,
)

KEY, IMPORTANT, NICE = TopicImportance.key, TopicImportance.important, TopicImportance.nice
WEIGHTS = {"key": 3.0, "important": 2.0, "nice": 1.0}
BANDS = [0.2, 0.5, 0.8]
CAP = 0.1
MIDDLE = 0.5
TOPICS = ("databases", "api", "distributed", "security")
NEED_STACK = ("postgresql", "django", "kafka", "docker")
EXACT = 1e-9


def reqs(*importance: TopicImportance) -> list[Requirement]:
    return requirements(
        list(zip(TOPICS, importance or (KEY, IMPORTANT, NICE, NICE), strict=True)),
        requirement=MIDDLE,
        importance_weights=WEIGHTS,
    )


def levels(*means: float, sd: float = 0.4) -> dict[str, Normal]:
    return {topic: Normal(mean, sd) for topic, mean in zip(TOPICS, means, strict=True)}


def random_levels(rng: random.Random) -> dict[str, Normal]:
    return {t: Normal(rng.uniform(-2.5, 2.5), rng.uniform(0.2, 1.2)) for t in TOPICS}


def random_stack(rng: random.Random) -> set[str]:
    return {tech for tech in (*NEED_STACK, "react", "go") if rng.random() < 0.5}


def test_topic_weight_is_importance_weight_normalized_and_requirement_is_grade_threshold() -> None:
    result = reqs(KEY, IMPORTANT, NICE, NICE)

    assert [r.topic for r in result] == list(TOPICS)
    assert [r.weight for r in result] == pytest.approx([3 / 7, 2 / 7, 1 / 7, 1 / 7])
    assert {r.level for r in result} == {MIDDLE}


def test_score_is_weighted_probability_of_meeting_requirements_plus_capped_stack() -> None:
    need = reqs(KEY, IMPORTANT, NICE, NICE)
    candidate = levels(1.3, 0.5, -0.3, 0.9)

    result = match_score(
        need, candidate, NEED_STACK, {"postgresql", "kafka", "react"}, stack_cap=CAP
    )

    probabilities = [
        0.5 * (1 + math.erf((m - MIDDLE) / 0.4 / math.sqrt(2))) for m in (1.3, 0.5, -0.3, 0.9)
    ]
    expected = (1 - CAP) * sum(
        r.weight * p for r, p in zip(need, probabilities, strict=True)
    ) + CAP * (2 / 4)
    assert result.score == pytest.approx(expected, abs=EXACT)
    assert [t.probability for t in result.topics] == pytest.approx(probabilities)
    assert result.topics[1].probability == pytest.approx(0.5)
    assert result.stack.matched == ("kafka", "postgresql")
    assert result.stack.overlap == 0.5


def test_contributions_sum_to_score() -> None:
    rng = random.Random(7)
    for _ in range(1000):
        need = reqs(*(rng.choice([KEY, IMPORTANT, NICE]) for _ in TOPICS))
        result = match_score(need, random_levels(rng), NEED_STACK, random_stack(rng), stack_cap=CAP)

        total = sum(t.contribution for t in result.topics) + result.stack.contribution
        assert abs(total - result.score) <= EXACT


def test_zeroing_a_topic_lowers_score_by_exactly_its_contribution() -> None:
    rng = random.Random(11)
    for _ in range(200):
        need = reqs()
        candidate = random_levels(rng)
        stack = random_stack(rng)
        full = match_score(need, candidate, NEED_STACK, stack, stack_cap=CAP)

        for i, topic in enumerate(TOPICS):
            # Уровень −∞ — вероятность выполнить требование ровно 0.
            zeroed = candidate | {topic: Normal(-math.inf, candidate[topic].sd)}
            without = match_score(need, zeroed, NEED_STACK, stack, stack_cap=CAP)

            assert without.topics[i].probability == 0.0
            assert abs(full.score - without.score - full.topics[i].contribution) <= EXACT


def test_zeroing_the_stack_lowers_score_by_exactly_its_contribution() -> None:
    rng = random.Random(13)
    for _ in range(200):
        need = reqs()
        candidate = random_levels(rng)
        full = match_score(need, candidate, NEED_STACK, random_stack(rng), stack_cap=CAP)
        without = match_score(need, candidate, NEED_STACK, set(), stack_cap=CAP)

        assert without.stack.contribution == 0.0
        assert abs(full.score - without.score - full.stack.contribution) <= EXACT


def test_self_reported_stack_lifts_score_at_most_by_cap() -> None:
    rng = random.Random(17)
    for _ in range(500):
        need = reqs()
        candidate = random_levels(rng)
        honest = match_score(need, candidate, NEED_STACK, random_stack(rng), stack_cap=CAP)
        # Накрутчик дописал весь стек потребности и ещё сверху.
        padded = match_score(
            need, candidate, NEED_STACK, {*NEED_STACK, "react", "go"}, stack_cap=CAP
        )

        assert padded.stack.contribution == pytest.approx(CAP)
        assert padded.score - honest.score <= CAP + EXACT


def test_stack_alone_never_lifts_a_weak_candidate_over_cap() -> None:
    weak = match_score(reqs(), levels(-9, -9, -9, -9), NEED_STACK, NEED_STACK, stack_cap=CAP)

    assert weak.score == pytest.approx(CAP)


def test_need_without_stack_gives_no_stack_contribution() -> None:
    result = match_score(reqs(), levels(9, 9, 9, 9), (), {"postgresql"}, stack_cap=CAP)

    assert result.stack.overlap == 0.0
    assert result.stack.contribution == 0.0
    assert result.score == pytest.approx(1 - CAP)


def test_score_is_monotone_in_topic_level() -> None:
    rng = random.Random(19)
    for _ in range(10_000):
        need = reqs(*(rng.choice([KEY, IMPORTANT, NICE]) for _ in TOPICS))
        candidate = random_levels(rng)
        stack = random_stack(rng)
        topic = rng.choice(TOPICS)
        before = match_score(need, candidate, NEED_STACK, stack, stack_cap=CAP)
        raised = candidate | {
            topic: Normal(candidate[topic].mean + rng.uniform(0, 1), candidate[topic].sd)
        }
        after = match_score(need, raised, NEED_STACK, stack, stack_cap=CAP)

        assert after.score >= before.score


def test_raising_a_topic_level_never_moves_candidate_down_the_ranking() -> None:
    rng = random.Random(23)
    salt = 23
    need = reqs()
    for _ in range(100):
        pool = {uuid.uuid4(): (random_levels(rng), random_stack(rng)) for _ in range(30)}

        def place(pool: dict[uuid.UUID, tuple[dict[str, Normal], set[str]]], who: uuid.UUID) -> int:
            scores = {
                c: match_score(need, lv, NEED_STACK, st, stack_cap=CAP).score
                for c, (lv, st) in pool.items()
            }
            return ranking(scores, salt).index(who)

        who = rng.choice(list(pool))
        topic = rng.choice(TOPICS)
        candidate, stack = pool[who]
        raised = candidate | {topic: Normal(candidate[topic].mean + 0.5, candidate[topic].sd)}

        assert place(pool | {who: (raised, stack)}, who) <= place(pool, who)


def test_narrower_error_lifts_candidate_above_requirement_and_lowers_one_below() -> None:
    def probability(mean: float, sd: float) -> float:
        return (
            match_score(reqs(), levels(mean, 0, 0, 0, sd=sd), (), (), stack_cap=CAP)
            .topics[0]
            .probability
        )

    assert probability(1.0, 0.3) > probability(1.0, 0.8)
    assert probability(0.0, 0.3) < probability(0.0, 0.8)


def test_ties_break_by_hash_of_salt_and_candidate_not_by_input_order() -> None:
    candidates = [uuid.uuid4() for _ in range(20)]
    scores = dict.fromkeys(candidates, 0.5)

    order = ranking(scores, 7)

    assert ranking(dict(reversed(scores.items())), 7) == order
    # Другая соль — другой порядок ничьих: никто не стоит выше всегда (шанс совпасть — 1/20!).
    assert ranking(scores, 8) != order


def test_higher_score_ranks_first() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    assert ranking({a: 0.2, b: 0.9, c: 0.5}, 0) == [b, c, a]


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.95, Verdict.confidently_above),
        (0.8, Verdict.confidently_above),
        (0.79, Verdict.likely_above),
        (0.5, Verdict.likely_above),
        (0.49, Verdict.likely_below),
        (0.2, Verdict.likely_below),
        (0.19, Verdict.below),
        (0.0, Verdict.below),
    ],
)
def test_verdict_words_follow_confidence_bands(probability: float, expected: Verdict) -> None:
    assert verdict(probability, BANDS) == expected
