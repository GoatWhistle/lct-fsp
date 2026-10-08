"""Проверки покрытия банка (mechanics.md, §5) на маленьком синтетическом банке: каждая находит
своё нарушение. На настоящем банке те же функции строят отчёт `python -m bank_report`."""

import random

import pytest

import bank_report
from app.domain.bank import Family, Instance, Kind
from app.domain.bank.coverage import (
    Bounds,
    Violation,
    cells_without_description,
    cells_without_families,
    scenario_shortage,
    trace_overflow,
)
from app.domain.bank.runner import CodeRunner
from app.domain.grade_matrix import Cell, GradeMatrix

BOUNDS = Bounds(max_trace_share_per_topic=0.25, min_scenario_families_per_grade=2)
GRADES = ("intern", "junior", "middle", "senior")


def _generate(rng: random.Random, runner: CodeRunner) -> Instance:
    return Instance("?", "1", {})


def family(topic: str, grade: str, kind: Kind, n: int = 0) -> Family:
    return Family(f"{topic}.{grade}-{kind}-{n}", topic, grade, kind, _generate)


def balanced(topic: str) -> list[Family]:
    """Тема без нарушений: по грейду — вычисление, у старших — два сценария, одна трассировка."""
    families = [family(topic, grade, Kind.COMPUTE) for grade in GRADES]
    for grade in ("middle", "senior"):
        families += [family(topic, grade, Kind.SCENARIO_CHOICE, n) for n in range(2)]
    families.append(family(topic, "intern", Kind.TRACE))
    return families


def matrix(*topics: str) -> GradeMatrix:
    return GradeMatrix({Cell(t, g): ("умеет",) for t in topics for g in GRADES})


def test_balanced_bank_has_no_violations() -> None:
    bank = balanced("a.x")

    assert trace_overflow(bank, BOUNDS) == []
    assert scenario_shortage(bank, BOUNDS) == []
    assert cells_without_families(bank, matrix("a.x")) == []
    assert cells_without_description(bank, matrix("a.x")) == []


def test_trace_share_above_ceiling_is_found() -> None:
    bank = [*balanced("a.x"), *(family("a.x", "junior", Kind.TRACE, n) for n in range(3))]

    # 4 трассировки из 12 — 0,33 > 0,25.
    assert trace_overflow(bank, BOUNDS) == [
        Violation("a.x", None, "трассировка — 4 из 12 (0.33) при потолке 0.25")
    ]


def test_trace_share_at_ceiling_is_allowed() -> None:
    bank = [*balanced("a.x"), *(family("a.x", "junior", Kind.TRACE, n) for n in range(2))]
    bank.append(family("a.x", "junior", Kind.COMPUTE))

    # 3 трассировки из 12 — ровно потолок.
    assert trace_overflow(bank, BOUNDS) == []


def test_missing_scenarios_for_senior_grades_are_found() -> None:
    bank = [f for f in balanced("a.x") if f.code != "a.x.senior-scenario_choice-1"]

    assert scenario_shortage(bank, BOUNDS) == [
        Violation("a.x", "senior", "сценарных семейств 1 при минимуме 2")
    ]


def test_every_scenario_kind_counts_and_junior_grades_need_none() -> None:
    bank = [family("a.x", grade, Kind.COMPUTE) for grade in GRADES]
    bank += [
        family("a.x", "middle", Kind.BUG_HUNT),
        family("a.x", "middle", Kind.ORDERING),
        family("a.x", "senior", Kind.INCIDENT),
        family("a.x", "senior", Kind.SCENARIO_CHOICE),
    ]

    assert scenario_shortage(bank, BOUNDS) == []


def test_cell_described_in_matrix_without_families_is_found() -> None:
    bank = [f for f in balanced("a.x") if f.grade != "junior"]

    assert cells_without_families(bank, matrix("a.x")) == [
        Violation("a.x", "junior", "в матрице описана, семейств нет")
    ]


def test_family_in_cell_without_description_is_found() -> None:
    bank = [*balanced("a.x"), family("b.y", "middle", Kind.COMPUTE)]

    assert cells_without_description(bank, matrix("a.x")) == [
        Violation("b.y", "middle", "семейств 1, в матрице не описана")
    ]


def test_report_on_real_bank_shows_violations_without_failing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Нарушения настоящего банка видны в отчёте; строгие пороги на нём включит наполнение банка."""
    bank_report.main([])

    report = capsys.readouterr().out
    assert report.startswith("# Покрытие банка заданий")
    assert "### Доля трассировки выше потолка" in report
    assert "### Сценарных семейств меньше минимума" in report
    assert "`backend.databases` | 17 |" in report
    assert "Данных калибровки нет" in report
