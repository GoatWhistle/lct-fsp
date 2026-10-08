"""Приглашение в домене (mechanics.md, §14): переходы статусов, срок ответа, неделя бюджета."""

import itertools
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.errors import (
    InvitationAlreadyOpen,
    InvitationBudgetExhausted,
    InvitationExpired,
    InvitationTransitionNotAllowed,
)
from app.domain.invitation import (
    TRANSITIONS,
    Invitation,
    InvitationBudget,
    InvitationStatus,
    InvitationTerms,
    answered,
    budget_week,
    check_can_send,
    transition,
    viewed,
)
from app.domain.work import SalaryRange

S = InvitationStatus
T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TTL = timedelta(days=7)

ALLOWED = {
    (S.sent, S.viewed),
    (S.sent, S.accepted),
    (S.sent, S.declined),
    (S.sent, S.expired),
    (S.viewed, S.accepted),
    (S.viewed, S.declined),
    (S.viewed, S.expired),
}


def invitation(status: InvitationStatus = S.sent, sent_at: datetime = T0) -> Invitation:
    return Invitation(
        id=uuid.uuid4(),
        employer_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        company_name="Рога и копыта",
        terms=InvitationTerms("Бэкенд платежей", SalaryRange(200_000, 260_000), "@hr_roga"),
        status=status,
        sent_at=sent_at,
        viewed_at=None,
        answered_at=None,
    )


def test_transitions_are_exactly_the_allowed_ones() -> None:
    assert ALLOWED == TRANSITIONS


@pytest.mark.parametrize(("current", "target"), sorted(ALLOWED))
def test_allowed_transition_passes(current: InvitationStatus, target: InvitationStatus) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    sorted(set(itertools.product(S, S)) - ALLOWED),
)
def test_other_transition_is_rejected(current: InvitationStatus, target: InvitationStatus) -> None:
    with pytest.raises(InvitationTransitionNotAllowed):
        transition(current, target)


def test_unanswered_invitation_expires_after_ttl() -> None:
    sent = invitation()

    assert sent.at(T0 + TTL - timedelta(seconds=1), TTL).status is S.sent
    assert sent.at(T0 + TTL, TTL).status is S.expired
    assert replace(sent, status=S.viewed).at(T0 + TTL, TTL).status is S.expired
    assert sent.expires_at(TTL) == T0 + TTL


@pytest.mark.parametrize("status", [S.accepted, S.declined])
def test_answered_invitation_never_expires(status: InvitationStatus) -> None:
    assert invitation(status).at(T0 + 10 * TTL, TTL).status is status


def test_open_is_sent_or_viewed_and_not_expired() -> None:
    assert invitation(S.sent).is_open
    assert invitation(S.viewed).is_open
    assert not invitation(S.accepted).is_open
    assert not invitation(S.declined).is_open
    assert not invitation().at(T0 + TTL, TTL).is_open


def test_view_marks_sent_as_viewed_once() -> None:
    now = T0 + timedelta(hours=1)

    first = viewed(invitation(), now)
    again = viewed(first, now + timedelta(hours=1))

    assert (first.status, first.viewed_at) == (S.viewed, now)
    assert again == first


@pytest.mark.parametrize("status", [S.accepted, S.declined, S.expired])
def test_view_of_closed_changes_nothing(status: InvitationStatus) -> None:
    closed = invitation(status)

    assert viewed(closed, T0) == closed


@pytest.mark.parametrize("status", [S.sent, S.viewed])
@pytest.mark.parametrize("accept", [True, False])
def test_answer_from_open(status: InvitationStatus, accept: bool) -> None:
    now = T0 + timedelta(days=1)

    result = answered(invitation(status), accept=accept, now=now)

    assert result.status is (S.accepted if accept else S.declined)
    assert result.answered_at == now


@pytest.mark.parametrize("status", [S.accepted, S.declined])
@pytest.mark.parametrize("accept", [True, False])
def test_answer_twice_is_rejected(status: InvitationStatus, accept: bool) -> None:
    with pytest.raises(InvitationTransitionNotAllowed):
        answered(invitation(status), accept=accept, now=T0)


def test_answer_to_expired_is_rejected_as_expired() -> None:
    expired = invitation().at(T0 + TTL, TTL)

    with pytest.raises(InvitationExpired):
        answered(expired, accept=True, now=T0 + TTL)


def test_budget_week_starts_monday_midnight_moscow() -> None:
    # Понедельник 12 октября 2026, 00:00 МСК — воскресенье 11 октября, 21:00 UTC.
    monday = datetime(2026, 10, 11, 21, 0, tzinfo=UTC)

    assert budget_week(monday) == (monday, monday + timedelta(days=7))
    assert budget_week(monday - timedelta(seconds=1)) == (monday - timedelta(days=7), monday)
    assert budget_week(monday + timedelta(days=6, hours=23)) == (
        monday,
        monday + timedelta(days=7),
    )


def test_budget_remaining_never_negative() -> None:
    resets = T0 + timedelta(days=3)

    assert InvitationBudget(limit=20, used=5, resets_at=resets).remaining == 15
    assert InvitationBudget(limit=2, used=3, resets_at=resets).remaining == 0


def test_cannot_send_over_budget() -> None:
    with pytest.raises(InvitationBudgetExhausted):
        check_can_send(InvitationBudget(limit=2, used=2, resets_at=T0), None, T0, TTL)


def test_cannot_send_while_previous_is_open() -> None:
    budget = InvitationBudget(limit=20, used=1, resets_at=T0)

    with pytest.raises(InvitationAlreadyOpen):
        check_can_send(budget, invitation(S.viewed), T0, TTL)


@pytest.mark.parametrize("status", [S.accepted, S.declined])
def test_can_send_after_previous_is_answered(status: InvitationStatus) -> None:
    budget = InvitationBudget(limit=20, used=1, resets_at=T0)

    check_can_send(budget, invitation(status), T0, TTL)


@pytest.mark.parametrize("status", [S.sent, S.viewed])
def test_can_send_after_previous_expired_though_stored_open(status: InvitationStatus) -> None:
    budget = InvitationBudget(limit=20, used=1, resets_at=T0)

    check_can_send(budget, invitation(status), T0 + TTL, TTL)
