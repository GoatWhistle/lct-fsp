"""Справочники и путь кандидата к категории: опрос, попытки теста, предъявления, категория.

Справочники — грейды, отрасли, специализации, их темы и технологии стека. Содержимое — в
`catalog.yaml`, в базу его кладёт `python -m app.assessment.catalog`. Ключ каждой записи —
стабильный `code`: на него ссылаются тест, профиль и подбор.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, Enum, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

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


class Survey(Base):
    """Опрос — первый шаг пути: отрасль и специализация. Последний опрос кандидата — текущий."""

    __tablename__ = "surveys"
    __table_args__ = (UniqueConstraint("user_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Номер опроса кандидата с 1. Порядок — по нему: часы сервера при синхронизации отходят назад.
    number: Mapped[int]
    industry_code: Mapped[str] = mapped_column(ForeignKey("industries.code"))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    industry: Mapped[Industry] = relationship()
    specialization: Mapped[Specialization] = relationship()


class AttemptOutcome(enum.StrEnum):
    """Чем закончилась попытка первичного определения категории (mechanics.md, §4)."""

    # Категория присвоена: грейд попытки или ниже, если для него уверенность уже набрана.
    assigned = "assigned"
    # Уверенности не хватило — предложен дотест на грейд ниже.
    offered = "offered"
    # Не хватило и для стажёра: кандидат без категории до даты повтора.
    no_category = "no_category"


class TestAttempt(Base):
    """Попытка — прохождение теста на один грейд. Дотест каскада продолжает оценку попытки,
    на которую ссылается `continues_attempt_id`: вместе они — одно определение категории."""

    __tablename__ = "test_attempts"
    __table_args__ = (UniqueConstraint("user_id", "number"),)
    __test__ = False  # имя начинается с Test — pytest не должен собирать класс как тест

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Номер попытки кандидата с 1. Порядок — по нему, а не по часам, как у опросов.
    number: Mapped[int]
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    continues_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"), unique=True
    )
    # Коды семейств бланка по порядку предъявления.
    blueprint: Mapped[list[str]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]

    # Оценка теста на момент остановки: общий уровень θ̄ и его погрешность.
    overall_theta: Mapped[float | None]
    overall_theta_sd: Mapped[float | None]
    outcome: Mapped[AttemptOutcome | None] = mapped_column(
        Enum(
            AttemptOutcome,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="attempt_outcome",
        )
    )
    # Присвоенный или предложенный для дотеста грейд — по `outcome`.
    outcome_grade_code: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    retest_after: Mapped[datetime | None]

    presentations: Mapped[list["Presentation"]] = relationship(
        order_by="Presentation.position", back_populates="attempt"
    )


class Presentation(Base):
    """Предъявление экземпляра семейства: всё, на чём стоят калибровка, защита и валидация.

    Параметры семейства (a, b) записаны на момент показа: калибровка их потом сдвигает, а оценка
    попытки должна пересчитываться в то же значение. Эталон не хранится — он вычисляется из
    семейства и seed.
    """

    __tablename__ = "presentations"
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE")
    )
    position: Mapped[int]
    family_code: Mapped[str] = mapped_column(String(128), index=True)
    topic_code: Mapped[str] = mapped_column(ForeignKey("topics.code"))
    seed: Mapped[int] = mapped_column(BigInteger)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    discrimination: Mapped[float]
    difficulty: Mapped[float]
    # Оценка теста по теме до ответа (μ_t, σ_t).
    topic_theta_before: Mapped[float]
    topic_theta_sd_before: Mapped[float]
    # Время — по часам сервера: клиентские подделываются.
    shown_at: Mapped[datetime] = mapped_column(default=utcnow)
    answered_at: Mapped[datetime | None]
    response: Mapped[str | None] = mapped_column(String(500))
    correct: Mapped[bool | None]
    response_time_ms: Mapped[int | None]

    attempt: Mapped[TestAttempt] = relationship(back_populates="presentations")


class CandidateCategory(Base):
    """Категория кандидата — специализация × грейд. Строку пишет только присвоение по тесту:
    выдача работодателя строится по этой таблице, кандидата без строки в ней нет."""

    __tablename__ = "candidate_categories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_attempts.id"))
    assigned_at: Mapped[datetime] = mapped_column(default=utcnow)

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()
