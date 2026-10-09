"""Инварианты подборки в домене (mechanics.md, §12–13, §17): порядок блоков, досягаемость,
взаимный скор и признаки модели принятия."""

import dataclasses
import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candidate import GradeStatusKind
from app.domain.catalog import CatalogRef, Grade
from app.domain.match import Match, StackFit
from app.domain.selection import (
    BLOCK_ORDER,
    AcceptanceFeatures,
    NeedSnapshot,
    PoolCandidate,
    Scored,
    SelectionBlock,
    SelectionRules,
    UnconfirmedCandidate,
    arrange,
    block_of,
    mutual_score,
    showcase,
)
from app.domain.skill import Normal
from app.domain.work import WorkFormat

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
RULES = SelectionRules(
    stack_cap=0.15,
    nearby_grade_distance=1,
    verdict_bands=(0.2, 0.5, 0.8),
    low_data_sd=0.8,
    stale_after=timedelta(days=180),
    missing_level=Normal(0.0, 1.0),
)


def test_acceptance_features_have_no_protected_attributes() -> None:
    """Пол, возраст и вуз не входят ни в одну модель (§17): в признаках принятия их нет по
    построению. Новый признак — правка этого списка, а не тихое расширение."""
    names = {f.name for f in dataclasses.fields(AcceptanceFeatures)}

    assert names == {
        "salary",
        "expected_salary",
        "work_formats",
        "city",
        "relocation",
        "need_work_format",
        "need_city",
        "grade",
        "match_score",
        "market_salary",
        "open_invitations",
        "industries",
        "company_industry",
    }
    protected = ("gender", "sex", "age", "birth", "university", "education", "photo", "name")
    assert not [n for n in names if any(p in n for p in protected)]


def test_exact_block_is_above_nearby_and_every_block_has_a_place() -> None:
    assert BLOCK_ORDER.index(SelectionBlock.exact) < BLOCK_ORDER.index(SelectionBlock.nearby)
    assert sorted(BLOCK_ORDER) == sorted(SelectionBlock)
    assert len(set(BLOCK_ORDER)) == len(BLOCK_ORDER)


@pytest.mark.parametrize(
    ("candidate_rank", "distance", "block"),
    [
        (3, 1, SelectionBlock.exact),
        (2, 1, SelectionBlock.nearby),
        (4, 1, SelectionBlock.nearby),
        (1, 1, None),
        (5, 2, SelectionBlock.nearby),
        (2, 0, None),
    ],
)
def test_reach_by_grade_rank(
    candidate_rank: int, distance: int, block: SelectionBlock | None
) -> None:
    assert block_of(3, candidate_rank, distance) is block


def test_mutual_score_without_acceptance_is_the_match() -> None:
    assert mutual_score(0.7, None) == 0.7
    assert mutual_score(0.7, 0.5) == pytest.approx(0.35)
    for wrong in (-0.1, 1.1, float("nan")):
        with pytest.raises(ValueError):
            mutual_score(0.7, wrong)


def scored(score: float, grade: Grade, block: SelectionBlock) -> Scored:
    candidate = PoolCandidate(
        candidate_id=uuid.uuid4(),
        specialization="qa",
        grade=grade,
        overall=Normal(0.0, 1.0),
        levels={},
        stack=frozenset(),
        last_signal_at=T0,
        expectations=None,
    )
    return Scored(candidate, block, Match(score, (), StackFit((), 0, 0.0, 0.0)))


def test_arrange_orders_blocks_then_mutual_score() -> None:
    middle, junior = Grade("middle", "Middle", 3), Grade("junior", "Junior", 2)
    items = [
        scored(0.9, junior, SelectionBlock.nearby),
        scored(0.5, middle, SelectionBlock.exact),
        scored(0.8, middle, SelectionBlock.exact),
    ]

    entries = arrange(items, [1.0, 0.9, 0.3], salt=1, now=T0, rules=RULES)

    # Внутри точных 0.5 × 0.9 = 0.45 выше 0.8 × 0.3 = 0.24; «близкий» ниже обоих.
    assert [e.candidate_id for e in entries] == [
        items[1].candidate.candidate_id,
        items[2].candidate.candidate_id,
        items[0].candidate.candidate_id,
    ]
    assert [(e.block, e.rank, e.position) for e in entries] == [
        (SelectionBlock.exact, 1, 1),
        (SelectionBlock.exact, 2, 2),
        (SelectionBlock.nearby, 1, 3),
    ]
    assert entries[2].grade == CatalogRef("junior", "Junior")
    assert [e.match_score for e in entries] == [0.5, 0.8, 0.9]


def test_arrange_wants_one_probability_per_candidate() -> None:
    item = scored(0.5, Grade("middle", "Middle", 3), SelectionBlock.exact)

    with pytest.raises(ValueError):
        arrange([item, item], [None], salt=1, now=T0, rules=RULES)


MIDDLE = Grade("middle", "Middle", 3)
JUNIOR = Grade("junior", "Junior", 2)
MAIN_BLOCKS = (SelectionBlock.exact, SelectionBlock.nearby)


def unconfirmed(stack: frozenset[str], claimed: Grade = MIDDLE) -> UnconfirmedCandidate:
    return UnconfirmedCandidate(uuid.uuid4(), "qa", claimed, stack)


def need_of(stack: tuple[str, ...]) -> NeedSnapshot:
    return NeedSnapshot(
        title="QA",
        specialization=CatalogRef("qa", "QA"),
        grade=CatalogRef(MIDDLE.code, MIDDLE.name),
        stack=tuple(CatalogRef(code, code) for code in stack),
        work_format=WorkFormat.remote,
        city=None,
        salary=None,
        topics=(),
        updated_at=T0,
    )


def test_unconfirmed_block_is_last() -> None:
    assert BLOCK_ORDER[-1] is SelectionBlock.unconfirmed


def test_showcase_takes_only_the_claimed_grade_of_the_need_specialization() -> None:
    fits = unconfirmed(frozenset({"pytest"}))
    other_grade = unconfirmed(frozenset({"pytest"}), JUNIOR)
    other_specialization = dataclasses.replace(fits, candidate_id=uuid.uuid4(), specialization="be")

    shown = showcase(need_of(("pytest",)), [fits, other_grade, other_specialization])

    assert [s.candidate for s in shown] == [fits]
    assert shown[0].stack.matched == ("pytest",)
    assert shown[0].stack.overlap == 1.0


def test_unconfirmed_entries_order_by_self_reported_stack_without_score() -> None:
    half = unconfirmed(frozenset({"pytest"}))
    full = unconfirmed(frozenset({"playwright", "pytest"}))
    none = unconfirmed(frozenset())
    shown = showcase(need_of(("playwright", "pytest")), [half, none, full])

    entries = arrange([], [], showcased=shown, salt=1, now=T0, rules=RULES)

    assert [e.candidate_id for e in entries] == [
        full.candidate_id,
        half.candidate_id,
        none.candidate_id,
    ]
    assert {e.block for e in entries} == {SelectionBlock.unconfirmed}
    assert [(e.rank, e.position) for e in entries] == [(1, 1), (2, 2), (3, 3)]
    for entry in entries:
        assert entry.match_score is None
        assert entry.mutual_score is None
        assert entry.acceptance_probability is None
        assert entry.explanation.topics == ()
        assert entry.explanation.stack.contribution is None
        assert entry.status.kind is GradeStatusKind.unconfirmed
        assert entry.grade == CatalogRef("middle", "Middle")


def test_no_unconfirmed_entry_is_ever_above_a_confirmed_one() -> None:
    """Свойство на случайных выдачах: какие бы скоры ни были у подтверждённых и какой бы стек ни
    был у неподтверждённых, нижний блок идёт после всех записей с категорией."""
    rng = random.Random(36)
    technologies = ("a", "b", "c", "d")
    need = need_of(technologies)
    for _ in range(200):
        items = [
            scored(rng.random(), rng.choice((MIDDLE, JUNIOR)), rng.choice(MAIN_BLOCKS))
            for _ in range(rng.randrange(0, 6))
        ]
        acceptance = [rng.choice((None, rng.random())) for _ in items]
        pool = [
            unconfirmed(frozenset(rng.sample(technologies, rng.randrange(0, 5))))
            for _ in range(rng.randrange(0, 6))
        ]

        entries = arrange(
            items,
            acceptance,
            showcased=showcase(need, pool),
            salt=rng.randrange(1 << 30),
            now=T0,
            rules=RULES,
        )

        blocks = [e.block for e in entries]
        assert len(entries) == len(items) + len(pool)
        assert [e.position for e in entries] == list(range(1, len(entries) + 1))
        bottom = blocks.index(SelectionBlock.unconfirmed) if pool else len(blocks)
        assert SelectionBlock.unconfirmed not in blocks[:bottom]
        assert all(b is SelectionBlock.unconfirmed for b in blocks[bottom:])


def test_confirmed_entries_carry_grade_status() -> None:
    cascaded = scored(0.5, JUNIOR, SelectionBlock.nearby)
    cascaded = dataclasses.replace(
        cascaded, candidate=dataclasses.replace(cascaded.candidate, claimed=MIDDLE)
    )
    exact = scored(0.5, MIDDLE, SelectionBlock.exact)

    entries = arrange([cascaded, exact], [None, None], salt=1, now=T0, rules=RULES)

    assert [e.status.kind for e in entries] == [
        GradeStatusKind.confirmed,
        GradeStatusKind.below_claimed,
    ]
    assert entries[1].status.claimed == CatalogRef("middle", "Middle")
    assert entries[1].grade == CatalogRef("junior", "Junior")
