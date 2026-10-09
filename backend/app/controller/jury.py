"""Режим жюри: статус, вход демо-работодателем и свежий тестовый кандидат. Правил здесь нет:
контроллер вызывает сценарии `app.usecase.jury` и ставит cookie входа, как обычный вход.
Выключенный режим отвечает на входы 404 и ничего не создаёт."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.controller.auth import set_session_cookie
from app.controller.auth_schemas import UserOut
from app.controller.deps import JuryDep, SessionCookieDep
from app.controller.errors import error_responses
from app.domain import errors

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoStatusOut(BaseModel):
    enabled: bool = Field(description="Режим жюри включён настройкой окружения `DEMO_MODE`")


class DemoCandidateIn(BaseModel):
    specialization: str = Field(default="backend", description="Код специализации опроса")
    grade: str = Field(default="middle", description="Заявленный грейд экспресс-теста")


@router.get("/status", summary="Включён ли режим жюри")
def demo_status(jury: JuryDep) -> DemoStatusOut:
    return DemoStatusOut(enabled=jury.status().enabled)


@router.post(
    "/employer",
    summary="Войти демо-работодателем",
    description="Демо-компания с потребностями и подборками; учётка помечена и заводится при "
    "первом входе. Ставит cookie входа.",
    responses=error_responses(errors.DemoDisabled),
)
def demo_employer(response: Response, jury: JuryDep, cookie: SessionCookieDep) -> UserOut:
    signed_in = jury.employer()
    set_session_cookie(response, signed_in.session_token, cookie)
    return UserOut.model_validate(signed_in.account)


@router.post(
    "/candidate",
    status_code=status.HTTP_201_CREATED,
    summary="Новый тестовый кандидат",
    description="Свежая подтверждённая учётка с пройденным опросом и начатым экспресс-тестом; "
    "каждый вызов — новая, поэтому повторное прохождение не ждёт смены грейда. Ставит cookie "
    "входа.",
    responses=error_responses(
        errors.DemoDisabled,
        errors.UnknownSpecialization,
        errors.SpecializationWithoutTest,
        errors.UnknownGrade,
    ),
)
def demo_candidate(
    body: DemoCandidateIn, response: Response, jury: JuryDep, cookie: SessionCookieDep
) -> UserOut:
    signed_in = jury.candidate(body.specialization, body.grade)
    set_session_cookie(response, signed_in.session_token, cookie)
    return UserOut.model_validate(signed_in.account)
