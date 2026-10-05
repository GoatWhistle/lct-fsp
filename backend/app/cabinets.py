"""Кабинеты ролей. Пока пустые: разделы добавят профиль, подбор и рынок."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role
from app.identity.schemas import UserOut

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


@candidate_router.get("/cabinet", summary="Кабинет кандидата")
def candidate_cabinet(user: CurrentUser) -> CabinetOut:
    return CabinetOut(user=UserOut.model_validate(user))


@employer_router.get("/cabinet", summary="Кабинет работодателя")
def employer_cabinet(user: CurrentUser) -> CabinetOut:
    return CabinetOut(user=UserOut.model_validate(user))
