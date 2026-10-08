"""Схемы API регулярных заданий."""

import enum
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.controller.schemas import CatalogRef
from app.domain.regular_task import (
    MAX_TOPICS,
    PROMPT_MAX,
    REFERENCE_MAX,
    RESPONSE_MAX,
    TaskKind,
)

Prompt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=PROMPT_MAX)
]
Response = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RESPONSE_MAX)
]

KIND = (
    "`reference` — с эталоном: короткий ответ строкой или числом проверяет система; `open` — "
    "открытое: ответ оценивает автор по рубрике 0–3"
)


class TaskIn(BaseModel):
    specialization: str = Field(description="Код специализации из `/api/catalog/specializations`")
    grade: str = Field(description="Код грейда из `/api/catalog/grades` — от него сложность")
    kind: TaskKind = Field(description=KIND)
    prompt: Prompt = Field(description="Условие задания")
    topics: list[str] = Field(
        max_length=10,
        description=f"Коды тем специализации задания — от 1 до {MAX_TOPICS}",
    )
    reference_answer: Annotated[str, StringConstraints(max_length=REFERENCE_MAX)] | None = Field(
        default=None,
        description="Эталон — только у задания с эталоном: строка или число, сравнивается с "
        "ответом после нормализации, как в тесте",
    )


class TaskOut(BaseModel):
    """Задание в кабинете автора — с эталоном."""

    id: uuid.UUID
    specialization: CatalogRef
    grade: CatalogRef
    kind: TaskKind = Field(description=KIND)
    prompt: str
    topics: list[CatalogRef]
    reference_answer: str | None
    answers: int = Field(description="Сколько кандидатов ответило")
    editable: bool = Field(description="Править можно, пока нет ответов и задание не снято")
    created_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None = Field(description="Снято из каталога; `null` — активно")


class CatalogTaskOut(BaseModel):
    """Задание в каталоге кандидата — без эталона и автора."""

    id: uuid.UUID
    grade: CatalogRef
    kind: TaskKind = Field(description=KIND)
    prompt: str
    topics: list[CatalogRef]
    answers: int = Field(description="Сколько кандидатов ответило")
    created_at: datetime
    answered: bool = Field(description="Кандидат уже ответил — второй ответ не принимается")


class TaskAnswerIn(BaseModel):
    response: Response = Field(description="Ответ: у задания с эталоном — строка или число")


class AnswerStatus(enum.StrEnum):
    accepted = "accepted"
    awaiting_review = "awaiting_review"
    reviewed = "reviewed"


class OwnAnswerOut(BaseModel):
    """Свой ответ кандидата. Вердикта и оценки нет: они уходят в профиль навыков."""

    task: CatalogTaskOut
    response: str
    answered_at: datetime
    status: AnswerStatus = Field(
        description="`accepted` — принят и учтён в профиле (задание с эталоном), "
        "`awaiting_review` — ждёт оценки автора, `reviewed` — оценён и учтён в профиле"
    )


class AuthorAnswerOut(BaseModel):
    """Ответ на задание для его автора — обезличенно: без ФИО, контактов и профиля."""

    id: uuid.UUID
    candidate: str = Field(description="Псевдоним кандидата — свой в каждом задании")
    response: str = Field(description="Текст ответа как есть")
    answered_at: datetime
    correct: bool | None = Field(description="Вердикт системы — у задания с эталоном")
    rubric: int | None = Field(description="Оценка по рубрике 0–3 — у открытого после оценки")
    graded_at: datetime | None


class GradeIn(BaseModel):
    rubric: int = Field(
        ge=0,
        le=3,
        description="0 — не решено или не по делу; 1 — частично, подход с ошибками; 2 — верно в "
        "целом; 3 — верно и хорошо: оптимально, с разбором краёв",
    )
