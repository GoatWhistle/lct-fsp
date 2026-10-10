"""Схемы API теста по вакансии: план, превью с примерами заданий и итог для работодателя."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.controller.path_schemas import OptionOut
from app.controller.schemas import CatalogRef
from app.domain.bank import AnswerFormat
from app.domain.importance import TopicImportance
from app.usecase.vacancy_test import VacancyTestStatus


class PlannedTopicOut(BaseModel):
    topic: CatalogRef
    importance: TopicImportance
    weight: float = Field(
        description="Вес темы в тесте — вес важности, нормированный на темы теста"
    )
    items: int = Field(description="Сколько заданий по теме")


class VacancyTestPlanOut(BaseModel):
    specialization: CatalogRef
    grade: CatalogRef = Field(description="Грейд потребности: его порог — требуемый уровень")
    items: int = Field(description="Заданий в тесте — ровно столько")
    topics: list[PlannedTopicOut] = Field(
        description="Ключевые и важные темы потребности, без них — все темы специализации"
    )


class ExampleOut(BaseModel):
    topic: CatalogRef
    family_code: str
    prompt: str
    code: str | None
    answer_format: AnswerFormat
    options: list[OptionOut]


class VacancyTestPreviewOut(BaseModel):
    plan: VacancyTestPlanOut
    examples: list[ExampleOut] = Field(
        description="Пример задания на тему: семейство со сложностью ближе всех к требуемому "
        "уровню, экземпляр — со свежим seed, без эталона"
    )


class TopicOutcomeOut(BaseModel):
    topic: CatalogRef
    answered: int
    correct: int
    level: float = Field(description="Уровень θ по теме")
    level_sd: float = Field(description="Погрешность уровня")
    probability: float = Field(description="P(уровень ≥ требуемого)")


class VacancyTestResultOut(BaseModel):
    finished_at: datetime
    match: float = Field(description="Взвешенная доля выполненных требований по темам теста")
    topics: list[TopicOutcomeOut]


class VacancyTestOut(BaseModel):
    need_title: str
    plan: VacancyTestPlanOut
    status: VacancyTestStatus = Field(
        description="`not_started` — не начат; `in_progress` — идёт; `finished` — пройден"
    )
    answered: int
    result: VacancyTestResultOut | None = Field(
        description="Итог — только пригласившей компании; категорию и профиль он не меняет"
    )
