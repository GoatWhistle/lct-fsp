"""Кто делает запрос. Права проверяет только бэкенд — фронт лишь прячет кнопки.

Разделы одной роли — роутер с `dependencies=role_guard(Role.x)` и префиксом
`/api/candidate` или `/api/employer`; пользователь в эндпоинте — `CurrentUser`.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, params
from fastapi.security import APIKeyCookie

from app.config import SettingsDep
from app.db import DbSession
from app.errors import AppError, error_responses
from app.identity.models import Role, User
from app.identity.security import read_access_token

ACCESS_COOKIE = "access_token"

_cookie_scheme = APIKeyCookie(
    name=ACCESS_COOKIE,
    scheme_name="session",
    auto_error=False,
    description="httpOnly-cookie; ставит `POST /api/auth/login`, снимает `POST /api/auth/logout`",
)


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Войдите, чтобы продолжить"


class WrongRole(AppError):
    status_code = 403
    code = "wrong_role"
    message = "Раздел доступен другой роли"


def get_current_user(
    db: DbSession,
    settings: SettingsDep,
    access_token: Annotated[str | None, Depends(_cookie_scheme)],
) -> User:
    user_id = read_access_token(access_token, settings.secret_key) if access_token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise NotAuthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

AUTH_RESPONSES = error_responses(NotAuthenticated)


def require_role(role: Role) -> Callable[[User], User]:
    def check(user: CurrentUser) -> User:
        if user.role != role:
            raise WrongRole()
        return user

    return check


def role_guard(role: Role) -> list[params.Depends]:
    return [Depends(require_role(role))]


ROLE_RESPONSES: dict[int | str, dict[str, Any]] = error_responses(NotAuthenticated, WrongRole)
