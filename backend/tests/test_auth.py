from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert, text

from app.adapter.clock import FrozenClock
from app.adapter.password import Argon2Passwords
from app.domain.account import Role
from app.repository.orm import User
from main import create_app
from settings import Mechanics, Settings
from tests.conftest import PASSWORD, Outbox


def register(client: TestClient, email: str, role: str = "candidate") -> dict[str, object]:
    response = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "role": role}
    )
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def login(client: TestClient, email: str, password: str = PASSWORD) -> TestClient:
    client.post("/api/auth/login", json={"email": email, "password": password})
    return client


def test_registration_sends_confirmation_link(client: TestClient, outbox: Outbox) -> None:
    user = register(client, "Anna@Example.com")

    assert user["email"] == "anna@example.com"
    assert user["role"] == "candidate"
    assert user["email_verified"] is False
    mail = outbox.last_to("anna@example.com")
    assert "http://front.test/verify-email?token=" in mail.text


def test_confirmed_user_signs_in_to_own_cabinet(client: TestClient, outbox: Outbox) -> None:
    register(client, "boris@example.com", role="employer")
    token = outbox.verification_token("boris@example.com")

    confirmed = client.post("/api/auth/verify-email", json={"token": token})
    assert confirmed.status_code == 200
    assert confirmed.json()["email_verified"] is True

    signed_in = client.post(
        "/api/auth/login", json={"email": "BORIS@example.com", "password": PASSWORD}
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["role"] == "employer"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "boris@example.com"

    cabinet = client.get("/api/employer/cabinet")
    assert cabinet.status_code == 200
    assert cabinet.json()["user"]["email"] == "boris@example.com"


def test_sign_in_before_confirmation_is_rejected(client: TestClient) -> None:
    register(client, "vera@example.com")

    response = client.post(
        "/api/auth/login", json={"email": "vera@example.com", "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"
    assert "не подтверждён" in response.json()["message"]
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_is_rejected_without_hinting_at_confirmation(client: TestClient) -> None:
    register(client, "gleb@example.com")

    for email, password in [
        ("gleb@example.com", "wrong-password"),
        ("nobody@example.com", PASSWORD),
    ]:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_credentials"


def test_email_is_registered_once_regardless_of_case(client: TestClient) -> None:
    register(client, "dina@example.com")

    response = client.post(
        "/api/auth/register",
        json={"email": "DINA@example.com", "password": PASSWORD, "role": "employer"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


class RacingClock(FrozenClock):
    """Между проверкой адреса и вставкой учётки — при первом чтении часов — тот же адрес
    регистрирует параллельный запрос."""

    def __init__(self, engine: Engine) -> None:
        super().__init__(datetime.now(UTC))
        self._engine = engine
        self._raced = False

    def now(self) -> datetime:
        if not self._raced:
            self._raced = True
            with self._engine.begin() as conn:
                conn.execute(
                    insert(User).values(
                        email="eva@example.com",
                        password_hash="x",
                        role=Role.employer,
                        created_at=datetime.now(UTC),
                    )
                )
        return super().now()


def test_concurrent_registration_of_same_email_is_rejected(
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    passwords: Argon2Passwords,
) -> None:
    """Адрес заняли параллельным запросом между проверкой и вставкой: ответ тот же, что при
    обычном повторе, письма нет."""
    app = create_app(settings, mechanics, outbox, clock=RacingClock(db_engine), passwords=passwords)
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={"email": "eva@example.com", "password": PASSWORD, "role": "candidate"},
        )

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"
    assert outbox.sent == []


def test_invalid_registration_data_is_rejected(client: TestClient) -> None:
    for body in [
        {"email": "egor@example.com", "password": "short", "role": "candidate"},
        {"email": "egor@example.com", "password": PASSWORD, "role": "admin"},
        {"email": "not-an-email", "password": PASSWORD, "role": "candidate"},
    ]:
        assert client.post("/api/auth/register", json=body).status_code == 422


def test_unknown_confirmation_token_is_rejected(client: TestClient) -> None:
    response = client.post("/api/auth/verify-email", json={"token": "made-up"})

    assert response.status_code == 400
    assert response.json()["code"] == "token_invalid"


def test_confirmation_link_expires(client: TestClient, outbox: Outbox, clock: FrozenClock) -> None:
    register(client, "zhanna@example.com")
    token = outbox.verification_token("zhanna@example.com")

    clock.shift(timedelta(hours=24))
    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 400
    assert response.json()["code"] == "token_expired"


def test_confirmation_link_works_once(client: TestClient, outbox: Outbox) -> None:
    register(client, "zoya@example.com")
    token = outbox.verification_token("zoya@example.com")
    client.post("/api/auth/verify-email", json={"token": token})

    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 400
    assert response.json()["code"] == "token_invalid"


def test_resent_link_confirms_address(client: TestClient, outbox: Outbox) -> None:
    register(client, "igor@example.com")

    response = client.post("/api/auth/resend-verification", json={"email": "IGOR@example.com"})
    assert response.status_code == 202
    assert len([m for m in outbox.sent if m.to == "igor@example.com"]) == 2

    token = outbox.verification_token("igor@example.com")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert login(client, "igor@example.com").get("/api/auth/me").status_code == 200


def test_resend_does_not_reveal_who_is_registered(client: TestClient, outbox: Outbox) -> None:
    response = client.post("/api/auth/resend-verification", json={"email": "ghost@example.com"})

    assert response.status_code == 202
    assert outbox.sent == []


def test_session_is_an_http_only_cookie_and_logout_clears_it(
    client: TestClient, outbox: Outbox
) -> None:
    register(client, "kira@example.com")
    client.post(
        "/api/auth/verify-email", json={"token": outbox.verification_token("kira@example.com")}
    )

    response = client.post(
        "/api/auth/login", json={"email": "kira@example.com", "password": PASSWORD}
    )

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("access_token=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert "access_token" not in response.text

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_session_expires(signed_in: Callable[[Role], TestClient], clock: FrozenClock) -> None:
    client = signed_in(Role.candidate)
    clock.shift(timedelta(days=7) - timedelta(seconds=1))
    assert client.get("/api/auth/me").status_code == 200, "срок входа ещё не вышел"

    clock.shift(timedelta(seconds=1))
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_session_survives_server_clock_stepping_back(
    signed_in: Callable[[Role], TestClient], clock: FrozenClock
) -> None:
    """Синхронизация часов отводит их назад на секунды — свежий вход не должен слетать."""
    client = signed_in(Role.candidate)

    clock.shift(timedelta(seconds=-5))
    response = client.get("/api/auth/me")

    assert response.status_code == 200


def test_forged_session_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.set("access_token", "not-a-token")

    assert client.get("/api/auth/me").status_code == 401


def test_password_is_stored_as_argon2_hash(client: TestClient, db_engine: Engine) -> None:
    register(client, "lev@example.com")

    with db_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT password_hash FROM users WHERE email = 'lev@example.com'")
        ).scalar_one()

    assert stored.startswith("$argon2")
    assert PASSWORD not in stored


def test_unknown_address_is_checked_against_a_decoy_hash() -> None:
    """Вход на неизвестный адрес тоже проверяет пароль по argon2 — и всегда неудачно, даже если
    пароль совпал с фиктивным."""
    passwords = Argon2Passwords()

    assert passwords.verify(None, PASSWORD) is False
    assert passwords.verify(passwords.hash(PASSWORD), PASSWORD) is True
    assert passwords.verify(passwords.hash(PASSWORD), "wrong-password") is False
