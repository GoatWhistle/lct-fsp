"""Схемы API потребности."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.assessment.schemas import CatalogRef
from app.matching.importance import TopicImportance
from app.matching.models import WorkFormat

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Salary = Annotated[int, Field(le=1_000_000_000, description="Рубли в месяц")]


class TopicImportanceIn(BaseModel):
    specialization: str = Field(description="Код специализации из `/api/catalog/specializations`")
    stack: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Коды технологий из `/api/catalog/technologies` — любые из справочника",
    )
    topic_importance: dict[str, TopicImportance] = Field(
        default_factory=dict,
        description="Правки важности: код темы специализации → важность. Темы без правки получают "
        "важность из стека",
    )


class NeedIn(TopicImportanceIn):
    title: Title = Field(description="Кого ищете")
    team_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = (
        Field(default="", description="Чем занимается команда")
    )
    grade: str = Field(description="Код грейда из `/api/catalog/grades`")
    work_format: WorkFormat
    city: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = Field(
        default=None, description="Обязателен для офиса и гибрида"
    )
    salary_from: Salary | None = Field(
        default=None,
        description="Вилка необязательна; если указана — обе границы больше нуля, «от» не "
        "больше «до»",
    )
    salary_to: Salary | None = None


class TopicImportanceOut(BaseModel):
    topic: CatalogRef
    importance: TopicImportance = Field(
        description="`key` — ключевая, `important` — важная, `nice` — желательная"
    )
    edited: bool = Field(description="Важность поставил работодатель, а не вывод из стека")
    technologies: list[CatalogRef] = Field(description="Технологии стека, связанные с темой")


class NeedOut(BaseModel):
    id: uuid.UUID
    title: str
    team_description: str
    specialization: CatalogRef
    grade: CatalogRef
    stack: list[CatalogRef] = Field(description="По названию технологии")
    work_format: WorkFormat
    city: str | None
    salary_from: int | None
    salary_to: int | None
    topics: list[TopicImportanceOut] = Field(description="Все темы специализации по порядку")
    created_at: datetime
    updated_at: datetime
