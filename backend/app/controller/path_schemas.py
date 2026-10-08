"""Схемы API пути кандидата. Эталоны, верность ответов и параметры экземпляров сюда не входят:
они живут только на бэкенде."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.controller.schemas import CatalogRef
from app.domain import candidate
from app.domain.attempt import Stage
from app.domain.bank import AnswerFormat
from app.domain.candidate import Level


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SurveyIn(BaseModel):
    specialization: str = Field(
        description="Направление — код специализации из `/api/catalog/specializations` с `has_test`"
    )


class AttemptIn(BaseModel):
    grade: str = Field(description="Код грейда: заявленный или предложенный для дотеста")


class AnswerIn(BaseModel):
    presentation_id: uuid.UUID = Field(description="`id` задания из `GET /api/candidate/path/item`")
    response: str = Field(min_length=1, max_length=500)


class SurveyOut(_Out):
    specialization: CatalogRef
    created_at: datetime


class LevelBandOut(BaseModel):
    """Уровень словами (mechanics.md, §4): `low == high` — «уверенно `low`», иначе «между `low`
    и `high`». `null` — ниже порога младшего грейда."""

    low: str | None
    high: str | None
    confident: bool


class LevelOut(BaseModel):
    theta: float = Field(description="Уровень θ, логиты шкалы")
    theta_sd: float = Field(description="Погрешность уровня")
    band: LevelBandOut


class GradeProbabilityOut(BaseModel):
    grade: str
    probability: float = Field(description="P(общий уровень ≥ порог грейда)")


class TestResultOut(BaseModel):
    """Оценка теста определения категории — по ней решается грейд."""

    grade: str = Field(description="Грейд последней попытки")
    overall: LevelOut = Field(description="Общий уровень по специализации")
    grade_probabilities: list[GradeProbabilityOut] = Field(description="От младшего грейда")
    grade_up_hint: str | None = Field(
        description="Грейд выше присвоенного, если стоит попробовать его пройти"
    )


class TopicLevelOut(BaseModel):
    topic: CatalogRef
    level: LevelOut


class SkillProfileOut(BaseModel):
    """Профиль навыков: уровень и погрешность по темам из всех сигналов — так его видит подбор."""

    overall: LevelOut
    topics: list[TopicLevelOut] = Field(description="В порядке тем справочника")
    updated_at: datetime


def level_view(level: Level) -> LevelOut:
    band = level.band
    return LevelOut(
        theta=level.theta,
        theta_sd=level.theta_sd,
        band=LevelBandOut(low=band.low, high=band.high, confident=band.confident),
    )


def skill_profile_view(profile: candidate.SkillProfile) -> SkillProfileOut:
    """Профиль навыков из доменной проекции — уровни словами уже посчитаны."""
    return SkillProfileOut(
        overall=level_view(profile.overall),
        topics=[
            TopicLevelOut(topic=CatalogRef.model_validate(t.topic), level=level_view(t.level))
            for t in profile.topics
        ],
        updated_at=profile.updated_at,
    )


class AttemptProgressOut(BaseModel):
    grade: str
    answered: int
    max_items: int = Field(
        description="Больше заданий попытка не задаст; обычно тест останавливается раньше — "
        "когда уровень определён с нужной точностью"
    )


class CategoryOut(_Out):
    specialization: CatalogRef
    grade: CatalogRef
    assigned_at: datetime


class PathOut(BaseModel):
    stage: Stage = Field(
        description="`survey` — опрос; `grade` — выбор грейда; `test` — идёт тест; `offer` — "
        "предложен дотест на `offer_grade`; `category` — категория присвоена; `no_category` — "
        "без категории до `retest_after`"
    )
    survey: SurveyOut | None
    attempt: AttemptProgressOut | None = Field(description="Ход теста на шаге `test`")
    offer_grade: str | None
    retest_after: datetime | None
    category: CategoryOut | None
    result: TestResultOut | None = Field(description="На шагах `offer`, `category`, `no_category`")
    profile: SkillProfileOut | None


class OptionOut(BaseModel):
    letter: str = Field(description="Буква варианта — её кандидат и отвечает")
    text: str


class ItemOut(BaseModel):
    id: uuid.UUID
    number: int = Field(description="Номер задания в попытке, с 1")
    max_items: int = Field(
        description="Лимит заданий попытки; длина адаптивного теста заранее неизвестна"
    )
    topic: CatalogRef
    prompt: str
    code: str | None = Field(description="Листинг, таблица или граф к условию — моноширинно")
    answer_format: AnswerFormat = Field(
        description="`value` — ответ вводится текстом; `choice` — буква одного варианта; "
        "`ordering` — буквы всех вариантов в верном порядке строкой, например «KBXF»"
    )
    options: list[OptionOut] = Field(
        description="Варианты по алфавиту букв; буквы и порядок текстов свои у каждого экземпляра"
    )
