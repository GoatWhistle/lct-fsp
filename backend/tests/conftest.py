"""Тесты ходят в бэкенд через HTTP API и пишут во временную PostgreSQL.

Сервер PostgreSQL — `TEST_DATABASE_URL` (любая база на нём, нужны права на CREATE DATABASE)
или контейнер testcontainers. На сервере создаётся своя база на прогон и удаляется после.
Часовой пояс у неё не UTC — так набор ловит время, которое зависит от настроек базы.
"""

import os
import re
import uuid
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.assessment.catalog import load_catalog, sync_catalog
from app.config import BACKEND_DIR, Mechanics, Settings
from app.db import create_db_engine
from app.identity.models import Role
from app.mail import Mail
from app.main import create_app

PASSWORD = "correct-horse-battery"
DATABASE_TIMEZONE = "Europe/Moscow"


class Outbox:
    """Почта, которая никуда не уходит: тест читает письма отсюда."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)

    def last_to(self, email: str) -> Mail:
        mails = [m for m in self.sent if m.to == email]
        assert mails, f"писем на {email} нет"
        return mails[-1]

    def verification_token(self, email: str) -> str:
        match = re.search(r"/verify-email\?token=(\S+)", self.last_to(email).text)
        assert match, "в письме нет ссылки подтверждения"
        return match.group(1)


@pytest.fixture(scope="session")
def postgres_server_url() -> Iterator[str]:
    if url := os.environ.get("TEST_DATABASE_URL"):
        yield url
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def database_url(postgres_server_url: str) -> Iterator[str]:
    name = f"test_{uuid.uuid4().hex[:12]}"
    admin = create_db_engine(postgres_server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
        conn.execute(text(f"ALTER DATABASE \"{name}\" SET timezone TO '{DATABASE_TIMEZONE}'"))
    url = make_url(postgres_server_url).set(database=name).render_as_string(hide_password=False)

    alembic_cfg = Config(BACKEND_DIR / "alembic.ini")
    alembic_cfg.attributes["database_url"] = url
    alembic_cfg.attributes["configure_logger"] = False
    command.upgrade(alembic_cfg, "head")
    engine = create_db_engine(url)
    with Session(engine) as db:
        sync_catalog(db, load_catalog())
        db.commit()
    engine.dispose()

    yield url

    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db_engine(database_url: str) -> Iterator[Engine]:
    engine = create_db_engine(database_url)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, family_calibrations, scale_links CASCADE"))
    engine.dispose()


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        secret_key="test-secret-key-at-least-32-bytes-long",
        frontend_url="http://front.test",
    )


@pytest.fixture
def mechanics(settings: Settings) -> Mechanics:
    return Mechanics.from_yaml(settings.mechanics_file)


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


@pytest.fixture
def app(
    db_engine: Engine, settings: Settings, mechanics: Mechanics, outbox: Outbox
) -> Iterator[FastAPI]:
    app = create_app(settings, mechanics, outbox)
    yield app
    app.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def new_client(app: FastAPI) -> Iterator[Callable[[], TestClient]]:
    """Отдельный клиент со своими cookie — второй пользователь в том же тесте."""
    clients: list[TestClient] = []

    def make() -> TestClient:
        c = TestClient(app)
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.close()


@pytest.fixture
def signed_in(new_client: Callable[[], TestClient], outbox: Outbox) -> Callable[[Role], TestClient]:
    """Клиент пользователя роли `role`, прошедшего регистрацию, подтверждение и вход."""

    def sign_in(role: Role) -> TestClient:
        c = new_client()
        email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
        c.post("/api/auth/register", json={"email": email, "password": PASSWORD, "role": role})
        token = outbox.verification_token(email)
        c.post("/api/auth/verify-email", json={"token": token}).raise_for_status()
        c.post("/api/auth/login", json={"email": email, "password": PASSWORD}).raise_for_status()
        return c

    return sign_in
