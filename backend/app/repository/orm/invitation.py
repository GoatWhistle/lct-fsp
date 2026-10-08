"""Приглашения работодателей кандидатам (mechanics.md, §14).

Хранится записанный статус — отправлено, просмотрено, принято, отклонено. «Истекло» не
записывается: его выводит домен по сроку ответа на момент чтения. Компания — учётка работодателя;
её название записывается на момент отправки. Отзыв доступа — отметка времени на принятом
приглашении. Сообщения переписки — в своей таблице, по приглашению.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Identity, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.conversation import Side
from app.domain.invitation import InvitationStatus
from app.repository.database import Base


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
