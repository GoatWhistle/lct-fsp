"""Инварианты подборки в домене (mechanics.md, §12–13, §17): порядок блоков, досягаемость,
взаимный скор и признаки модели принятия."""

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.catalog import CatalogRef, Grade
from app.domain.match import Match, StackFit
from app.domain.selection import (
    BLOCK_ORDER,
    AcceptanceFeatures,
    PoolCandidate,
    Scored,
    SelectionBlock,
    SelectionRules,
    arrange,
    block_of,
    mutual_score,
)
from app.domain.skill import Normal

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
