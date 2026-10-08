"""Приглашения в Postgres — реализация порта `InvitationRepository`. Изменения не фиксируются —
это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.domain.invitation import Invitation, InvitationStatus, InvitationTerms
from app.domain.work import SalaryRange
from app.repository.orm import Invitation as InvitationRow
from app.repository.orm import User


class SqlInvitations:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_company(self, employer_id: uuid.UUID) -> None:
        self._session.execute(select(User.id).where(User.id == employer_id).with_for_update())

    def add(
        self,
        employer_id: uuid.UUID,
        candidate_id: uuid.UUID,
        company_name: str,
        terms: InvitationTerms,
        now: datetime,
    ) -> Invitation:
        row = InvitationRow(
            id=uuid.uuid4(),
            employer_id=employer_id,
            candidate_id=candidate_id,
            company_name=company_name,
            description=terms.description,
            salary_from=terms.salary.low,
            salary_to=terms.salary.high,
            contact=terms.contact,
            status=InvitationStatus.sent,
            sent_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _invitation(row)

    def get(self, invitation_id: uuid.UUID, *, for_update: bool = False) -> Invitation | None:
        row = self._session.get(
            InvitationRow, invitation_id, with_for_update=for_update, populate_existing=True
        )
        return _invitation(row) if row else None

    def save(self, invitation: Invitation) -> None:
        if invitation.status is InvitationStatus.expired:
            raise ValueError("истёкшее не записывается — его выводит домен при чтении")
        row = self._session.get(InvitationRow, invitation.id)
        assert row is not None, "сохраняется только прочитанное приглашение"
        row.status = invitation.status
        row.viewed_at = invitation.viewed_at
        row.answered_at = invitation.answered_at
        self._session.flush()

    def by_candidate(self, candidate_id: uuid.UUID) -> list[Invitation]:
        return self._list(InvitationRow.candidate_id == candidate_id)

    def by_employer(self, employer_id: uuid.UUID) -> list[Invitation]:
        return self._list(InvitationRow.employer_id == employer_id)

    def latest(self, employer_id: uuid.UUID, candidate_id: uuid.UUID) -> Invitation | None:
        found = self._list(
            InvitationRow.employer_id == employer_id,
            InvitationRow.candidate_id == candidate_id,
            limit=1,
        )
        return found[0] if found else None

    def sent_since(self, employer_id: uuid.UUID, since: datetime) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(InvitationRow)
            .where(InvitationRow.employer_id == employer_id, InvitationRow.sent_at >= since)
        )
        return count or 0

    def accepted(self, employer_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
        found = self._session.scalar(
            select(InvitationRow.id)
            .where(
                InvitationRow.employer_id == employer_id,
                InvitationRow.candidate_id == candidate_id,
                InvitationRow.status == InvitationStatus.accepted,
            )
            .limit(1)
        )
        return found is not None

    def _list(self, *where: ColumnElement[bool], limit: int | None = None) -> list[Invitation]:
        stmt = (
            select(InvitationRow)
            .where(*where)
            .order_by(InvitationRow.sent_at.desc(), InvitationRow.id.desc())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return [_invitation(row) for row in self._session.scalars(stmt)]


def _invitation(row: InvitationRow) -> Invitation:
    return Invitation(
        id=row.id,
        employer_id=row.employer_id,
        candidate_id=row.candidate_id,
        company_name=row.company_name,
        terms=InvitationTerms(
            row.description, SalaryRange(row.salary_from, row.salary_to), row.contact
        ),
        status=row.status,
        sent_at=row.sent_at,
        viewed_at=row.viewed_at,
        answered_at=row.answered_at,
    )
