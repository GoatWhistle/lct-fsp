"""Вакансия работодателя (mechanics.md, §14): публичная витрина, на которую кандидат откликается
сам. С потребностью не связана: потребность — вход подборки, вакансия — объявление.

Вилка обязательна и проверяется так же, как у приглашения (`SalaryRange`). Снятая с публикации
вакансия — архивная: в общем списке её нет, откликнуться на неё нельзя, поданные отклики
остаются. Вернуть в публикацию нельзя — только опубликовать заново. Компания — учётка
работодателя; её название записывается при публикации и при каждой правке.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.catalog import CatalogRef, Grade, Specialization
from app.domain.errors import InvalidSalaryRange, UnknownGrade, UnknownSpecialization
from app.domain.work import SalaryRange, WorkFormat

# Ошибки формы вакансии — в порядке проверки.
VACANCY_ERRORS = (UnknownSpecialization, UnknownGrade, InvalidSalaryRange)


@dataclass(frozen=True)
class VacancyForm:
    """Вакансия, как её прислал работодатель: справочники — кодами."""

    title: str
    description: str
    specialization: str
    grade: str
    work_formats: tuple[WorkFormat, ...]
    salary_from: int
    salary_to: int


@dataclass(frozen=True)
class VacancyTerms:
    """Проверенная вакансия: справочники найдены, вилка по правилам, форматы без повторов. Вилка
    — рубли в месяц до вычета НДФЛ."""

    title: str
    description: str
    specialization: CatalogRef
    grade: CatalogRef
    work_formats: tuple[WorkFormat, ...]
    salary: SalaryRange


@dataclass(frozen=True)
class Vacancy:
    id: uuid.UUID
    employer_id: uuid.UUID
    company_name: str
    terms: VacancyTerms
    published_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


def vacancy_terms(
    form: VacancyForm, specialization: Specialization | None, grade: Grade | None
) -> VacancyTerms:
    """Проверка формы; `specialization` и `grade` — найденное в справочнике по кодам формы.
    Ошибки — в порядке `VACANCY_ERRORS`."""
    if specialization is None:
        raise UnknownSpecialization()
    if grade is None:
        raise UnknownGrade()
    return VacancyTerms(
        title=form.title,
        description=form.description,
        specialization=CatalogRef(specialization.code, specialization.name),
        grade=CatalogRef(grade.code, grade.name),
        work_formats=tuple(dict.fromkeys(form.work_formats)),
        salary=SalaryRange(form.salary_from, form.salary_to),
    )


def archived(vacancy: Vacancy, now: datetime) -> Vacancy:
    """Снять с публикации; повторное снятие ничего не меняет."""
    if vacancy.is_archived:
        return vacancy
    return replace(vacancy, archived_at=now)
