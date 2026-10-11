"""Учётка: регистрация, подтверждение адреса, вход и выход. Правил здесь нет: контроллер вызывает
сценарии `app.usecase.account` и ставит или снимает cookie входа."""

from fastapi import APIRouter, Response, status

from app.controller.auth_schemas import (
    LoginIn,
    RegisterIn,
    ResendVerificationIn,
    UserOut,
    VerifyEmailIn,
)
from app.controller.deps import (
    AUTH_RESPONSES,
    DEFAULT_SESSION_COOKIE,
    AccountsDep,
    CurrentUser,
    SessionCookie,
    SessionCookieDep,
)
from app.controller.errors import error_responses
from app.domain import errors

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по email и паролю",
    description="Создаёт учётку выбранной роли и отправляет письмо со ссылкой подтверждения. "
    "Войти можно только после подтверждения адреса.",
    responses=error_responses(errors.EmailTaken),
)
def register(body: RegisterIn, accounts: AccountsDep) -> UserOut:
    account = accounts.register(body.email, body.password, body.role, body.locale)
    return UserOut.model_validate(account)


@router.post(
    "/verify-email",
    summary="Подтверждение адреса по токену из письма",
    responses=error_responses(errors.TokenInvalid, errors.TokenExpired),
)
def verify_email(body: VerifyEmailIn, accounts: AccountsDep) -> UserOut:
    return UserOut.model_validate(accounts.verify_email(body.token))


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Повторное письмо подтверждения",
    description="Отвечает одинаково для любого адреса, чтобы не раскрывать, кто "
    "зарегистрирован. Письмо уходит, только если адрес зарегистрирован и не подтверждён.",
)
def resend_verification(body: ResendVerificationIn, accounts: AccountsDep) -> None:
    accounts.resend_verification(body.email, body.locale)


@router.post(
    "/login",
    summary="Вход",
    description=(
        f"Ставит httpOnly-cookie `{DEFAULT_SESSION_COOKIE}` (имя — настройка "
        "`SESSION_COOKIE_NAME`); срок — настройка `SESSION_TTL_HOURS`."
    ),
    responses=error_responses(errors.InvalidCredentials, errors.EmailNotVerified),
)
def login(
    body: LoginIn, response: Response, accounts: AccountsDep, cookie: SessionCookieDep
) -> UserOut:
    signed_in = accounts.sign_in(body.email, body.password)
    set_session_cookie(response, signed_in.session_token, cookie)
    return UserOut.model_validate(signed_in.account)


def set_session_cookie(response: Response, token: str, cookie: SessionCookie) -> None:
    """Cookie входа — одна для входа по email и через ФСП ID."""
    response.set_cookie(
        cookie.name,
        token,
        max_age=cookie.max_age,
        httponly=True,
        secure=cookie.secure,
        samesite="lax",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Выход")
def logout(response: Response, cookie: SessionCookieDep) -> None:
    response.delete_cookie(cookie.name, httponly=True, secure=cookie.secure, samesite="lax")


@router.get("/me", summary="Текущий пользователь", responses=AUTH_RESPONSES)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
