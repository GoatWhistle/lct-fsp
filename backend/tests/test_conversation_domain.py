"""Переписка в домене (mechanics.md, §14): кто пишет и читает, какой текст можно отправить;
отзыв доступа переписку не закрывает."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.domain.conversation import Side, check_text, party
from app.domain.errors import InvalidMessageText, InvitationNotAccepted, InvitationNotFound
from app.domain.invitation import Invitation, InvitationStatus, InvitationTerms
from app.domain.work import SalaryRange

S = InvitationStatus
T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
CANDIDATE = uuid.uuid4()
EMPLOYER = uuid.uuid4()


def invitation(status: InvitationStatus = S.accepted) -> Invitation:
    return Invitation(
        id=uuid.uuid4(),
        employer_id=EMPLOYER,
        candidate_id=CANDIDATE,
        company_name="Рога и копыта",
        terms=InvitationTerms("Бэкенд платежей", SalaryRange(200_000, 260_000), "@hr_roga"),
        status=status,
        sent_at=T0,
        viewed_at=None,
        answered_at=T0,
    )


@pytest.mark.parametrize(("side", "user"), [(Side.candidate, CANDIDATE), (Side.employer, EMPLOYER)])
def test_sides_of_accepted_invitation_may_talk(side: Side, user: uuid.UUID) -> None:
    party(invitation(), side, user)


@pytest.mark.parametrize(
    ("side", "user"),
    [
        (Side.candidate, uuid.uuid4()),
        (Side.employer, uuid.uuid4()),
        # Чужая сторона с тем же id не проходит: кандидат не пишет от имени компании.
        (Side.candidate, EMPLOYER),
        (Side.employer, CANDIDATE),
    ],
)
def test_outsider_does_not_see_the_conversation(side: Side, user: uuid.UUID) -> None:
    with pytest.raises(InvitationNotFound):
        party(invitation(), side, user)


@pytest.mark.parametrize("status", [S.sent, S.viewed, S.declined, S.expired])
def test_not_accepted_invitation_has_no_conversation(status: InvitationStatus) -> None:
    with pytest.raises(InvitationNotAccepted):
        party(invitation(status), Side.candidate, CANDIDATE)


def test_outsider_learns_nothing_even_about_not_accepted() -> None:
    with pytest.raises(InvitationNotFound):
        party(invitation(S.sent), Side.employer, uuid.uuid4())


def test_revoked_invitation_keeps_the_conversation() -> None:
    party(replace(invitation(), revoked_at=T0), Side.employer, EMPLOYER)


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_is_rejected(text: str) -> None:
    with pytest.raises(InvalidMessageText):
        check_text(text, 10)


def test_text_over_max_length_is_rejected() -> None:
    check_text("а" * 10, 10)
    with pytest.raises(InvalidMessageText):
        check_text("а" * 11, 10)


def test_text_is_not_filtered() -> None:
    text = "Мой телеграм @me, телефон +7 999"

    assert check_text(f"  {text}  ", 100) == text
