"""Потребность — описание того, кого ищет работодатель: вход подборки, модели принятия и теста
из вакансии (mechanics.md, §12).

Хранится то, что ввёл работодатель: поля формы, стек и правки важности тем. Важность остальных
тем выводится из стека при каждом чтении (`importance.py`), поэтому смена стека не оставляет
устаревших значений.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, Enum, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.assessment.models import Grade, Specialization, Technology
from app.db import Base, utcnow
from app.matching.importance import TopicImportance


class WorkFormat(enum.StrEnum):
    office = "office"
    hybrid = "hybrid"
    remote = "remote"


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
    # Рубли в месяц.
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
