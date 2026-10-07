"""Потребность и подборка (mechanics.md, §12).

Потребность — описание того, кого ищет работодатель: вход подборки, модели принятия и теста из
вакансии. Хранится то, что ввёл работодатель: поля формы, стек и правки важности тем. Важность
остальных тем выводится из стека при каждом чтении (`importance.py`), поэтому смена стека не
оставляет устаревших значений.

Подборка — результат подбора по потребности на момент построения: снимок потребности и выдача
со скорами и вкладами. Она не пересчитывается — открывается позже с той же выдачей, даже если
потребность поправили или удалили, а профили кандидатов изменились. Перестроение — новая
подборка.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, Enum, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.assessment.models import Grade, Specialization, Technology
from app.db import Base, utcnow
from app.domain.work import WorkFormat
from app.matching.importance import TopicImportance

need_technologies = Table(
    "need_technologies",
    Base.metadata,
    Column("need_id", ForeignKey("needs.id", ondelete="CASCADE"), primary_key=True),
    Column("technology_code", ForeignKey("technologies.code"), primary_key=True),
)


class Need(Base):
    __tablename__ = "needs"
    __table_args__ = (
        # Вилка необязательна, но указывается целиком: обе границы больше нуля, «от» ≤ «до».
        CheckConstraint(
            "(salary_from IS NULL AND salary_to IS NULL) OR "
            "(salary_from IS NOT NULL AND salary_to IS NOT NULL "
            "AND salary_from > 0 AND salary_from <= salary_to)",
            name="salary_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    team_description: Mapped[str] = mapped_column(String(2000))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    work_format: Mapped[WorkFormat] = mapped_column(
        Enum(WorkFormat, native_enum=False, create_constraint=True, length=16, name="work_format")
    )
    city: Mapped[str | None] = mapped_column(String(100))
    # Рубли в месяц до вычета НДФЛ — `app/domain/work.py`.
    salary_from: Mapped[int | None]
    salary_to: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()
    stack: Mapped[list[Technology]] = relationship(
        secondary=need_technologies, order_by="Technology.name"
    )
    edited_importance: Mapped[list["NeedTopicImportance"]] = relationship(
        cascade="all, delete-orphan"
    )


class NeedTopicImportance(Base):
    """Важность темы, которую работодатель поставил сам вместо выведенной из стека."""

    __tablename__ = "need_topic_importances"

    need_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("needs.id", ondelete="CASCADE"), primary_key=True
    )
    topic_code: Mapped[str] = mapped_column(ForeignKey("topics.code"), primary_key=True)
    importance: Mapped[TopicImportance] = mapped_column(
        Enum(
            TopicImportance,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="topic_importance",
        )
    )


class SelectionBlock(enum.StrEnum):
    # Категория кандидата — специализация и грейд потребности.
    exact = "exact"
    # Та же специализация, грейд на `nearby_grade_distance` от грейда потребности.
    nearby = "nearby"


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Удалённая потребность подборку не уносит: места кандидатов в подборках — история для
    # обратной связи кандидату, а открывается подборка по снимку.
    need_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("needs.id", ondelete="SET NULL"), index=True
    )
    # Потребность на момент построения с весами и требованиями по темам — `NeedSnapshot`.
    # Сохранённые подборки читаются этой схемой: её правка — вместе с миграцией данных.
    need_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # λ на момент построения — потолок вклада самоописания.
    stack_cap: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SelectionEntry(Base):
    """Кандидат в выдаче подборки: место, скоры и вклады на момент построения."""

    __tablename__ = "selection_entries"
    __table_args__ = (UniqueConstraint("selection_id", "candidate_id"),)

    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True
    )
    # Место в общей выдаче с 1: сначала точные, затем «близкие».
    position: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    block: Mapped[SelectionBlock] = mapped_column(
        Enum(
            SelectionBlock,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="selection_block",
        )
    )
    # Место внутри блока с 1.
    rank: Mapped[int]
    # Грейд категории кандидата на момент построения — со снимком названия, без ссылки на
    # справочник: правка справочника старую выдачу не меняет.
    grade_code: Mapped[str] = mapped_column(String(32))
    grade_name: Mapped[str] = mapped_column(String(64))
    match_score: Mapped[float]
    # P(принятия); NULL — модели принятия нет, множитель 1.
    acceptance_probability: Mapped[float | None]
    mutual_score: Mapped[float]
    # Вклады тем и стека — `Explanation`; коды тем и технологий, названия — из снимка. Как и
    # снимок, правка схемы — вместе с миграцией данных.
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Последний сигнал профиля старше `profile_stale_days`.
    stale: Mapped[bool]
