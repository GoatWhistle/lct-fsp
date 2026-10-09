"""Три уровня тестов — маркеры `unit`, `integration`, `simulation`; `uv run pytest` гоняет
только `unit`, остальные — `-m integration`, `-m simulation`, весь набор — `-m ""`.

- `integration` — тест ходит в PostgreSQL: через HTTP API или в хранилище напрямую. Маркер
  ставится сам, если тесту нужна фикстура базы; вариант `postgres` параметризованной фикстуры,
  которая берёт базу через `getfixturevalue`, помечается в `pytest.param` — без маркера
  `db_engine` роняет тест.
- `simulation` — свойство механики на синтетике: сотни прогонов, долго и без базы. Ставится
  руками.
- `unit` — всё остальное, ставится само.

Сервер PostgreSQL — `TEST_DATABASE_URL` (любая база на нём, нужны права на CREATE DATABASE)
или контейнер testcontainers. На сервере создаётся своя база на прогон и удаляется после.
Часовой пояс у неё не UTC — так набор ловит время, которое зависит от настроек базы.
"""

import os
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher, profiles
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.adapter.clock import FrozenClock
from app.adapter.fsp_id import MemoryFspId
from app.adapter.fsp_registry import MemoryFspRegistry
from app.adapter.mail import MemoryMailer
from app.adapter.password import Argon2Passwords
from app.adapter.seed import DerivedSeeds
from app.domain.account import Role
from app.domain.mail import Mail
from app.repository.database import create_db_engine
from app.repository.unit_of_work import SqlUnitOfWork
from main import create_app, sync_catalog
from settings import BACKEND_DIR, Mechanics, Settings

PASSWORD = "correct-horse-battery"
DATABASE_TIMEZONE = "Europe/Moscow"


@contextmanager
def transaction(engine: Engine) -> Iterator[Session]:
    """Запись из теста в обход API — через единицу работы, как в приложении: блок фиксируется
    при выходе без исключения."""
    with closing(SqlUnitOfWork(Session(engine))) as uow, uow:
        yield uow.session


class Outbox(MemoryMailer):
    """Почта в памяти: тест читает письма отсюда."""

    def last_to(self, email: str) -> Mail:
        mails = [m for m in self.sent if m.to == email]
        assert mails, f"писем на {email} нет"
        return mails[-1]

    def verification_token(self, email: str) -> str:
        match = re.search(r"/verify-email\?token=(\S+)", self.last_to(email).text)
        assert match, "в письме нет ссылки подтверждения"
        return match.group(1)


class Seeds:
    """Seed механики в тестах: воспроизводимая последовательность от seed прогона. Выданные
    seed видны тесту — по ним он узнаёт экземпляр показанного задания, не читая базу."""

    def __init__(self, run_seed: int = 0) -> None:
        self.reset(run_seed)

    def reset(self, run_seed: int) -> None:
        """Последовательность заново: тот же `run_seed` повторит те же seed."""
        self._source = DerivedSeeds(run_seed)
        self.issued: list[int] = []

    def seed(self) -> int:
        value = self._source.seed()
        self.issued.append(value)
        return value


TIERS = ("unit", "integration", "simulation")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "postgres_server_url" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)
        tiers = [t for t in TIERS if item.get_closest_marker(t)]
        if len(tiers) > 1:
            raise pytest.UsageError(f"{item.nodeid}: сразу несколько уровней — {tiers}")
        if not tiers:
            item.add_marker(pytest.mark.unit)


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
    sync_catalog(Settings(_env_file=None, database_url=url))
    with admin.connect() as conn:
        # Зависший запрос падает с текстом, а не держит прогон часами.
        conn.execute(text(f"ALTER DATABASE \"{name}\" SET statement_timeout TO '30s'"))

    yield url

    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db_engine(request: pytest.FixtureRequest, database_url: str) -> Iterator[Engine]:
    if request.node.get_closest_marker("integration") is None:
        pytest.fail("тест ходит в базу без маркера integration: pytest.param(..., marks=...)")
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
        # Модели принятия нет — множитель 1: HTTP-тесты подборки — по одному соответствию.
        # Модель из файла — test_acceptance_model.py.
        acceptance_model_file=Path("no-acceptance-model.cbm"),
    )


@pytest.fixture(scope="session")
def mechanics() -> Mechanics:
    """Механики из конфига — одни на прогон: модель неизменяемая, тест меняет её через
    `model_copy`. Базы не требуют — годятся и in-memory тестам."""
    return Mechanics.from_yaml(Settings(_env_file=None).mechanics_file)


@pytest.fixture(scope="session")
def passwords() -> Argon2Passwords:
    """argon2 с минимальными параметрами: хэш того же формата, но каждый вход и регистрация
    не стоят десятков миллисекунд."""
    return Argon2Passwords(PasswordHasher.from_parameters(profiles.CHEAPEST))


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


@pytest.fixture
def clock() -> FrozenClock:
    """Время приложения в тесте стоит; тест двигает его сам — `shift` и `set`."""
    return FrozenClock(datetime.now(UTC).replace(microsecond=0))


@pytest.fixture
def seeds() -> Seeds:
    return Seeds()


@pytest.fixture
def fsp_id() -> MemoryFspId:
    """ФСП ID в памяти: тест выдаёт код за участника."""
    return MemoryFspId()


@pytest.fixture
def fsp_registry() -> MemoryFspRegistry:
    """Реестр ФСП в памяти: тест кладёт достижения и выключает реестр."""
    return MemoryFspRegistry()


@pytest.fixture
def app(
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    clock: FrozenClock,
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
    passwords: Argon2Passwords,
) -> Iterator[FastAPI]:
    app = create_app(
        settings,
        mechanics,
        outbox,
        clock=clock,
        seeds=seeds,
        fsp_id=fsp_id,
        fsp_registry=fsp_registry,
        passwords=passwords,
    )
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
