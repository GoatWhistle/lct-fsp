"""Cookie входа: своё имя, изоляция от чужих приложений на localhost, выход, перезагрузка, срок
и вход через ФСП ID (api.md, «Вход»)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.adapter.fsp_id import MemoryFspId
from app.adapter.password import Argon2Passwords
from app.domain.account import Role
from main import create_app
from settings import Mechanics, Settings
from tests.conftest import PASSWORD, Outbox
from tests.test_fsp import identity, via_fsp_id

NAME = "calibr_session"
FOREIGN = "access_token"


def set_cookie_headers(response: Any) -> list[str]:
    headers: list[str] = response.headers.get_list("set-cookie")
    return headers


def sign_up(client: TestClient, outbox: Outbox, email: str = "sess@example.com") -> str:
    body = {"email": email, "password": PASSWORD, "role": "candidate"}
    client.post("/api/auth/register", json=body)
    client.post("/api/auth/verify-email", json={"token": outbox.verification_token(email)})
    return email


def test_default_cookie_name_is_project_specific() -> None:
    assert Settings(_env_file=None).session_cookie_name == NAME
    assert NAME != FOREIGN


def test_login_sets_only_the_project_cookie(client: TestClient, outbox: Outbox) -> None:
    email = sign_up(client, outbox)

    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})

    cookies = set_cookie_headers(response)
    assert len(cookies) == 1
    assert cookies[0].startswith(f"{NAME}=")
    assert client.get("/api/auth/me").status_code == 200


def test_foreign_cookie_with_same_token_does_not_sign_in(
    signed_in: Callable[[Role], TestClient], new_client: Callable[[], TestClient]
) -> None:
    token = signed_in(Role.candidate).cookies[NAME]
    other = new_client()

    other.cookies.set(FOREIGN, token)

    assert other.get("/api/auth/me").status_code == 401


def test_foreign_app_cookie_does_not_break_session(
    signed_in: Callable[[Role], TestClient],
) -> None:
    """Чужое приложение на другом порту того же localhost пишет свой `access_token`."""
    client = signed_in(Role.candidate)

    client.cookies.set(FOREIGN, "token-of-another-app")

    assert client.get("/api/auth/me").status_code == 200


def test_logout_deletes_cookie_with_the_same_attributes(
    signed_in: Callable[[Role], TestClient],
) -> None:
    client = signed_in(Role.candidate)

    response = client.post("/api/auth/logout")

    [deleted] = set_cookie_headers(response)
    lowered = deleted.lower()
    assert deleted.startswith(f"{NAME}=")
    assert "max-age=0" in lowered
    assert "path=/" in lowered
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert client.get("/api/auth/me").status_code == 401
    assert NAME not in client.cookies


def test_page_reload_keeps_session(
    signed_in: Callable[[Role], TestClient], new_client: Callable[[], TestClient]
) -> None:
    """Перезагрузка страницы — новый запрос с той же cookie."""
    first = signed_in(Role.candidate)
    reloaded = new_client()
    reloaded.cookies.set(NAME, first.cookies[NAME])

    assert reloaded.get("/api/auth/me").json() == first.get("/api/auth/me").json()


def test_cookie_max_age_is_session_ttl(
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    passwords: Argon2Passwords,
) -> None:
    """Без Max-Age браузер сбросил бы cookie при закрытии вкладки."""
    configured = settings.model_copy(update={"session_ttl_hours": 3})
    app = create_app(configured, mechanics, outbox, passwords=passwords)
    with TestClient(app) as client:
        email = sign_up(client, outbox)
        response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    app.state.engine.dispose()

    assert f"Max-Age={3 * 3600}" in set_cookie_headers(response)[0]


@pytest.fixture
def renamed(
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    clock: FrozenClock,
    passwords: Argon2Passwords,
) -> Iterator[TestClient]:
    configured = settings.model_copy(
        update={"session_cookie_name": "other_sid", "session_ttl_hours": 2}
    )
    app = create_app(configured, mechanics, outbox, clock=clock, passwords=passwords)
    with TestClient(app) as client:
        yield client
    app.state.engine.dispose()


def test_cookie_name_comes_from_settings(renamed: TestClient, outbox: Outbox) -> None:
    email = sign_up(renamed, outbox)

    response = renamed.post("/api/auth/login", json={"email": email, "password": PASSWORD})

    assert set_cookie_headers(response)[0].startswith("other_sid=")
    assert renamed.get("/api/auth/me").status_code == 200
    token = renamed.cookies["other_sid"]
    renamed.cookies.clear()
    renamed.cookies.set(NAME, token)
    assert renamed.get("/api/auth/me").status_code == 401, "под именем по умолчанию не читается"


def test_renamed_session_expires_by_configured_ttl_and_logout_uses_its_name(
    renamed: TestClient, outbox: Outbox, clock: FrozenClock
) -> None:
    email = sign_up(renamed, outbox)
    renamed.post("/api/auth/login", json={"email": email, "password": PASSWORD})

    clock.shift(timedelta(hours=2) - timedelta(seconds=1))
    assert renamed.get("/api/auth/me").status_code == 200
    clock.shift(timedelta(seconds=1))
    assert renamed.get("/api/auth/me").status_code == 401

    [deleted] = set_cookie_headers(renamed.post("/api/auth/logout"))
    assert deleted.startswith("other_sid=")


def test_fsp_id_login_sets_the_project_cookie(client: TestClient, fsp_id: MemoryFspId) -> None:
    via_fsp_id(client, fsp_id, identity())

    assert NAME in client.cookies
    assert FOREIGN not in client.cookies
    assert client.get("/api/auth/me").status_code == 200


def test_fsp_id_start_cookie_is_project_specific_and_cleared_after_return(
    client: TestClient, fsp_id: MemoryFspId
) -> None:
    started = client.post("/api/auth/fsp/authorize", json={"intent": "login"})
    assert any(h.startswith("calibr_fsp_authorization=") for h in set_cookie_headers(started))

    via_fsp_id(client, fsp_id, identity())

    assert "calibr_fsp_authorization" not in client.cookies


def test_openapi_documents_cookie_scheme_by_default_name(client: TestClient) -> None:
    scheme = client.get("/api/openapi.json").json()["components"]["securitySchemes"]["session"]

    assert (scheme["type"], scheme["in"], scheme["name"]) == ("apiKey", "cookie", NAME)


@pytest.mark.parametrize("bad", ["", "with space", "a;b", "x" * 65])
def test_invalid_cookie_name_is_rejected_at_startup(bad: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_cookie_name=bad)
