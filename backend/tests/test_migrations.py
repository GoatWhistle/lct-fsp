"""Миграции данных: старые записи переходят в новый формат без потерь смысла."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from app.repository.database import create_db_engine
from settings import BACKEND_DIR

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
BEFORE_GRADE_STATUS = "3e1f0c9a7b42"
GRADE_STATUS = "3f1c9a7d2e64"


@pytest.fixture
def blank_url(postgres_server_url: str) -> Iterator[str]:
    """Своя пустая база: миграции идут с нуля до нужной ревизии."""
    name = f"migrate_{uuid.uuid4().hex[:12]}"
    admin = create_db_engine(postgres_server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    yield make_url(postgres_server_url).set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def alembic(url: str) -> Config:
    cfg = Config(BACKEND_DIR / "alembic.ini")
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


def insert(engine: Engine, table: str, **row: object) -> None:
    columns = ", ".join(row)
    values = ", ".join(f":{c}" for c in row)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), row)


def candidate(engine: Engine, chain: tuple[str, ...]) -> uuid.UUID:
    """Кандидат с категорией по последней попытке цепочки; первая — заявленный грейд."""
    user_id, survey = uuid.uuid4(), uuid.uuid4()
    insert(
        engine,
        "users",
        id=user_id,
        email=f"{user_id.hex}@example.com",
        password_hash="-",
        role="candidate",
        created_at=T0,
    )
    insert(
        engine,
        "surveys",
        id=survey,
        user_id=user_id,
        number=1,
        specialization_code="qa",
        created_at=T0,
    )
    previous = None
    for number, grade in enumerate(chain, start=1):
        attempt = uuid.uuid4()
        insert(
            engine,
            "test_attempts",
            id=attempt,
            user_id=user_id,
            number=number,
            survey_id=survey,
            specialization_code="qa",
            grade_code=grade,
            continues_attempt_id=previous,
            started_at=T0,
        )
        previous = attempt
    insert(
        engine,
        "candidate_categories",
        user_id=user_id,
        specialization_code="qa",
        grade_code=chain[-1],
        attempt_id=previous,
        assigned_at=T0,
    )
    return user_id


def test_old_selection_entries_get_grade_status_from_the_category_chain(blank_url: str) -> None:
    cfg = alembic(blank_url)
    command.upgrade(cfg, BEFORE_GRADE_STATUS)
    engine = create_db_engine(blank_url)
    try:
        insert(engine, "specializations", code="qa", name="QA", position=1)
        for rank, (code, name) in enumerate((("junior", "Junior"), ("middle", "Middle")), 1):
            insert(engine, "grades", code=code, name=name, rank=rank)
        confirmed = candidate(engine, ("middle",))
        cascaded = candidate(engine, ("middle", "junior"))
        owner = uuid.uuid4()
        insert(
            engine,
            "users",
            id=owner,
            email="employer@example.com",
            password_hash="-",
            role="employer",
            created_at=T0,
        )
        selection = uuid.uuid4()
        insert(
            engine,
            "selections",
            id=selection,
            user_id=owner,
            need_snapshot='{"specialization": {"code": "qa", "name": "QA"}}',
            stack_cap=0.15,
            created_at=T0,
        )
        for position, (user_id, grade, name) in enumerate(
            ((confirmed, "middle", "Middle"), (cascaded, "junior", "Junior")), 1
        ):
            insert(
                engine,
                "selection_entries",
                selection_id=selection,
                position=position,
                candidate_id=user_id,
                block="exact" if grade == "middle" else "nearby",
                rank=1,
                grade_code=grade,
                grade_name=name,
                match_score=0.5,
                mutual_score=0.5,
                explanation="{}",
                stale=False,
            )

        command.upgrade(cfg, GRADE_STATUS)

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT candidate_id, grade_status, claimed_grade_code, claimed_grade_name "
                    "FROM selection_entries ORDER BY position"
                )
            ).all()
        assert [tuple(r) for r in rows] == [
            (confirmed, "confirmed", "middle", "Middle"),
            (cascaded, "below_claimed", "middle", "Middle"),
        ]

        command.downgrade(cfg, BEFORE_GRADE_STATUS)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM selection_entries")).scalar() == 2
    finally:
        engine.dispose()
