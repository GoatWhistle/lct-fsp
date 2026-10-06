from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from fastapi import Depends, Request
from sqlalchemy import DateTime, Engine, MetaData, create_engine  # noqa: TID251
from sqlalchemy.orm import DeclarativeBase, Session

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


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_db_engine(url: str, **kwargs: Any) -> Engine:
    """Движок, у которого время из базы приходит в UTC, какой бы пояс ни стоял у сервера.

    Пояс задаётся в стартовых параметрах подключения: он становится поясом сессии
    по умолчанию, и `RESET ALL` его не сбрасывает.
    """
    return create_engine(url, connect_args={"options": "-c timezone=UTC"}, **kwargs)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
