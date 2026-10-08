"""Проверки покрытия банка (mechanics.md, §5) — чистые функции над семействами, матрицей
грейдов и параметрами, каждая возвращает список нарушений.

Тест различает грейды, только если задания ячейки мерят её умения. Трассировку («что выведет
код») решат и junior, и senior: она мерит внимательность, поэтому её доля в теме ограничена. У
middle и senior в каждой теме нужны сценарные задания — выбор решения, поиск ошибки, порядок
шагов, разбор инцидента. Отчёт покрытия зовёт эти функции; строгие тесты порогов на настоящем
банке будут звать их же.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.bank.family import SCENARIO_KINDS, Family, Kind
from app.domain.grade_matrix import Cell, GradeMatrix

# Грейды, у которых в каждой теме нужны сценарные семейства.
SCENARIO_GRADES = ("middle", "senior")


@dataclass(frozen=True)
class Bounds:
    """Пороги покрытия — `bank_max_trace_share_per_topic` и
    `bank_min_scenario_families_per_grade` из docs/parameters.md."""

    max_trace_share_per_topic: float
    min_scenario_families_per_grade: int


@dataclass(frozen=True)
class Violation:
    """Нарушение в теме или в ячейке темы × грейда (`grade` задан)."""

    topic: str
    grade: str | None
    message: str


def topic_counts(families: Iterable[Family]) -> dict[str, tuple[int, int]]:
    """Тема → (семейств, из них трассировки), темы — по алфавиту."""
    total: Counter[str] = Counter()
    traces: Counter[str] = Counter()
    for family in families:
        total[family.topic] += 1
        traces[family.topic] += family.kind == Kind.TRACE
    return {topic: (n, traces[topic]) for topic, n in sorted(total.items())}


def scenario_counts(families: Iterable[Family]) -> Counter[Cell]:
    """Сценарных семейств в каждой ячейке."""
    return Counter(Cell(f.topic, f.grade) for f in families if f.kind in SCENARIO_KINDS)


def trace_overflow(families: Iterable[Family], bounds: Bounds) -> list[Violation]:
    """Темы, где доля трассировки среди семейств выше потолка."""
    limit = bounds.max_trace_share_per_topic
    return [
        Violation(
            topic,
            None,
            f"трассировка — {traces} из {n} ({traces / n:.2f}) при потолке {limit}",
        )
        for topic, (n, traces) in topic_counts(families).items()
        if traces / n > limit
    ]


def scenario_shortage(families: Iterable[Family], bounds: Bounds) -> list[Violation]:
    """Ячейки middle и senior, где сценарных семейств меньше минимума."""
    families = list(families)
    scenarios = scenario_counts(families)
    minimum = bounds.min_scenario_families_per_grade
    return [
        Violation(
            topic,
            grade,
            f"сценарных семейств {scenarios[Cell(topic, grade)]} при минимуме {minimum}",
        )
        for topic in sorted({f.topic for f in families})
        for grade in SCENARIO_GRADES
        if scenarios[Cell(topic, grade)] < minimum
    ]


def cells_without_families(families: Iterable[Family], matrix: GradeMatrix) -> list[Violation]:
    """Ячейки, описанные в матрице, где нет ни одного семейства."""
    present = {Cell(f.topic, f.grade) for f in families}
    return [
        Violation(cell.topic, cell.grade, "в матрице описана, семейств нет")
        for cell in sorted(matrix.cells)
        if cell not in present
    ]


def cells_without_description(families: Iterable[Family], matrix: GradeMatrix) -> list[Violation]:
    """Ячейки с семействами, которых нет в матрице: неясно, какие умения они мерят."""
    counts = Counter(Cell(f.topic, f.grade) for f in families)
    return [
        Violation(cell.topic, cell.grade, f"семейств {n}, в матрице не описана")
        for cell, n in sorted(counts.items())
        if cell not in matrix.cells
    ]
