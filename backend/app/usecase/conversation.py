"""Переписка сторон принятого приглашения (mechanics.md, §14): только текст, непрочитанное —
счётчиком при запросе, без почты.

Кто пускается в переписку, решает домен (`party`): чужому она не существует, как чужое
приглашение. Открытие переписки отмечает сообщения другой стороны прочитанными.
"""

import uuid

from app.domain.conversation import Message, Side, check_text, party
from app.domain.errors import InvitationNotFound
from app.usecase.interface import Clock, InvitationRepository, MessageRepository, UnitOfWork


class Conversations:
    def __init__(
        self,
        uow: UnitOfWork,
        invitations: InvitationRepository,
        messages: MessageRepository,
        clock: Clock,
        *,
        max_length: int,
    ) -> None:
        self._uow = uow
        self._invitations = invitations
        self._messages = messages
        self._clock = clock
        self.max_length = max_length

    def open(self, side: Side, user_id: uuid.UUID, invitation_id: uuid.UUID) -> list[Message]:
        """Переписка приглашения, старые сверху; сообщения другой стороны становятся
        прочитанными."""
        with self._uow:
            self._party(side, user_id, invitation_id)
            self._messages.mark_read(invitation_id, side, self._clock.now())
            return self._messages.by_invitation(invitation_id)

    def send(self, side: Side, user_id: uuid.UUID, invitation_id: uuid.UUID, text: str) -> Message:
        """Новое сообщение стороны; в неприятое приглашение — `InvitationNotAccepted`."""
        with self._uow:
            self._party(side, user_id, invitation_id)
            text = check_text(text, self.max_length)
            return self._messages.add(invitation_id, side, text, self._clock.now())

    def unread(self, side: Side, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Непрочитанное пользователя по приглашениям; без непрочитанного — не попадают."""
        with self._uow:
            return self._messages.unread(side, user_id)

    def _party(self, side: Side, user_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        invitation = self._invitations.get(invitation_id)
        if invitation is None:
            raise InvitationNotFound()
        party(invitation, side, user_id)
