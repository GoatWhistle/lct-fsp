"""Чат-поиск кандидатов: работодатель пишет как есть, агент вызывает сценарии подбора и
пересказывает результат. Список кандидатов — вывод сценариев, а не слова модели."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.controller.deps import ROLE_RESPONSES, CurrentUser, SearchChatDep, role_guard
from app.controller.errors import error_responses
from app.domain import errors
from app.domain.account import Role

router = APIRouter(
    prefix="/api/employer/chat",
    tags=["employer-chat"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    selection_id: uuid.UUID | None = Field(
        default=None,
        description="Подборка, начатая раньше в чате или в форме: сообщение без текста вакансии "
        "уточняет её фильтрами",
    )


class ChipOut(BaseModel):
    kind: str = Field(description="`stack`, `fsp`, `confident`, `grade` или `specialization`")
    value: str


class CardOut(BaseModel):
    candidate_id: uuid.UUID
    position: int
    block: str
    grade: str
    match_score: float | None


class ChatOut(BaseModel):
    selection_id: uuid.UUID = Field(description="Подборка открывается в форме по этому id")
    cards: list[CardOut] = Field(description="Ровно вывод подборки и фильтров, в их порядке")
    chips: list[ChipOut] = Field(description="Сужения, которые сделал агент, — снимаются")
    summary: str | None = Field(
        description="Пересказ; `null` — числа не прошли сверку с выводом, показывается таблица"
    )
    total: int


@router.get("/status", summary="Доступен ли чат")
def status(chat: SearchChatDep) -> dict[str, bool]:
    return {"available": chat.available}


@router.post(
    "",
    summary="Сообщение чат-поиска",
    description="Агент разбирает текст, строит подборку и применяет фильтры теми же сценариями, "
    "что форма; кандидатов не переставляет и не добавляет. Модели нет — 503, работает путь руками.",
    responses=error_responses(errors.ChatUnavailable, errors.StepUnavailable),
)
def send(body: ChatIn, user: CurrentUser, chat: SearchChatDep) -> ChatOut:
    reply = chat.send(user.id, body.message, body.selection_id)
    return ChatOut(
        selection_id=uuid.UUID(reply.selection_id),
        cards=[
            CardOut(
                candidate_id=uuid.UUID(c.candidate_id),
                position=c.position,
                block=c.block,
                grade=c.grade,
                match_score=c.match_score,
            )
            for c in reply.cards
        ],
        chips=[ChipOut(kind=c.kind, value=c.value) for c in reply.chips],
        summary=reply.summary,
        total=reply.total,
    )
