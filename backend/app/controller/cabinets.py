"""Кабинеты ролей: кто вошёл и сколько непрочитанных сообщений во всех переписках."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.controller.auth_schemas import UserOut
from app.controller.deps import ROLE_RESPONSES, ConversationsDep, CurrentUser, role_guard
from app.domain.account import Account, Role
from app.domain.conversation import Side
from app.usecase.conversation import Conversations

candidate_router = APIRouter(
    prefix="/api/candidate",
    tags=["candidate"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)
employer_router = APIRouter(
    prefix="/api/employer",
    tags=["employer"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)


class CabinetOut(BaseModel):
    user: UserOut
    unread_messages: int = Field(
        description="Непрочитанные сообщения другой стороны во всех переписках; почты нет — "
        "счётчик обновляется при запросе"
    )


@candidate_router.get("/cabinet", summary="Кабинет кандидата")
def candidate_cabinet(user: CurrentUser, conversations: ConversationsDep) -> CabinetOut:
    return _cabinet(user, Side.candidate, conversations)


@employer_router.get("/cabinet", summary="Кабинет работодателя")
def employer_cabinet(user: CurrentUser, conversations: ConversationsDep) -> CabinetOut:
    return _cabinet(user, Side.employer, conversations)


def _cabinet(user: Account, side: Side, conversations: Conversations) -> CabinetOut:
    unread = conversations.unread(side, user.id)
    return CabinetOut(user=UserOut.model_validate(user), unread_messages=sum(unread.values()))
