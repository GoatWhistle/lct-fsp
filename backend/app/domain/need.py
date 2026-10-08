"""Потребность работодателя: заведение, правка и важность тем (mechanics.md, §12).

Хранится то, что ввёл работодатель: поля формы, стек и правки важности тем. Важность остальных
тем выводится из стека при каждом чтении (`app.domain.importance`), поэтому смена стека не
оставляет устаревших значений. Подборка берёт потребность как `app.domain.selection.Need`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.catalog import CatalogRef, Grade, Specialization, Technology, Topic
from app.domain.errors import (
    CityRequired,
    InvalidSalaryRange,
    TopicNotInSpecialization,
    UnknownGrade,
    UnknownSpecialization,
    UnknownTechnology,
)
from app.domain.importance import TopicImportance, topic_importance
from app.domain.selection import Need, NeedContent
from app.domain.work import SalaryRange, WorkFormat

# Ошибки формы потребности — в порядке проверки.
NEED_ERRORS = (
    UnknownSpecialization,
    UnknownGrade,
    UnknownTechnology,
    TopicNotInSpecialization,
    InvalidSalaryRange,
    CityRequired,
)


@dataclass(frozen=True)
class NeedForm:
    """Потребность, как её прислал работодатель: справочники — кодами."""

    title: str
    team_description: str
    specialization: str
    grade: str
    stack: tuple[str, ...]
    # Код темы → важность, которую работодатель поставил сам.
    topic_importance: Mapping[str, TopicImportance]
    work_format: WorkFormat
    city: str | None
    salary_from: int | None
    salary_to: int | None


@dataclass(frozen=True)
class NeedTerms:
    """Проверенная потребность — то, что хранится: справочники найдены, вилка и город по
    правилам, правки важности — только темы своей специализации."""

    title: str
    team_description: str
    specialization: Specialization
    grade: Grade
    # По названию технологии.
    stack: tuple[Technology, ...]
    edited_importance: Mapping[str, TopicImportance]
    work_format: WorkFormat
    city: str | None
    salary: SalaryRange | None


@dataclass(frozen=True)
class NeedRecord:
    """Сохранённая потребность в кабинете работодателя."""

    need: Need
    team_description: str
    created_at: datetime


@dataclass(frozen=True)
class TopicView:
    """Важность темы потребности и технологии стека, из которых она выведена."""

    topic: Topic
    importance: TopicImportance
    # Важность поставил работодатель, а не вывод из стека.
    edited: bool
    technologies: tuple[CatalogRef, ...]


def known_specialization(found: Specialization | None) -> Specialization:
    if found is None:
        raise UnknownSpecialization()
    return found


def known_stack(codes: Sequence[str], found: Sequence[Technology]) -> tuple[Technology, ...]:
    """Стек — любые технологии справочника: `found` — найденные по кодам `codes`."""
    if len(found) != len(set(codes)):
        raise UnknownTechnology()
    return tuple(found)


def check_edited_topics(
    specialization: Specialization, edited: Mapping[str, TopicImportance]
) -> None:
    if set(edited) - {t.code for t in specialization.topics}:
        raise TopicNotInSpecialization()


def need_terms(
    form: NeedForm,
    specialization: Specialization | None,
    grade: Grade | None,
    stack: Sequence[Technology],
) -> NeedTerms:
    """Проверка формы; `specialization`, `grade` и `stack` — найденное в справочнике по кодам
    формы. Ошибки — в порядке `NEED_ERRORS`."""
    known = known_specialization(specialization)
    if grade is None:
        raise UnknownGrade()
    technologies = known_stack(form.stack, stack)
    check_edited_topics(known, form.topic_importance)
    salary = SalaryRange.optional(form.salary_from, form.salary_to)
    city = form.city or None
    if city is None and form.work_format != WorkFormat.remote:
        raise CityRequired()
    return NeedTerms(
        title=form.title,
        team_description=form.team_description,
        specialization=known,
        grade=grade,
        stack=technologies,
        edited_importance=dict(form.topic_importance),
        work_format=form.work_format,
        city=city,
        salary=salary,
    )


def need_content(terms: NeedTerms, now: datetime) -> NeedContent:
    """Проверенная потребность, которую не сохраняли, — черновик после правки человеком: подборка
    по нему строится так же, как по сохранённой."""
    return NeedContent(
        title=terms.title,
        specialization=terms.specialization,
        grade=terms.grade,
        stack=terms.stack,
        edited_importance=terms.edited_importance,
        work_format=terms.work_format,
        city=terms.city,
        salary=terms.salary,
        updated_at=now,
    )


def topic_views(
    specialization: Specialization,
    stack: Sequence[Technology],
    edited: Mapping[str, TopicImportance],
    *,
    key_min_technologies: int,
) -> list[TopicView]:
    """Все темы специализации по порядку — с важностью из стека и правок."""
    rows = topic_importance(
        [t.code for t in specialization.topics],
        {tech.code: set(tech.topics) for tech in stack},
        edited,
        key_min_technologies=key_min_technologies,
    )
    technologies = {tech.code: CatalogRef(tech.code, tech.name) for tech in stack}
    return [
        TopicView(
            topic, row.importance, row.edited, tuple(technologies[c] for c in row.technologies)
        )
        for topic, row in zip(specialization.topics, rows, strict=True)
    ]
