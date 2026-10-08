"""M21 — точность разбора потребности из текста по полям на размеченном наборе
(docs/validation-plan.md, D5 и M21). Формат набора — `validation/data/need_texts.md`.

Разбор идёт тем же сценарием, что HTTP (`NeedDrafts.parse`), на стенде со справочником из
`catalog.yaml`. Порог — из плана валидации; базовая линия для специализации и грейда — самый
частый класс разметки.
"""

import statistics
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.domain.need_draft import CheckedDraft, CheckedOutOfCatalog
from app.domain.work import WorkFormat

# Порог M21 по полям — из плана валидации.
THRESHOLDS = {
    "specialization": 0.90,
    "grade": 0.80,
    "stack": 0.80,
    "work_format": 0.85,
    "city": 0.85,
    "salary": 0.90,
    "out_of_catalog": 0.90,
}
FIELD_NAMES = {
    "specialization": "Специализация",
    "grade": "Грейд",
    "stack": "Стек, micro-F1",
    "work_format": "Формат",
    "city": "Город",
    "salary": "Вилка «от» и «до»",
    "out_of_catalog": "Вне справочника, полнота",
}


class LabeledText(BaseModel):
    """Текст с разметкой; `checked_by` — чья она. Значения — коды справочника, чего в тексте
    нет — `null`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    source: str
    date: date
    checked_by: str = Field(min_length=1)
    text: str
    out_of_catalog: bool = False
    specialization: str | None = None
    grade: str | None = None
    stack: list[str] = Field(default_factory=list)
    work_format: WorkFormat | None = None
    city: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None


class LabeledSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    texts: list[LabeledText] = Field(min_length=1)


def load_labeled(path: Path) -> list[LabeledText]:
    with path.open(encoding="utf-8") as f:
        return LabeledSet.model_validate(yaml.safe_load(f)).texts


Parsed = CheckedDraft | CheckedOutOfCatalog


@dataclass(frozen=True)
class FieldScore:
    field: str
    # Сколько текстов вошло в метрику.
    total: int
    value: float | None
    baseline: float | None
    threshold: float

    @property
    def passed(self) -> bool | None:
        return None if self.value is None else self.value >= self.threshold


@dataclass(frozen=True)
class ParsingReport:
    fields: list[FieldScore]
    # Медиана времени разбора текста, мс.
    median_ms: float


def _share(hits: Sequence[bool]) -> float | None:
    return sum(hits) / len(hits) if hits else None


def _majority(labels: Sequence[str | None]) -> float | None:
    """Точность ответа «самый частый класс разметки»."""
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][1] / len(labels)


def _code(ref: object) -> str | None:
    return getattr(ref, "code", None)


def score_parsing(labeled: Sequence[LabeledText], parsed: Sequence[Parsed]) -> list[FieldScore]:
    """Точность по полям. Поля потребности считаются на текстах из справочника: ответ «вне
    справочника» на таком тексте — промах по каждому полю. Вилка — на текстах, где она есть, и
    только точное совпадение обеих границ."""
    pairs = list(zip(labeled, parsed, strict=True))
    inside = [(t, p) for t, p in pairs if not t.out_of_catalog]
    drafts = [(t, p if isinstance(p, CheckedDraft) else None) for t, p in inside]

    def accuracy(
        get: Callable[[CheckedDraft], object], label: Callable[[LabeledText], object]
    ) -> float | None:
        return _share([d is not None and get(d) == label(t) for t, d in drafts])

    true_positive = false_positive = false_negative = 0
    for t, d in drafts:
        predicted = {s.code for s in d.stack} if d else set()
        wanted = set(t.stack)
        true_positive += len(predicted & wanted)
        false_positive += len(predicted - wanted)
        false_negative += len(wanted - predicted)
    f1_base = 2 * true_positive + false_positive + false_negative
    stack_f1 = 2 * true_positive / f1_base if f1_base else None

    with_salary = [
        (t, d) for t, d in drafts if t.salary_from is not None or t.salary_to is not None
    ]
    outside = [p for t, p in pairs if t.out_of_catalog]
    values = {
        "specialization": (
            len(drafts),
            accuracy(lambda d: _code(d.specialization), lambda t: t.specialization),
            _majority([t.specialization for t, _ in drafts]),
        ),
        "grade": (
            len(drafts),
            accuracy(lambda d: _code(d.grade), lambda t: t.grade),
            _majority([t.grade for t, _ in drafts]),
        ),
        "stack": (len(drafts), stack_f1, None),
        "work_format": (
            len(drafts),
            accuracy(lambda d: d.work_format, lambda t: t.work_format),
            None,
        ),
        "city": (len(drafts), accuracy(lambda d: d.city, lambda t: t.city), None),
        "salary": (
            len(with_salary),
            _share(
                [
                    d is not None and (d.salary_from, d.salary_to) == (t.salary_from, t.salary_to)
                    for t, d in with_salary
                ]
            ),
            None,
        ),
        "out_of_catalog": (
            len(outside),
            _share([isinstance(p, CheckedOutOfCatalog) for p in outside]),
            None,
        ),
    }
    return [
        FieldScore(name, total, value, baseline, THRESHOLDS[name])
        for name, (total, value, baseline) in values.items()
    ]


def run_parsing(labeled: Sequence[LabeledText], parse: Callable[[str], Parsed]) -> ParsingReport:
    parsed, elapsed = [], []
    for item in labeled:
        start = time.perf_counter()
        parsed.append(parse(item.text))
        elapsed.append((time.perf_counter() - start) * 1000)
    return ParsingReport(score_parsing(labeled, parsed), statistics.median(elapsed))


def parsing_table(report: ParsingReport) -> str:
    def number(value: float | None) -> str:
        return "—" if value is None else f"{value:.2f}"

    rows = [
        "| Поле | Текстов | Точность | Базовая линия | Порог | Проходит |",
        "|---|---|---|---|---|---|",
    ]
    for s in report.fields:
        verdict = {True: "да", False: "нет", None: "нет данных"}[s.passed]
        rows.append(
            f"| {FIELD_NAMES[s.field]} | {s.total} | {number(s.value)} | {number(s.baseline)} "
            f"| {s.threshold:.2f} | {verdict} |"
        )
    rows.append("")
    rows.append(f"Медиана времени разбора: {report.median_ms:.1f} мс на текст.")
    return "\n".join(rows)
