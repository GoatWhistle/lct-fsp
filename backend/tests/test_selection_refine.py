"""Уточнение подборки фильтрами, шортлист и поиск по банку — сценарии на портах (mechanics.md,
§12). Те же тесты идут на in-memory репозиториях и на Postgres."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest

from app.domain.candidate import GradeStatusKind
from app.domain.errors import NotInSelection, SelectionNotFound
from app.domain.search import NO_FILTERS, CandidateFilters, CategoryFilter
from app.domain.selection import Page, SelectionBlock
from app.domain.skill import Normal
from tests.test_selection_scenarios import (
    CandidateSeed,
    Harness,
    UnconfirmedSeed,
    make,
    remote,
)

__all__ = ["make"]

PAGE: dict[str, Any] = {"offset": 0, "limit": 100}


def built(h: Harness) -> tuple[list[uuid.UUID], Page]:
    """Подборка по потребности middle QA: шесть кандидатов в трёх блоках."""
    ids = h.candidates(
        [
            CandidateSeed(stack=("pytest",), expectations=remote(200_000)),
            CandidateSeed(fsp=True),
            CandidateSeed(grade="junior", stack=("playwright",), expectations=remote(150_000)),
            CandidateSeed(grade="senior", overall=Normal(1.5, 0.3)),
        ]
    )
    ids.append(h.unconfirmed(UnconfirmedSeed(chain=("middle",))))
    page = h.selections.build(h.employer, h.need(), limit=100)
    return ids, page


def test_refine_narrows_without_touching_places_and_reset_restores(
    make: Callable[..., Harness],
) -> None:
    h = make()
    _, page = built(h)
    original = h.selections.open(h.employer, page.selection.id, **PAGE)

    refined = h.selections.refine(
        h.employer,
        page.selection.id,
        CandidateFilters(stack=frozenset({"pytest", "playwright"})),
        **PAGE,
    )

    kept = [e for e in original.entries if e in refined.entries]
    assert list(refined.entries) == kept, "строки — исходные, порядок — исходный"
    assert len(refined.entries) == 2
    assert refined.totals == original.totals
    assert refined.filtered_totals == {
        SelectionBlock.exact: 1,
        SelectionBlock.nearby: 1,
        SelectionBlock.unconfirmed: 0,
    }

    reset = h.selections.refine(h.employer, page.selection.id, NO_FILTERS, **PAGE)
    assert reset == original


def test_reopen_returns_last_filters_and_filtered_page(make: Callable[..., Harness]) -> None:
    h = make()
    _, page = built(h)
    filters = CandidateFilters(grade_status=frozenset({GradeStatusKind.unconfirmed}))

    h.selections.refine(h.employer, page.selection.id, filters, **PAGE)
    reopened = h.selections.open(h.employer, page.selection.id, **PAGE)

    assert reopened.selection.filters == filters
    assert [e.block for e in reopened.entries] == [SelectionBlock.unconfirmed]
    assert h.selections.summaries(h.employer, None, limit=10)[0].selection.filters == filters


def test_refine_pages_through_filtered_output(make: Callable[..., Harness]) -> None:
    h = make()
    _, page = built(h)
    filters = CandidateFilters(specialization="qa")
    whole = h.selections.refine(h.employer, page.selection.id, filters, **PAGE).entries

    second = h.selections.open(h.employer, page.selection.id, offset=1, limit=2)

    assert second.entries == whole[1:3]
    assert second.offset == 1


@pytest.mark.parametrize(
    "filters",
    [
        CandidateFilters(fsp_confirmed=True),
        CandidateFilters(confident=True),
        CandidateFilters(category=CategoryFilter("qa", "junior")),
        CandidateFilters(grade="middle"),
    ],
    ids=["fsp", "confident", "category", "grade"],
)
def test_filter_over_selection_matches_search_over_the_same_people(
    make: Callable[..., Harness], filters: CandidateFilters
) -> None:
    """Одно правило на два пути: кто прошёл фильтр в подборке, тот проходит его и в поиске."""
    h = make()
    _, page = built(h)

    refined = h.selections.refine(h.employer, page.selection.id, filters, **PAGE)
    searched = h.selections.search(filters, **PAGE)

    in_selection = {e.candidate_id for e in refined.entries}
    assert in_selection
    assert in_selection == {hit.facts.candidate_id for hit in searched.hits} & {
        e.candidate_id for e in page.entries
    }


def test_shortlist_survives_reopen_and_filters(make: Callable[..., Harness]) -> None:
    h = make()
    ids, page = built(h)
    selection_id = page.selection.id
    first, second = ids[0], ids[2]

    h.selections.shortlist(h.employer, selection_id, first, True)
    h.selections.shortlist(h.employer, selection_id, second, True)
    h.selections.shortlist(h.employer, selection_id, second, True)
    h.selections.shortlist(h.employer, selection_id, first, False)
    h.selections.refine(h.employer, selection_id, CandidateFilters(fsp_confirmed=True), **PAGE)

    listed = h.selections.shortlisted(h.employer, selection_id)
    assert [e.candidate_id for e in listed.entries] == [second]
    assert h.selections.open(h.employer, selection_id, **PAGE).selection.shortlist == (second,)
    assert second not in {
        e.candidate_id for e in h.selections.open(h.employer, selection_id, **PAGE).entries
    }


def test_shortlist_takes_only_candidates_of_the_selection(make: Callable[..., Harness]) -> None:
    h = make()
    _, page = built(h)
    stranger = h.candidate(CandidateSeed(specialization="backend"))

    with pytest.raises(NotInSelection):
        h.selections.shortlist(h.employer, page.selection.id, stranger, True)


def test_foreign_selection_is_not_found_for_refine_and_shortlist(
    make: Callable[..., Harness],
) -> None:
    h = make()
    ids, page = built(h)
    other = h.user()

    with pytest.raises(SelectionNotFound):
        h.selections.refine(other, page.selection.id, NO_FILTERS, **PAGE)
    with pytest.raises(SelectionNotFound):
        h.selections.shortlist(other, page.selection.id, ids[0], True)
    with pytest.raises(SelectionNotFound):
        h.selections.shortlisted(other, page.selection.id)


def test_search_puts_unconfirmed_below_confirmed(make: Callable[..., Harness]) -> None:
    h = make()
    ids, _ = built(h)
    backend = h.candidate(CandidateSeed(specialization="backend"))

    found = h.selections.search(NO_FILTERS, **PAGE)

    order = [hit.facts.candidate_id for hit in found.hits]
    assert set(order) == {*ids, backend}
    assert order[-1] == ids[-1], "заявленный неподтверждённый грейд — ниже всех"
    assert (found.total, found.unconfirmed_total) == (6, 1)
    assert [hit.position for hit in found.hits] == list(range(1, 7))

    only_backend = h.selections.search(CandidateFilters(specialization="backend"), **PAGE)
    assert [hit.facts.candidate_id for hit in only_backend.hits] == [backend]
