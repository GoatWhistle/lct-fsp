"""Вакансии работодателей и отклики кандидатов на них (mechanics.md, §14).

Вакансия хранит то, что ввёл работодатель, и название компании на момент последней правки;
снятая с публикации — отметка времени. У отклика — записанный статус, как у приглашения:
«истекло» выводит домен по сроку ответа на момент чтения. Отзыв доступа — отметка времени.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.invitation import InvitationStatus
from app.repository.database import Base
from app.repository.orm.catalog import Grade, Specialization


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        # Вилка обязательна: обе границы больше нуля, «от» ≤ «до».
        CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),
        CheckConstraint(
            "cardinality(work_formats) > 0 "
            "AND work_formats <@ ARRAY['office', 'hybrid', 'remote']::varchar[]",
            name="work_formats",
        ),
        # Общий список — опубликованные, новые сверху.
        Index("ix_vacancies_archived_at_published_at", "archived_at", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    employer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(5000))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    # Рубли в месяц до вычета НДФЛ — `app/domain/work.py`.
    salary_from: Mapped[int]
    salary_to: Mapped[int]
    published_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    archived_at: Mapped[datetime | None]

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        # Один отклик кандидата на вакансию.
        UniqueConstraint("vacancy_id", "candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="application_status",
        )
    )
    applied_at: Mapped[datetime]
    viewed_at: Mapped[datetime | None]
    answered_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    vacancy: Mapped[Vacancy] = relationship()
