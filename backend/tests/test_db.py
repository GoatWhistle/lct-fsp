"""Подключение к базе: время из неё приходит в UTC, какой бы часовой пояс ни стоял у базы."""

from datetime import timedelta

from sqlalchemy import create_engine, text  # noqa: TID251 — пояс самой базы, без фабрики

from app.db import create_db_engine
from tests.conftest import DATABASE_TIMEZONE


def test_database_under_test_is_not_in_utc(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        zone = conn.scalar(text("SHOW timezone"))
    engine.dispose()

    assert zone == DATABASE_TIMEZONE


def test_engine_reads_time_in_utc_on_database_in_another_zone(database_url: str) -> None:
    engine = create_db_engine(database_url)
    with engine.connect() as conn:
        moment = conn.scalar(text("SELECT now()"))
        conn.execute(text("RESET ALL"))
        after_reset = conn.scalar(text("SELECT now()"))
    engine.dispose()

    assert moment.utcoffset() == timedelta(0)
    assert after_reset.utcoffset() == timedelta(0)
