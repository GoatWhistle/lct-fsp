"""Справочники: грейды, сферы бизнеса, специализации, их темы и технологии стека.

Содержимое — в `config/catalog.yaml`, в базу его кладёт синхронизация справочника
(`app.usecase.catalog`). Ключ каждой записи — стабильный `code`: на него ссылаются тест, профиль и
подбор.
"""

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repository.database import Base

technology_topics = Table(
    "technology_topics",
    Base.metadata,
    Column(
        "technology_code", ForeignKey("technologies.code", ondelete="CASCADE"), primary_key=True
    ),
    Column("topic_code", ForeignKey("topics.code", ondelete="CASCADE"), primary_key=True),
)


class Grade(Base):
    __tablename__ = "grades"
    # Уникальность ранга проверяется в конце транзакции: синхронизация переставляет ранги.
    __table_args__ = (UniqueConstraint("rank", deferrable=True, initially="DEFERRED"),)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    rank: Mapped[int]


class Industry(Base):
    """Сфера бизнеса: деятельность компании и интересные кандидату сферы. «Отрасль» из ТЗ —
    другое: IT-направление, то есть специализация."""

    __tablename__ = "industries"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int]


class Specialization(Base):
    __tablename__ = "specializations"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int]

    topics: Mapped[list["Topic"]] = relationship(order_by="Topic.position")


class Topic(Base):
    __tablename__ = "topics"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    position: Mapped[int]


class Technology(Base):
    __tablename__ = "technologies"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))

    topics: Mapped[list[Topic]] = relationship(secondary=technology_topics, order_by="Topic.code")
