"""Приглашения работодателей кандидатам (mechanics.md, §14).

Хранится записанный статус — отправлено, просмотрено, принято, отклонено. «Истекло» не
записывается: его выводит домен по сроку ответа на момент чтения. Компания — учётка работодателя;
её название записывается на момент отправки. Отзыв доступа — отметка времени на принятом
приглашении. Сообщения переписки — в своей таблице, по приглашению.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Identity, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.conversation import Side
from app.domain.invitation import InvitationStatus
from app.repository.database import Base
from app.repository.orm.catalog import Grade, Specialization


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        # Вилка обязательна: обе границы больше нуля, «от» ≤ «до».
        CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),
        # Бюджет недели — отправленные компанией с понедельника.
        Index("ix_invitations_employer_id_sent_at", "employer_id", "sent_at"),
        # Последнее приглашение пары и принятое приглашение пары.
        Index("ix_invitations_employer_id_candidate_id", "employer_id", "candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(3000))
    # Рубли в месяц до вычета НДФЛ — `app/domain/work.py`.
    salary_from: Mapped[int]
    salary_to: Mapped[int]
    contact: Mapped[str] = mapped_column(String(300))
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="invitation_status",
        )
    )
    sent_at: Mapped[datetime]
    viewed_at: Mapped[datetime | None]
    answered_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class InvitationMessage(Base):
    __tablename__ = "invitation_messages"
    __table_args__ = (
        # Переписка приглашения по порядку и непрочитанное стороны в нём.
        Index("ix_invitation_messages_invitation_id_seq", "invitation_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Порядок записи: у сообщений одной секунды порядок не теряется.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE")
    )
    author: Mapped[Side] = mapped_column(
        Enum(Side, native_enum=False, create_constraint=True, length=16, name="message_author")
    )
    text: Mapped[str] = mapped_column(String)
    sent_at: Mapped[datetime]
    # Прочитано другой стороной: открытие переписки отмечает её сообщения.
    read_at: Mapped[datetime | None]


class VacancyTest(Base):
    """Тест по вакансии, приложенный к приглашению: план на момент отправки. Темы — список
    словарей {код, название, важность, вес, заданий}, его собирает и читает репозиторий."""

    __tablename__ = "vacancy_tests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"), unique=True
    )
    need_title: Mapped[str] = mapped_column(String(200))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    # Требуемый уровень θ — порог грейда потребности на момент отправки.
    requirement: Mapped[float]
    topics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime]

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()
