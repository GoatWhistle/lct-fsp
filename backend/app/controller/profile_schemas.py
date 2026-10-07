"""Схемы API профиля кандидата и карточки кандидата для работодателя."""

import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
)

from app.assessment.schemas import CategoryOut, SkillProfileOut
from app.controller.schemas import CatalogRef
from app.domain.work import WorkFormat
from app.salary import SALARY_UNIT, Salary, SalaryBasisOut

DISCLOSED = "Раскрывается работодателю только после принятия приглашения или отклика"

TELEGRAM_USERNAME = re.compile(r"[A-Za-z0-9_]{5,32}")
TELEGRAM_PREFIX = re.compile(r"^(?:https?://)?(?:t\.me/|telegram\.me/)|^@", re.IGNORECASE)


def _text(max_length: int, min_length: int = 0) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


def _one_line(value: object) -> object:
    """Переводы строк и повторные пробелы — в один пробел: однострочное поле в PDF и
    интерфейсе не растёт в высоту."""
    return " ".join(value.split()) if isinstance(value, str) else value


OneLine = BeforeValidator(_one_line)


def _unique_tags(values: list[str]) -> list[str]:
    """Метки без пустых и повторов без учёта регистра; порядок — как ввёл кандидат."""
    seen: set[str] = set()
    tags = []
    for value in values:
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            tags.append(value)
    return tags


def _canonical_formats(values: list[WorkFormat]) -> list[WorkFormat]:
    return [f for f in WorkFormat if f in values]


JobRoles = Annotated[list[Annotated[str, OneLine, _text(100)]], AfterValidator(_unique_tags)]
SoftSkills = Annotated[list[Annotated[str, OneLine, _text(50)]], AfterValidator(_unique_tags)]
WorkFormats = Annotated[list[WorkFormat], AfterValidator(_canonical_formats)]


class SelfReportedOut(BaseModel):
    """Самоописание, которое видно в обезличенной карточке: низший уровень доверия, на
    категорию не влияет. Только структурные поля — свободный текст до раскрытия скрыт."""

    stack: list[CatalogRef] = Field(description="По названию технологии")
    experience_years: int = Field(description="Стаж в ИТ, полных лет; 0 — меньше года")
    work_formats: list[WorkFormat] = Field(description="Допустимые форматы работы")
    city: str | None = Field(description="Где кандидат живёт")
    relocation: bool = Field(description="Готов к переезду")
    industries: list[CatalogRef] = Field(
        description="Интересные сферы бизнеса в порядке справочника; пусто — не указаны"
    )


class ProfileOut(SelfReportedOut, SalaryBasisOut):
    full_name: str = Field(description=DISCLOSED)
    contact_email: str = Field(description=DISCLOSED)
    contact_phone: str | None = Field(description=DISCLOSED)
    telegram: str | None = Field(description=f"Имя пользователя без «@». {DISCLOSED}")
    about: str = Field(description=f"О себе. {DISCLOSED}")
    job_roles: list[str] = Field(
        description=f"Кем кандидат работал или хочет работать. {DISCLOSED}: свободный текст"
    )
    soft_skills: list[str] = Field(description=f"{DISCLOSED}: свободный текст")
    salary_from: int = Field(
        description=f"Ожидаемая зарплата «от». {SALARY_UNIT}. Работодателю не показывается: "
        "по ней считается вероятность принятия приглашения"
    )
    updated_at: datetime


class ProfileIn(BaseModel):
    full_name: Annotated[str, OneLine, _text(200, min_length=1)] = Field(description="ФИО")
    contact_email: EmailStr
    contact_phone: Annotated[str, OneLine, _text(32)] | None = None
    telegram: Annotated[str, _text(64)] | None = Field(
        default=None, description="Имя пользователя, `@имя` или ссылка `t.me/имя`"
    )
    about: Annotated[str, _text(3000)] = Field(default="", description="О себе")

    stack: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Коды технологий из `/api/catalog/technologies`",
    )
    job_roles: JobRoles = Field(
        default_factory=list,
        max_length=10,
        description="Короткие метки: «бэкенд-разработчик», «тимлид»",
    )
    experience_years: StrictInt = Field(ge=0, le=60, description="Полных лет; 0 — меньше года")
    soft_skills: SoftSkills = Field(default_factory=list, max_length=15)

    work_formats: WorkFormats = Field(
        min_length=1, description="Допустимые форматы работы, хотя бы один"
    )
    city: Annotated[str, OneLine, _text(100)] | None = Field(
        default=None, description="Обязателен, если подходит офис или гибрид"
    )
    relocation: bool = False
    industries: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Интересные сферы бизнеса — коды из `/api/catalog/industries`; необязательно",
    )
    salary_from: Salary = Field(gt=0, description=f"Ожидаемая зарплата «от». {SALARY_UNIT}")

    @field_validator("contact_email")
    @classmethod
    def email_is_lowercase(cls, value: str) -> str:
        return value.lower()

    @field_validator("contact_phone", "city")
    @classmethod
    def empty_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("telegram")
    @classmethod
    def telegram_username(cls, value: str | None) -> str | None:
        if not value:
            return None
        username = TELEGRAM_PREFIX.sub("", value).rstrip("/")
        if not TELEGRAM_USERNAME.fullmatch(username):
            raise ValueError("имя в Telegram — от 5 до 32 латинских букв, цифр и «_»")
        return username


class CandidateCardOut(BaseModel):
    """Обезличенная карточка: решение — по навыкам. Без ФИО, контактов, свободного текста
    («о себе», роли, софт-скиллы) и ожидаемой зарплаты; фото, возраст и вуз платформа не
    собирает."""

    id: uuid.UUID
    category: CategoryOut = Field(description="Категория по тесту")
    skill_profile: SkillProfileOut | None = Field(description="Профиль навыков специализации")
    self_reported: SelfReportedOut | None = Field(
        description="Самоописание; `null` — кандидат ещё не заполнил профиль"
    )
