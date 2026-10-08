"""Приглашение работодателя кандидату (mechanics.md, §14): инициатива у работодателя.

Статусы: отправлено → просмотрено → принято, отклонено или истекло. Переходы — `TRANSITIONS`,
проверяет их `transition`. «Истекло» не записывается: приглашение без ответа дольше срока
читается истёкшим по текущему моменту (`Invitation.at`) — фоновый планировщик не нужен.

Рынок, а не спам: у компании недельный бюджет приглашений с понедельника 00:00 по Москве, и
пока приглашение компании кандидату открыто, второе той же компании не создаётся
(`check_can_send`). Отклонённые и истёкшие бюджет не возвращают. Компания — учётка
работодателя: одна учётка — одна компания.
"""

import enum
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta, timezone

from app.domain.errors import (
    InvitationAlreadyOpen,
    InvitationBudgetExhausted,
    InvitationExpired,
    InvitationTransitionNotAllowed,
)
from app.domain.work import SalaryRange

# Москва без перехода на летнее время с 2014 года — фиксированный UTC+3.
MOSCOW = timezone(timedelta(hours=3), "MSK")


class InvitationStatus(enum.StrEnum):
    sent = "sent"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"


OPEN = frozenset({InvitationStatus.sent, InvitationStatus.viewed})

TRANSITIONS = frozenset(
    {(InvitationStatus.sent, InvitationStatus.viewed)}
    | {
        (current, target)
        for current in OPEN
        for target in (
            InvitationStatus.accepted,
            InvitationStatus.declined,
            InvitationStatus.expired,
        )
    }
)


def transition(current: InvitationStatus, target: InvitationStatus) -> InvitationStatus:
    """Переход статуса; не из `TRANSITIONS` — `InvitationTransitionNotAllowed`."""
    if (current, target) not in TRANSITIONS:
        raise InvitationTransitionNotAllowed()
    return target


@dataclass(frozen=True)
class InvitationTerms:
    """Условия приглашения — кандидат видит их до начала общения. Вилка обязательна: рубли в
    месяц до вычета НДФЛ."""

    description: str
    salary: SalaryRange
    contact: str


@dataclass(frozen=True)
class Invitation:
    """Приглашение; `status` — записанный статус, текущий — после `at`. `company_name` — название
    компании на момент отправки: кандидат видит, кто его пригласил, даже если профиль потом
    поправили."""

    id: uuid.UUID
    employer_id: uuid.UUID
    candidate_id: uuid.UUID
    company_name: str
    terms: InvitationTerms
    status: InvitationStatus
    sent_at: datetime
    viewed_at: datetime | None
    answered_at: datetime | None

    def expires_at(self, ttl: timedelta) -> datetime:
        return self.sent_at + ttl

    def at(self, now: datetime, ttl: timedelta) -> "Invitation":
        """Приглашение на момент `now`: без ответа дольше `ttl` с отправки — истекло."""
        if self.status in OPEN and now >= self.expires_at(ttl):
            return replace(self, status=transition(self.status, InvitationStatus.expired))
        return self

    @property
    def is_open(self) -> bool:
        """Ждёт ответа. Верно только для приглашения после `at`."""
        return self.status in OPEN


def viewed(invitation: Invitation, now: datetime) -> Invitation:
    """Кандидат открыл приглашение: отправленное становится просмотренным, остальное — как было."""
    if invitation.status is not InvitationStatus.sent:
        return invitation
    return replace(
        invitation, status=transition(invitation.status, InvitationStatus.viewed), viewed_at=now
    )


def answered(invitation: Invitation, *, accept: bool, now: datetime) -> Invitation:
    """Ответ кандидата — из отправленного или просмотренного; на истёкшее —
    `InvitationExpired`, повторный — `InvitationTransitionNotAllowed`."""
    if invitation.status is InvitationStatus.expired:
        raise InvitationExpired()
    target = InvitationStatus.accepted if accept else InvitationStatus.declined
    return replace(invitation, status=transition(invitation.status, target), answered_at=now)


def budget_week(now: datetime) -> tuple[datetime, datetime]:
    """Неделя бюджета, в которую попадает `now`: с понедельника 00:00 по Москве до следующего;
    границы — в UTC."""
    local = now.astimezone(MOSCOW)
    monday = local.date() - timedelta(days=local.weekday())
    start = datetime.combine(monday, time(), MOSCOW).astimezone(UTC)
    return start, start + timedelta(days=7)


@dataclass(frozen=True)
class InvitationBudget:
    """Бюджет компании на текущую неделю: сколько можно, сколько отправлено, когда обновится."""

    limit: int
    used: int
    resets_at: datetime

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)


def check_can_send(
    budget: InvitationBudget, latest: Invitation | None, now: datetime, ttl: timedelta
) -> None:
    """Можно ли компании отправить приглашение кандидату. `latest` — её последнее приглашение
    этому кандидату, как записано: открытым может быть только оно; истёкшее — уже не открыто."""
    if latest is not None and latest.at(now, ttl).is_open:
        raise InvitationAlreadyOpen()
    if budget.remaining == 0:
        raise InvitationBudgetExhausted()
