"""Схемы API пути кандидата. Эталоны, верность ответов и параметры экземпляров сюда не входят:
они живут только на бэкенде."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.assessment.service import Stage


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CatalogRef(_Out):
    code: str
    name: str


class SurveyIn(BaseModel):
    industry: str = Field(description="Код отрасли из `/api/catalog/industries`")
    specialization: str = Field(
        description="Код специализации из `/api/catalog/specializations` с `has_test`"
    )


class AttemptIn(BaseModel):
    grade: str = Field(description="Код грейда: заявленный или предложенный для дотеста")


class AnswerIn(BaseModel):
    presentation_id: uuid.UUID = Field(description="`id` задания из `GET /api/candidate/path/item`")
    response: str = Field(min_length=1, max_length=500)


class SurveyOut(_Out):
    industry: CatalogRef
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


class AttemptProgressOut(BaseModel):
    grade: str
    answered: int
    total: int


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


class ItemOut(BaseModel):
    id: uuid.UUID
    number: int = Field(description="Номер задания в попытке, с 1")
    total: int
    topic: CatalogRef
    prompt: str
    code: str | None = Field(description="Листинг, таблица или граф к условию — моноширинно")
    options: list[str] = Field(description="Варианты; пусто — ответ вводится текстом")
