from datetime import timedelta

from fastapi import APIRouter, Response, status

from app.config import SettingsDep
from app.controller.deps import ClockDep, MailerDep
from app.controller.errors import error_responses
from app.db import DbSession
from app.domain import errors
from app.identity import service
from app.identity.deps import ACCESS_COOKIE, AUTH_RESPONSES, CurrentUser
from app.identity.schemas import (
    LoginIn,
    RegisterIn,
    ResendVerificationIn,
    UserOut,
    VerifyEmailIn,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по email и паролю",
    description="Создаёт учётку выбранной роли и отправляет письмо со ссылкой подтверждения. "
    "Войти можно только после подтверждения адреса.",
    responses=error_responses(errors.EmailTaken),
)
def register(
    body: RegisterIn,
    db: DbSession,
    mailer: MailerDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> UserOut:
    user = service.register(
        db, mailer, settings, clock, email=body.email, password=body.password, role=body.role
    )
    return UserOut.model_validate(user)


@router.post(
    "/verify-email",
    summary="Подтверждение адреса по токену из письма",
    responses=error_responses(errors.TokenInvalid, errors.TokenExpired),
)
def verify_email(body: VerifyEmailIn, db: DbSession, clock: ClockDep) -> UserOut:
    return UserOut.model_validate(service.verify_email(db, clock, token=body.token))


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Повторное письмо подтверждения",
    description="Отвечает одинаково для любого адреса, чтобы не раскрывать, кто "
    "зарегистрирован. Письмо уходит, только если адрес зарегистрирован и не подтверждён.",
)
def resend_verification(
    body: ResendVerificationIn,
    db: DbSession,
    mailer: MailerDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> None:
    service.resend_verification(db, mailer, settings, clock, email=body.email)


@router.post(
    "/login",
    summary="Вход",
    description=f"Ставит httpOnly-cookie `{ACCESS_COOKIE}`; срок — настройка `SESSION_TTL_HOURS`.",
    responses=error_responses(errors.InvalidCredentials, errors.EmailNotVerified),
)
def login(
    body: LoginIn,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
    clock: ClockDep,
) -> UserOut:
    user = service.authenticate(db, email=body.email, password=body.password)
    response.set_cookie(
        ACCESS_COOKIE,
        service.issue_session(user, settings, clock),
        max_age=int(timedelta(hours=settings.session_ttl_hours).total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Выход")
def logout(response: Response, settings: SettingsDep) -> None:
    response.delete_cookie(
        ACCESS_COOKIE, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


@router.get("/me", summary="Текущий пользователь", responses=AUTH_RESPONSES)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
