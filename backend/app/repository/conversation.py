"""Переписка в приглашениях в Postgres — реализация порта `MessageRepository`. Изменения не
фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.conversation import Message, Side
from app.repository.orm import Invitation as InvitationRow
from app.repository.orm import InvitationMessage as MessageRow


class SqlMessages:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, invitation_id: uuid.UUID, author: Side, text: str, now: datetime) -> Message:
        row = MessageRow(
            id=uuid.uuid4(), invitation_id=invitation_id, author=author, text=text, sent_at=now
        )
        self._session.add(row)
        self._session.flush()
        return _message(row)

    def by_invitation(self, invitation_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(MessageRow)
            .where(MessageRow.invitation_id == invitation_id)
            .order_by(MessageRow.seq)
            .execution_options(populate_existing=True)
        )
        return [_message(row) for row in self._session.scalars(stmt)]

    def mark_read(self, invitation_id: uuid.UUID, reader: Side, now: datetime) -> None:
        self._session.execute(
            update(MessageRow)
            .where(
                MessageRow.invitation_id == invitation_id,
                MessageRow.author != reader,
                MessageRow.read_at.is_(None),
            )
            .values(read_at=now)
        )

    def unread(self, reader: Side, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        own = InvitationRow.candidate_id if reader is Side.candidate else InvitationRow.employer_id
        rows = self._session.execute(
            select(MessageRow.invitation_id, func.count())
            .join(InvitationRow, InvitationRow.id == MessageRow.invitation_id)
            .where(own == user_id, MessageRow.author != reader, MessageRow.read_at.is_(None))
            .group_by(MessageRow.invitation_id)
        )
        return {invitation_id: count for invitation_id, count in rows}


def _message(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        invitation_id=row.invitation_id,
        author=row.author,
        text=row.text,
        sent_at=row.sent_at,
        read_at=row.read_at,
    )
