"""Фильтры кандидатов и порядок поиска по банку — чистые функции (mechanics.md, §12)."""

import uuid

import pytest

from app.domain.candidate import GradeStatus, GradeStatusKind
from app.domain.catalog import CatalogRef
from app.domain.search import (
    NO_FILTERS,
    CandidateFacts,
    CandidateFilters,
    CategoryFilter,
    admits,
    search_order,
)
from app.domain.skill import Normal, SkillProfileLevels

JUNIOR = CatalogRef("junior", "Junior")
MIDDLE = CatalogRef("middle", "Middle")
SENIOR = CatalogRef("senior", "Senior")
THRESHOLDS = {"junior": 0.0, "middle": 0.5, "senior": 1.0}
CONFIDENT_SD = 0.6
TYPICAL = Normal(0.5, 0.4)


def facts(
    *,
    specialization: str = "qa",
    status: GradeStatus | None = None,
    stack: frozenset[str] = frozenset(),
    fsp: bool = False,
    overall: Normal | None = TYPICAL,
) -> CandidateFacts:
    status = status or GradeStatus(GradeStatusKind.confirmed, MIDDLE, MIDDLE)
    profile = (
        None
        if overall is None or status.confirmed is None
        else SkillProfileLevels(overall, {}, 0, None)
    )
    return CandidateFacts(uuid.uuid4(), specialization, status, stack, fsp, profile)


def unconfirmed(claimed: CatalogRef = MIDDLE) -> CandidateFacts:
    return facts(status=GradeStatus(GradeStatusKind.unconfirmed, claimed, None))


def passes(filters: CandidateFilters, candidate: CandidateFacts) -> bool:
    return admits(filters, candidate, confident_sd=CONFIDENT_SD)


def test_empty_filters_admit_everyone() -> None:
    assert NO_FILTERS.empty
    assert passes(NO_FILTERS, facts())
    assert passes(NO_FILTERS, unconfirmed())


@pytest.mark.parametrize(
    ("filters", "admitted", "rejected"),
    [
        (CandidateFilters(specialization="qa"), facts(), facts(specialization="backend")),
        (
            CandidateFilters(grade="middle"),
            facts(),
            facts(status=GradeStatus(GradeStatusKind.confirmed, JUNIOR, JUNIOR)),
        ),
        (
            CandidateFilters(category=CategoryFilter("qa", "middle")),
            facts(),
            facts(specialization="backend"),
        ),
        (
            CandidateFilters(stack=frozenset({"pytest", "go"})),
            facts(stack=frozenset({"pytest"})),
            facts(stack=frozenset({"java"})),
        ),
        (CandidateFilters(fsp_confirmed=True), facts(fsp=True), facts()),
        (
            CandidateFilters(confident=True),
            facts(overall=Normal(0.5, CONFIDENT_SD)),
            facts(overall=Normal(0.5, CONFIDENT_SD + 0.01)),
        ),
        (
            CandidateFilters(grade_status=frozenset({GradeStatusKind.unconfirmed})),
            unconfirmed(),
            facts(),
        ),
    ],
    ids=["specialization", "grade", "category", "stack", "fsp", "confident", "grade_status"],
)
def test_each_filter_narrows(
    filters: CandidateFilters, admitted: CandidateFacts, rejected: CandidateFacts
) -> None:
    assert passes(filters, admitted)
    assert not passes(filters, rejected)


def test_grade_of_unconfirmed_is_claimed_but_category_needs_test() -> None:
    claimed_middle = unconfirmed(MIDDLE)

    assert passes(CandidateFilters(grade="middle"), claimed_middle)
    assert not passes(CandidateFilters(category=CategoryFilter("qa", "middle")), claimed_middle)
    # Каскад дал junior при заявленном middle: грейд в выдаче — junior.
    below = facts(status=GradeStatus(GradeStatusKind.below_claimed, MIDDLE, JUNIOR))
    assert passes(CandidateFilters(grade="junior"), below)
    assert not passes(CandidateFilters(grade="middle"), below)


def test_confident_rejects_candidate_without_category() -> None:
    assert not passes(CandidateFilters(confident=True), unconfirmed())


def test_combination_is_intersection() -> None:
    filters = CandidateFilters(stack=frozenset({"pytest"}), fsp_confirmed=True)

    assert passes(filters, facts(stack=frozenset({"pytest"}), fsp=True))
    assert not passes(filters, facts(stack=frozenset({"pytest"})))
    assert not passes(filters, facts(fsp=True))


def test_search_puts_unconfirmed_below_every_confirmed() -> None:
    weak = facts(overall=Normal(-3.0, 0.3))
    without_profile = facts(overall=None)
    strong_claim = unconfirmed(SENIOR)

    hits = search_order([strong_claim, weak, without_profile], THRESHOLDS)

    assert [h.facts for h in hits] == [weak, without_profile, strong_claim]
    assert [h.position for h in hits] == [1, 2, 3]
    assert hits[2].grade_probability is None


def test_search_orders_by_confidence_inside_category() -> None:
    sure = facts(overall=Normal(1.0, 0.2))
    unsure = facts(overall=Normal(1.0, 0.8))

    hits = search_order([unsure, sure], THRESHOLDS)

    assert [h.facts for h in hits] == [sure, unsure]
    assert hits[0].grade_probability == pytest.approx(Normal(1.0, 0.2).prob_at_least(0.5))


def test_search_does_not_compare_confidence_across_grades() -> None:
    """У junior порог ниже, и уверенность в нём выше, — но senior он не обгоняет."""
    senior = facts(
        status=GradeStatus(GradeStatusKind.confirmed, SENIOR, SENIOR), overall=Normal(1.1, 0.4)
    )
    junior = facts(
        status=GradeStatus(GradeStatusKind.confirmed, JUNIOR, JUNIOR), overall=Normal(1.0, 0.2)
    )
    middle = facts()

    hits = search_order([junior, middle, senior], THRESHOLDS)

    assert [h.facts for h in hits] == [senior, middle, junior]
    assert [h.position for h in hits] == [1, 2, 3]
    assert hits[2].grade_probability > hits[0].grade_probability  # type: ignore[operator]


def test_search_order_does_not_depend_on_input_order() -> None:
    found = [facts() for _ in range(5)] + [unconfirmed() for _ in range(3)]

    first = [h.facts for h in search_order(found, THRESHOLDS)]
    again = [h.facts for h in search_order(list(reversed(found)), THRESHOLDS)]

    assert first == again
