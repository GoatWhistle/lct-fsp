from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, ClassVar

from fastapi import Depends, Request
from sqlalchemy import DateTime, MetaData
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


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
