"""Переписка внутри принятого приглашения (mechanics.md, §14): списаться на платформе вместо
обмена контактами.

Сторон две — кандидат-адресат и компания-отправитель; остальным переписка не существует так же,
как чужое приглашение (`party`). Пишут только в принятое приглашение, отзыв доступа переписку не
закрывает. Сообщение — только текст, без фильтра: кандидат сам решает, что писать. Читает
сообщение всегда другая сторона, поэтому отметка о прочтении — одна на сообщение (`read_at`).
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.errors import InvalidMessageText, InvitationNotAccepted, InvitationNotFound
from app.domain.invitation import Invitation, InvitationStatus


class Side(enum.StrEnum):
    candidate = "candidate"
    employer = "employer"


@dataclass(frozen=True)
class Message:
    id: uuid.UUID
    invitation_id: uuid.UUID
    author: Side
    text: str
    sent_at: datetime
    # Когда другая сторона открыла переписку после этого сообщения; `None` — не прочитано.
    read_at: datetime | None


def party(invitation: Invitation, side: Side, user_id: uuid.UUID) -> None:
    """Пустит ли переписка приглашения `invitation` (на момент чтения) пользователя с этой
    стороны. Не сторона — `InvitationNotFound`, как на чужое приглашение; приглашение не
    принято — `InvitationNotAccepted`."""
    own = invitation.candidate_id if side is Side.candidate else invitation.employer_id
    if own != user_id:
        raise InvitationNotFound()
    if invitation.status is not InvitationStatus.accepted:
        raise InvitationNotAccepted()


def check_text(text: str, max_length: int) -> str:
    """Текст сообщения без пробелов по краям; пустой или длиннее `max_length` —
    `InvalidMessageText`."""
    text = text.strip()
    if not text or len(text) > max_length:
        raise InvalidMessageText()
    return text
