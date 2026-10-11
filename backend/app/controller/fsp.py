"""ФСП ID: вход и привязка через ФСП ID, блок «ФСП ID» в профиле кандидата.

Правил здесь нет: контроллер вызывает сценарии `app.usecase.fsp`, держит начатый вход в
короткоживущей httpOnly-cookie и возвращает браузер на фронт. Ошибка после ухода в ФСП ID приходит
на фронт кодом в адресе — `fsp_error`, текст для кода — на фронте.
"""

import base64
import binascii
import json
import uuid
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Query, Response, status
from fastapi.responses import RedirectResponse

from app.controller.auth import set_session_cookie
from app.controller.deps import (
    AUTH_RESPONSES,
    ROLE_RESPONSES,
    CurrentUser,
    FrontendUrlDep,
    FspAccountsDep,
    OptionalUser,
    SessionCookieDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.fsp_schemas import (
    FspAchievementOut,
    FspAuthorizeIn,
    FspAuthorizeOut,
    FspDivergenceOut,
    FspStatusOut,
)
from app.domain import errors
from app.domain.account import Role
from app.domain.fsp import FspAuthorization, FspIntent
from app.usecase.fsp import FspStatus

# Начатый вход через ФСП ID: живёт, пока пользователь вводит пароль в ФСП ID.
AUTHORIZATION_COOKIE = "calibr_fsp_authorization"
AUTHORIZATION_COOKIE_PATH = "/api/auth/fsp"
AUTHORIZATION_TTL_SECONDS = 600

# Куда фронт ждёт браузер после ФСП ID.
AFTER_LOGIN = "/"
AFTER_LINK = "/candidate/profile"
LOGIN_PAGE = "/login"

router = APIRouter(prefix="/api/auth/fsp", tags=["auth"])

candidate_router = APIRouter(
    prefix="/api/candidate/fsp",
    tags=["candidate-fsp"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


@router.post(
    "/authorize",
    summary="Начать вход или привязку через ФСП ID",
    description=f"Ставит httpOnly-cookie `{AUTHORIZATION_COOKIE}` с начатым входом на "
    f"{AUTHORIZATION_TTL_SECONDS // 60} минут и отдаёт адрес страницы ФСП ID. После входа ФСП "
    "ID возвращает браузер на `GET /api/auth/fsp/callback`.",
    responses=error_responses(errors.FspIdUnavailable, errors.NotAuthenticated, errors.WrongRole),
)
def authorize(
    body: FspAuthorizeIn,
    response: Response,
    user: OptionalUser,
    fsp: FspAccountsDep,
    cookie: SessionCookieDep,
) -> FspAuthorizeOut:
    started = fsp.start(body.intent, user)
    response.set_cookie(
        AUTHORIZATION_COOKIE,
        _encode(started.authorization),
        max_age=AUTHORIZATION_TTL_SECONDS,
        path=AUTHORIZATION_COOKIE_PATH,
        httponly=True,
        secure=cookie.secure,
        samesite="lax",
    )
    return FspAuthorizeOut(authorization_url=started.url)


@router.get(
    "/callback",
    summary="Возврат из ФСП ID",
    description="Сюда ФСП ID возвращает браузер. Вход — ставит cookie входа и ведёт в кабинет; "
    f"привязка — ведёт в профиль кандидата `{AFTER_LINK}`. Ошибка — на страницу входа или в "
    "профиль с кодом в `fsp_error`.",
    status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse,
)
def callback(
    user: OptionalUser,
    fsp: FspAccountsDep,
    cookie: SessionCookieDep,
    frontend_url: FrontendUrlDep,
    # Без ограничений длины: любой ответ ФСП ID ведёт браузер на фронт, а не в ошибку API.
    state: Annotated[str | None, Query()] = None,
    code: Annotated[str | None, Query()] = None,
    started: Annotated[str | None, Cookie(alias=AUTHORIZATION_COOKIE)] = None,
) -> RedirectResponse:
    authorization = _decode(started)
    intent = authorization.intent if authorization else FspIntent.login
    page = AFTER_LINK if intent == FspIntent.link else LOGIN_PAGE
    try:
        signed_in = fsp.complete(authorization, state=state, code=code, user=user)
    except errors.DomainError as error:
        response = _redirect(frontend_url, page, {"fsp_error": error.code})
    else:
        if signed_in is None:
            response = _redirect(frontend_url, AFTER_LINK, {"fsp": "linked"})
        else:
            response = _redirect(frontend_url, AFTER_LOGIN)
            set_session_cookie(response, signed_in.session_token, cookie)
    response.delete_cookie(
        AUTHORIZATION_COOKIE,
        path=AUTHORIZATION_COOKIE_PATH,
        httponly=True,
        secure=cookie.secure,
        samesite="lax",
    )
    return response


@candidate_router.get(
    "",
    summary="ФСП ID кандидата",
    description="Привязка, подтверждённые достижения с датой снимка и расхождения ФСП и теста.",
    responses=AUTH_RESPONSES,
)
def get_status(user: CurrentUser, fsp: FspAccountsDep) -> FspStatusOut:
    return _status_out(fsp.status(user))


@candidate_router.post(
    "/refresh",
    summary="Обновить достижения из реестра ФСП",
    description="Новый снимок достижений и пересчёт профиля навыков. Реестр недоступен — "
    "остаётся прошлый снимок.",
    responses=error_responses(errors.FspNotLinked, errors.FspRegistryUnavailable),
)
def refresh(user: CurrentUser, fsp: FspAccountsDep) -> FspStatusOut:
    return _status_out(fsp.refresh(user))


@candidate_router.delete(
    "",
    summary="Отвязать ФСП ID",
    description="Достижения и их вклад в профиль навыков уходят, ФСП ID освобождается. Учётке, "
    "созданной через ФСП ID, отвязать нельзя: она входит только через него.",
    responses=error_responses(errors.FspNotLinked, errors.FspUnlinkForbidden),
)
def unlink(user: CurrentUser, fsp: FspAccountsDep) -> FspStatusOut:
    return _status_out(fsp.unlink(user))


def _status_out(found: FspStatus) -> FspStatusOut:
    history = found.history
    return FspStatusOut(
        linked=found.fsp_id is not None,
        fsp_id=found.fsp_id,
        can_unlink=found.can_unlink,
        fetched_at=history.fetched_at if history else None,
        achievements=[
            FspAchievementOut.model_validate(a) for a in (history.achievements if history else ())
        ],
        divergences=[FspDivergenceOut.model_validate(d) for d in found.divergences],
    )


def _redirect(
    frontend_url: str, page: str, query: dict[str, str] | None = None
) -> RedirectResponse:
    url = f"{frontend_url.rstrip('/')}{page}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def _encode(authorization: FspAuthorization) -> str:
    data = {
        "state": authorization.state,
        "code_verifier": authorization.code_verifier,
        "nonce": authorization.nonce,
        "intent": authorization.intent.value,
        "user_id": str(authorization.user_id) if authorization.user_id else None,
    }
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _decode(value: str | None) -> FspAuthorization | None:
    """Начатый вход из cookie; нет её или она испорчена — `None`: сценарий откажет."""
    if not value:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode()))
        return FspAuthorization(
            state=str(data["state"]),
            code_verifier=str(data["code_verifier"]),
            nonce=str(data["nonce"]),
            intent=FspIntent(data["intent"]),
            user_id=uuid.UUID(data["user_id"]) if data.get("user_id") else None,
        )
    except (binascii.Error, ValueError, KeyError, TypeError):
        return None
