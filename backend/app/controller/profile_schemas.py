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

from app.controller.fsp_schemas import FspAchievementOut, FspAnonymizedAchievementOut
from app.controller.path_schemas import CategoryOut, SkillProfileOut
from app.controller.salary import SALARY_UNIT, Salary, SalaryBasisOut
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain.candidate import HideableField
from app.domain.resume_draft import ResumeField
from app.domain.work import WorkFormat

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


FROM_CANDIDATE = (
    "Со слов кандидата: тестом и ФСП не подтверждено, на скор, место в выдаче, уровень и "
    "категорию не влияет"
)
MONTH = r"^(19|20)\d{2}-(0[1-9]|1[0-2])$"
Month = Annotated[str, StringConstraints(pattern=MONTH)]


class ExperienceEntryIn(BaseModel):
    """Запись опыта. Лимиты длины и числа записей — `experience_*` в механиках."""

    place: Annotated[str, OneLine, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Компания или проект"
    )
    role: Annotated[str, OneLine, StringConstraints(strip_whitespace=True)] = Field(
        default="", description="Кем работал"
    )
    start: Month = Field(description="Начало, `ГГГГ-ММ`; не в будущем")
    end: Month | None = Field(
        default=None, description="Конец, `ГГГГ-ММ`, не раньше начала; `null` — по сейчас"
    )
    stack: list[str] = Field(
        default_factory=list, description="Коды технологий из `/api/catalog/technologies`"
    )
    summary: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        default="", description="Что делал"
    )


class ExperienceEntryOut(BaseModel):
    place: str = Field(description="Компания или проект")
    role: str
    start: str = Field(description="`ГГГГ-ММ`")
    end: str | None = Field(description="`ГГГГ-ММ`; `null` — по сейчас")
    stack: list[CatalogRef] = Field(description="По названию технологии")
    summary: str = Field(description="Что делал")


class TechnologyYearsOut(BaseModel):
    technology: CatalogRef
    years: float = Field(
        description="Объединение периодов записей с технологией, лет, вниз до половины года"
    )


EXPERIENCE = f"Карточка опыта. {FROM_CANDIDATE}. {DISCLOSED}"
TECHNOLOGY_YEARS = (
    "Годы по технологиям — посчитаны из записей опыта на сегодня, руками не вводятся; больше "
    f"лет — раньше. {FROM_CANDIDATE}. {DISCLOSED}"
)


class SelfReportedOut(BaseModel):
    """Структурная часть самоописания: низший уровень доверия, на категорию не влияет."""

    stack: list[CatalogRef] = Field(description="По названию технологии")
    experience_years: int = Field(description="Стаж в ИТ, полных лет; 0 — меньше года")
    work_formats: list[WorkFormat] = Field(description="Допустимые форматы работы")
    city: str | None = Field(description="Где кандидат живёт")
    relocation: bool = Field(description="Готов к переезду")
    industries: list[CatalogRef] = Field(
        description="Интересные сферы бизнеса в порядке справочника; пусто — не указаны"
    )


HIDDEN = (
    "Поля самоописания, которые кандидат скрыл из обезличенной карточки: работодатель увидит их "
    "только после принятия приглашения или отклика. На подбор и скор не влияет, в PDF-профиле "
    "всё полностью. Пусто — видно всё"
)


def _canonical_hidden(values: list[HideableField]) -> list[HideableField]:
    return [f for f in HideableField if f in values]


HiddenFields = Annotated[list[HideableField], AfterValidator(_canonical_hidden)]


class CardSelfReportedOut(BaseModel):
    """Самоописание в карточке кандидата для работодателя. Поле, скрытое кандидатом, — `null`
    и его имя в `hidden`; `null` без имени в `hidden` — не заполнено."""

    stack: list[CatalogRef] | None = Field(description="По названию технологии")
    experience_years: int | None = Field(description="Стаж в ИТ, полных лет; 0 — меньше года")
    work_formats: list[WorkFormat] = Field(description="Допустимые форматы работы; видны всегда")
    city: str | None = Field(description="Где кандидат живёт")
    relocation: bool | None = Field(description="Готов к переезду")
    industries: list[CatalogRef] | None = Field(
        description="Интересные сферы бизнеса в порядке справочника; пусто — не указаны"
    )
    hidden: HiddenFields = Field(
        description="Скрыто кандидатом до принятия приглашения или отклика; после — пусто"
    )


class ProfileOut(SelfReportedOut, SalaryBasisOut):
    hidden: HiddenFields = Field(description=HIDDEN)
    full_name: str = Field(description=DISCLOSED)
    contact_email: str = Field(description=DISCLOSED)
    contact_phone: str | None = Field(description=DISCLOSED)
    telegram: str | None = Field(description=f"Имя пользователя без «@». {DISCLOSED}")
    about: str = Field(description=f"О себе. {DISCLOSED}")
    job_roles: list[str] = Field(
        description=f"Кем кандидат работал или хочет работать. {DISCLOSED}: свободный текст"
    )
    soft_skills: list[str] = Field(description=f"{DISCLOSED}: свободный текст")
    experience: list[ExperienceEntryOut] = Field(description=EXPERIENCE)
    technology_years: list[TechnologyYearsOut] = Field(description=TECHNOLOGY_YEARS)
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
    experience: list[ExperienceEntryIn] = Field(
        default_factory=list, description=f"Карточка опыта. {FROM_CANDIDATE}"
    )

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
    hidden: HiddenFields = Field(default_factory=list, description=HIDDEN)

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


class DisclosedOut(BaseModel):
    """Раскрытая часть анкеты: ФИО, контакты, свободный текст и карточка опыта. Ожидаемой
    зарплаты нет и здесь."""

    full_name: str
    contact_email: str
    contact_phone: str | None
    telegram: str | None = Field(description="Имя пользователя без «@»")
    about: str
    job_roles: list[str]
    soft_skills: list[str]
    experience: list[ExperienceEntryOut] = Field(description=f"Карточка опыта. {FROM_CANDIDATE}")
    technology_years: list[TechnologyYearsOut] = Field(
        description=f"Годы по технологиям из записей опыта. {FROM_CANDIDATE}"
    )


class CandidateCardOut(BaseModel):
    """Карточка кандидата для работодателя. До принятия приглашения — обезличенная: решение по
    навыкам, без ФИО, контактов, свободного текста («о себе», роли, софт-скиллы) и ожидаемой
    зарплаты; фото, возраст и вуз платформа не собирает. Ожидаемой зарплаты нет и после."""

    id: uuid.UUID
    category: CategoryOut | None = Field(
        description="Категория по тесту; `null` — тест не пройден, грейд только заявлен"
    )
    grade_status: GradeStatusOut
    skill_profile: SkillProfileOut | None = Field(description="Профиль навыков специализации")
    self_reported: CardSelfReportedOut | None = Field(
        description="Самоописание без скрытого кандидатом; `null` — кандидат ещё не заполнил "
        "профиль"
    )
    fsp_achievements: list[FspAnonymizedAchievementOut] = Field(
        description="Достижения ФСП — подтверждены, отдельно от самоописания: тип результата, "
        "дисциплина и год. Пусто — нет истории ФСП, это не штраф"
    )
    disclosed: DisclosedOut | None = Field(
        description="ФИО, контакты, свободный текст и карточка опыта — только после принятия "
        "приглашения вашей компании; `null` — карточка обезличена или профиль не заполнен"
    )
    fsp_details: list[FspAchievementOut] | None = Field(
        description="Достижения ФСП полностью — с мероприятием, местом и ролью в команде: только "
        "после принятия приглашения вашей компании; `null` — карточка обезличена"
    )


class GradeHintOut(BaseModel):
    """Подсказка грейда по стажу и ролям. Только подсказка: грейд выбирает кандидат, категорию
    определяет тест."""

    grade: CatalogRef = Field(description="Младший из грейдов по стажу и по ролям")
    by_experience: CatalogRef | None = Field(description="Грейд по стажу; `null` — стажа нет")
    by_roles: CatalogRef | None = Field(description="Грейд, названный в ролях; `null` — не назван")


class ResumeDraftOut(BaseModel):
    """Черновик анкеты «система поняла так» из резюме. Ничего не сохранено: кандидат правит
    поля и сохраняет профиль (`PUT /api/candidate/profile`). Ожиданий — формата, города,
    зарплаты — в черновике нет: их кандидат указывает сам."""

    full_name: str | None
    contact_email: str | None
    contact_phone: str | None
    telegram: str | None = Field(description="Имя пользователя без «@»")
    stack: list[CatalogRef] = Field(description="Только технологии справочника, в его порядке")
    job_roles: list[str] = Field(description="Названия ролей из словаря, а не фразы резюме")
    experience_years: int | None = Field(description="Полных лет; `null` — не найден")
    soft_skills: list[str] = Field(description="Названия из словаря, а не фразы резюме")
    experience: list[ExperienceEntryOut] = Field(
        description="Черновые записи опыта: периоды из раздела опыта, технологии справочника из "
        "текста записи, роль из словаря, место — заголовок записи; «что делал» пусто. Всегда "
        "неуверенные — проверьте их"
    )
    confidence: dict[ResumeField, float | None] = Field(
        description="Уверенность по распознанным полям в [0, 1]; `null` — разбор её не считает. "
        "Нераспознанных полей здесь нет"
    )
    uncertain: list[ResumeField] = Field(
        description="Распознанные поля с уверенностью ниже `resume_draft_confident` — проверьте их"
    )
    grade_hint: GradeHintOut | None = Field(
        description="Подсказка грейда по стажу и ролям черновика — для шага выбора грейда"
    )
