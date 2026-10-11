"""Рыночная симуляция приглашений (M6): бюджет недели, одно открытое приглашение компании
кандидату, срок ответа и воспроизводимость по сиду."""

import random
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence

from validation.invitation_market import (
    Answer,
    Opening,
    Ranked,
    budgets,
    gini,
    metrics,
    simulate,
)

EMPLOYERS = [uuid.UUID(int=i) for i in range(1, 4)]
CANDIDATES = [uuid.UUID(int=100 + i) for i in range(40)]
NEEDS = [(uuid.UUID(int=1000 + i), EMPLOYERS[i % 3]) for i in range(5)]


def ranked(opening: Opening, loads: Mapping[uuid.UUID, int]) -> Sequence[Ranked]:
    """Один и тот же порядок для всех: сверху — те же кандидаты, рынок перегревается."""
    return [Ranked(c, 1 - i / len(CANDIDATES)) for i, c in enumerate(CANDIDATES)]


def decide(opening: Opening, candidate: uuid.UUID, score: float, load: int) -> float:
    return max(0.05, 0.8 - 0.15 * load)


def run(seed: int = 1, strategy: str = "A"):  # type: ignore[no-untyped-def]
    openings = budgets(NEEDS, Counter(e for _, e in NEEDS), 6)
    return openings, simulate(
        strategy,
        openings,
        ranked,
        decide,
        weeks=8,
        ttl_days=7,
        response_mean_days=3,
        rng=random.Random(seed),
    )


def test_same_seed_gives_the_same_market() -> None:
    _, one = run(7)
    _, two = run(7)
    assert [(s.need, s.candidate, s.week, s.answer) for s in one.sent] == [
        (s.need, s.candidate, s.week, s.answer) for s in two.sent
    ]
    _, other = run(8)
    assert [s.answer for s in other.sent] != [s.answer for s in one.sent]


def test_weekly_budget_is_never_exceeded() -> None:
    openings, market = run()
    per_week = Counter((s.need, s.week) for s in market.sent)
    budget = {o.need: o.budget for o in openings}
    assert all(count <= budget[need] for (need, _), count in per_week.items())
    per_company = Counter((s.employer, s.week) for s in market.sent)
    assert max(per_company.values()) <= 6


def test_company_never_has_two_open_invitations_to_one_candidate() -> None:
    _, market = run()
    for s in market.sent:
        rivals = [
            o
            for o in market.sent
            if o is not s and o.employer == s.employer and o.candidate == s.candidate
        ]
        assert not any(o.open_at(s.sent_at, 7) for o in rivals)


def test_every_invitation_is_answered_or_expires() -> None:
    _, market = run()
    assert all(s.answer is not None for s in market.sent)
    assert {s.answer for s in market.sent} == set(Answer)
    assert all((s.answer == Answer.expired) == (s.answer_at is None) for s in market.sent)


def test_company_does_not_invite_who_already_accepted_it() -> None:
    _, market = run()
    for s in market.sent:
        earlier = [
            o
            for o in market.sent
            if o.employer == s.employer
            and o.candidate == s.candidate
            and o.answer == Answer.accepted
            and o.answer_at is not None
            and o.answer_at < s.sent_at
        ]
        assert not earlier


def test_gini_and_metrics() -> None:
    assert gini([1, 1, 1, 1]) == 0
    assert abs(gini([0, 0, 0, 4]) - 0.75) < 1e-9
    _, market = run()
    m = metrics(market.sent, CANDIDATES, lambda need, candidate: 0.5)
    assert m.sent == len(market.sent)
    assert 0 < m.accepted_share < 1
    assert m.true_match == 0.5
    assert 0 < m.gini < 1


def test_answer_load_includes_the_invitation_being_answered() -> None:
    loads: list[int] = []

    def record(opening: Opening, candidate: uuid.UUID, score: float, load: int) -> float:
        loads.append(load)
        return 0.5

    simulate(
        "A",
        [Opening(NEEDS[0][0], EMPLOYERS[0], 1)],
        ranked,
        record,
        weeks=1,
        ttl_days=7,
        response_mean_days=0.1,
        rng=random.Random(7),
    )
    assert loads == [1]


def test_more_needs_than_budget_cannot_overspend() -> None:
    openings = budgets(NEEDS, Counter(e for _, e in NEEDS), 1)
    assigned: Counter[uuid.UUID] = Counter()
    for opening in openings:
        assigned[opening.employer] += opening.budget
    assert all(value <= 1 for value in assigned.values())
