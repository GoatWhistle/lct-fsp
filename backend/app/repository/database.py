"""Подключение к Postgres и база ORM-моделей. ORM — только в `app.repository`, модели таблиц —
в `app.repository.orm`."""

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, Engine, MetaData, create_engine  # noqa: TID251
from sqlalchemy.orm import DeclarativeBase

# Имена ограничений задаём явно — иначе миграции на разных машинах расходятся.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar = {datetime: DateTime(timezone=True)}


def create_db_engine(url: str, **kwargs: Any) -> Engine:
    """Движок, у которого время из базы приходит в UTC, какой бы пояс ни стоял у сервера.

    Пояс задаётся в стартовых параметрах подключения: он становится поясом сессии
    по умолчанию, и `RESET ALL` его не сбрасывает.
    """
    return create_engine(url, connect_args={"options": "-c timezone=UTC"}, **kwargs)
