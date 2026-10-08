"""Регулярные задания работодателей и ответы кандидатов (mechanics.md, §11).

Задание после первого ответа не меняется: ответы оцениваются по его условию. Снятое задание
уходит из каталога, но остаётся в базе — его ответы и оценки входят в профили навыков.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.regular_task import PROMPT_MAX, REFERENCE_MAX, RESPONSE_MAX, TaskKind
from app.repository.database import Base
from app.repository.orm.catalog import Grade, Specialization, Topic


class RegularTask(Base):
    __tablename__ = "regular_tasks"
    __table_args__ = (
        # Эталон — у задания с эталоном и только у него.
        CheckConstraint(
            "(kind = 'reference') = (reference_answer IS NOT NULL)", name="reference_answer"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"), index=True)
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    kind: Mapped[TaskKind] = mapped_column(
        Enum(TaskKind, native_enum=False, create_constraint=True, length=16, name="task_kind")
    )
    prompt: Mapped[str] = mapped_column(String(PROMPT_MAX))
    reference_answer: Mapped[str | None] = mapped_column(String(REFERENCE_MAX))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()
    topics: Mapped[list["RegularTaskTopic"]] = relationship(
        cascade="all, delete-orphan", order_by="RegularTaskTopic.position"
    )


class RegularTaskTopic(Base):
    """Тема задания: 1–3 темы специализации задания в порядке, в котором их отметил автор."""

    __tablename__ = "regular_task_topics"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("regular_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    topic_code: Mapped[str] = mapped_column(ForeignKey("topics.code"), primary_key=True)
    position: Mapped[int]

    topic: Mapped[Topic] = relationship(lazy="joined")


class RegularTaskAnswer(Base):
    __tablename__ = "regular_task_answers"
    __table_args__ = (
        # На одно задание — один ответ кандидата.
        UniqueConstraint("task_id", "candidate_id"),
        CheckConstraint("rubric BETWEEN 0 AND 3", name="rubric_range"),
        CheckConstraint("(rubric IS NULL) = (graded_at IS NULL)", name="graded_at"),
        # Вердикт системы и оценка автора не бывают у одного ответа.
        CheckConstraint("correct IS NULL OR rubric IS NULL", name="one_verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("regular_tasks.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    response: Mapped[str] = mapped_column(String(RESPONSE_MAX))
    answered_at: Mapped[datetime]
    # Вердикт системы — у задания с эталоном.
    correct: Mapped[bool | None]
    # Оценка автора по рубрике 0–3 — у открытого задания.
    rubric: Mapped[int | None] = mapped_column(SmallInteger)
    graded_at: Mapped[datetime | None]
