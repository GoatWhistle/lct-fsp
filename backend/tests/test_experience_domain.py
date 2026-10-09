"""Карточка опыта: годы по технологиям и проверка записей — чистые функции домена."""

from datetime import date

import pytest

from app.domain import errors
from app.domain.catalog import CatalogRef
from app.domain.experience import (
    ExperienceEntry,
    ExperienceInput,
    ExperienceLimits,
    Month,
    TechnologyYears,
    check_experience,
    technology_years,
)

TODAY = date(2026, 10, 8)
PYTHON = CatalogRef("python", "Python")
DOCKER = CatalogRef("docker", "Docker")
GO = CatalogRef("go", "Go")
LIMITS = ExperienceLimits(entries_max=3, line_max=20, summary_max=50, stack_max=2)


def entry(
    start: str, end: str | None, *stack: CatalogRef, place: str = "ООО «Ромашка»"
) -> ExperienceEntry:
    return ExperienceEntry(
        place=place,
        role="Разработчик",
        start=Month.parse(start),
        end=Month.parse(end) if end else None,
        stack=stack,
        summary="",
    )


def given(
    start: str = "2020-01",
    end: str | None = "2021-12",
    *,
    stack: tuple[str, ...] = ("python",),
    place: str = "ООО «Ромашка»",
    role: str = "Разработчик",
    summary: str = "",
) -> ExperienceInput:
    return ExperienceInput(
        place=place,
        role=role,
        start=Month.parse(start),
        end=Month.parse(end) if end else None,
        stack=stack,
        summary=summary,
    )


def years(*entries: ExperienceEntry) -> dict[str, float]:
    return {y.technology.code: y.years for y in technology_years(entries, TODAY)}


def test_month_reads_and_writes_year_dash_month() -> None:
    month = Month.parse("2021-03")

    assert (month.year, month.month) == (2021, 3)
    assert str(month) == "2021-03"
    assert Month.parse("2020-12") < month
    assert Month.of(TODAY) == Month(2026, 10)


@pytest.mark.parametrize(
    "text", ["2021-13", "2021-00", "21-03", "2021-3", "март 2021", "", "0001-01", "2100-01"]
)
def test_month_rejects_other_forms(text: str) -> None:
    with pytest.raises(ValueError):
        Month.parse(text)


def test_period_counts_both_months_inclusive() -> None:
    # Январь — декабрь: двенадцать месяцев, ровно год.
    assert years(entry("2020-01", "2020-12", PYTHON)) == {"python": 1.0}


def test_years_round_down_to_half_year() -> None:
    # 17 месяцев — полтора года, а не почти два.
    assert years(entry("2020-01", "2021-05", PYTHON)) == {"python": 1.0}
    assert years(entry("2020-01", "2021-06", PYTHON)) == {"python": 1.5}
    assert years(entry("2020-01", "2020-05", PYTHON)) == {"python": 0.0}


def test_overlapping_periods_with_one_technology_are_not_counted_twice() -> None:
    found = years(
        entry("2020-01", "2021-12", PYTHON, DOCKER),
        # С 2021-01 по 2022-12 — год пересечения с первой записью по Python.
        entry("2021-01", "2022-12", PYTHON, place="Подработка"),
    )

    assert found == {"python": 3.0, "docker": 2.0}


def test_gap_between_periods_is_not_counted() -> None:
    found = years(entry("2018-01", "2018-12", PYTHON), entry("2020-01", "2020-12", PYTHON))

    assert found == {"python": 2.0}


def test_open_period_runs_to_current_month_from_clock() -> None:
    # 2025-10 … 2026-10 — тринадцать месяцев.
    assert years(entry("2025-10", None, GO)) == {"go": 1.0}
    assert technology_years([entry("2025-10", None, GO)], date(2026, 4, 1)) == (
        TechnologyYears(GO, 0.5),
    )


def test_end_after_today_counts_only_to_today() -> None:
    assert years(entry("2025-11", "2030-12", GO)) == years(entry("2025-11", None, GO))


def test_most_years_first_then_by_name() -> None:
    found = technology_years(
        [entry("2020-01", "2021-12", PYTHON), entry("2024-01", "2025-12", DOCKER, GO)], TODAY
    )

    assert [y.technology for y in found] == [DOCKER, GO, PYTHON]


def test_entries_without_stack_give_no_years() -> None:
    assert technology_years([entry("2020-01", "2021-12")], TODAY) == ()


def test_valid_entries_pass() -> None:
    check_experience([given(), given("2026-10", None)], TODAY, LIMITS)


def test_start_after_end_is_an_error() -> None:
    with pytest.raises(errors.ExperiencePeriodInvalid):
        check_experience([given("2022-01", "2021-12")], TODAY, LIMITS)


@pytest.mark.parametrize("end", ["2026-12", None])
def test_start_in_future_is_an_error(end: str | None) -> None:
    with pytest.raises(errors.ExperienceStartInFuture):
        check_experience([given("2026-11", end)], TODAY, LIMITS)


@pytest.mark.parametrize(
    "entries",
    [
        [given()] * 4,
        [given(place="Ж" * 21)],
        [given(role="Ж" * 21)],
        [given(summary="Ж" * 51)],
        [given(stack=("python", "go", "docker"))],
    ],
    ids=["записей", "место", "роль", "что делал", "стек"],
)
def test_limits_are_errors(entries: list[ExperienceInput]) -> None:
    with pytest.raises(errors.ExperienceTooLong):
        check_experience(entries, TODAY, LIMITS)


def test_place_is_required() -> None:
    with pytest.raises(errors.ExperiencePlaceRequired):
        check_experience([given(place="  ")], TODAY, LIMITS)
