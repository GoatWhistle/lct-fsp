"""Карточка опыта — записи опыта со слов кандидата и годы по технологиям из них (mechanics.md,
§11, §16).

Карточка — показ без веса: ни в одну модель — оценку уровня, категорию, скор, модель принятия,
обратную связь — она не входит. Ранжировать по опыту из резюме — ровно то, чем накручивают
подбор. Записи — часть раскрытой части профиля: в месте, роли и «что делал» бывают имена,
компании и контакты, поэтому работодатель видит карточку только после раскрытия.

Годы по технологии не вводятся и не хранятся: их считает `technology_years` из записей на
текущую дату.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Self

from app.domain.catalog import CatalogRef
from app.domain.errors import (
    ExperiencePeriodInvalid,
    ExperiencePlaceRequired,
    ExperienceStartInFuture,
    ExperienceTooLong,
)

# Годы — 1900–2099: «0001-01» дал бы тысячи лет по технологии.
_MONTH = re.compile(r"(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])")
# Годы по технологии округляются вниз до полугода.
_ROUNDING_MONTHS = 6


@dataclass(frozen=True, order=True)
class Month:
    """Месяц и год — точность периода работы в резюме и в форме."""

    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> Self:
        """`ГГГГ-ММ` с годом 1900–2099; другое — `ValueError`."""
        found = _MONTH.fullmatch(text)
        if found is None:
            raise ValueError(f"месяц в виде ГГГГ-ММ, а не {text!r}")
        return cls(int(found["year"]), int(found["month"]))

    @classmethod
    def of(cls, day: date) -> Self:
        return cls(day.year, day.month)

    @property
    def index(self) -> int:
        """Номер месяца от начала эры: разность номеров — число месяцев между ними."""
        return self.year * 12 + self.month - 1

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True)
class ExperienceEntry:
    """Запись опыта: где, кем, когда, на чём и что делал. `end` — `None`: «по сейчас». Оба
    месяца периода входят в него: «2020-01 — 2020-12» — год."""

    place: str
    role: str
    start: Month
    end: Month | None
    # Технологии справочника в порядке названий.
    stack: tuple[CatalogRef, ...]
    summary: str


@dataclass(frozen=True)
class ExperienceInput:
    """Запись опыта, как её прислал кандидат: стек — кодами справочника."""

    place: str
    role: str
    start: Month
    end: Month | None
    stack: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class ExperienceLimits:
    """Лимиты карточки опыта — `experience_*` в `config/mechanics.yaml`."""

    entries_max: int
    # Место и роль — одной строкой.
    line_max: int
    summary_max: int
    stack_max: int


@dataclass(frozen=True)
class TechnologyYears:
    technology: CatalogRef
    # Кратно половине года, вниз.
    years: float


def check_experience(
    entries: Sequence[ExperienceInput], today: date, limits: ExperienceLimits
) -> None:
    """Записи формы в пределах лимитов, с местом и периодом, который начался и не кончился раньше
    начала. Конец после сегодня допустим — годы его не досчитают. Коды стека сверяет хранилище,
    как стек анкеты."""
    if len(entries) > limits.entries_max:
        raise ExperienceTooLong()
    now = Month.of(today)
    for e in entries:
        if not e.place.strip():
            raise ExperiencePlaceRequired()
        if (
            len(e.place) > limits.line_max
            or len(e.role) > limits.line_max
            or len(e.summary) > limits.summary_max
            or len(set(e.stack)) > limits.stack_max
        ):
            raise ExperienceTooLong()
        if e.start > now:
            raise ExperienceStartInFuture()
        if e.end is not None and e.start > e.end:
            raise ExperiencePeriodInvalid()


def technology_years(
    entries: Sequence[ExperienceEntry], today: date
) -> tuple[TechnologyYears, ...]:
    """Годы по каждой технологии записей — длина объединения периодов записей с ней: пересечения
    не считаются дважды, перерывы не считаются. Открытый период и конец после сегодня — по
    текущий месяц включительно. Месяцы округляются вниз до полугода. Порядок — больше лет
    первыми, при равенстве — по названию."""
    now = Month.of(today).index + 1
    periods: dict[CatalogRef, list[tuple[int, int]]] = defaultdict(list)
    for e in entries:
        first = e.start.index
        last = min(e.end.index + 1 if e.end else now, now)
        for technology in e.stack:
            periods[technology].append((first, last))
    result = [
        TechnologyYears(technology, _years(_union_months(spans)))
        for technology, spans in periods.items()
    ]
    return tuple(sorted(result, key=lambda y: (-y.years, y.technology.name)))


def _union_months(spans: Sequence[tuple[int, int]]) -> int:
    months = reached = 0
    for first, last in sorted(spans):
        first = max(first, reached)
        if last > first:
            months += last - first
            reached = last
    return months


def _years(months: int) -> float:
    return months // _ROUNDING_MONTHS * _ROUNDING_MONTHS / 12
