"""Отклик кандидата на вакансию (mechanics.md, §14): инициатива у кандидата, ход — у работодателя.

Статусы и переходы — те же, что у приглашения (`InvitationStatus`, `transition`): отклик
отправлен → работодатель открыл его, просмотрено → принял или отклонил; без ответа дольше срока
— истёк. «Истекло» не записывается, его выводит `Application.at` по текущему моменту.

Отклик раскрывает кандидата компании вакансии сразу, в любом статусе: кандидат сам решил
показаться. Отзыв доступа — отметка на отклике, как на принятом приглашении; отклик остаётся в
своём статусе. Бюджет приглашений и правило одного открытого приглашения откликов не касаются —
откликнуться на вакансию можно один раз.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.domain.errors import (
    AlreadyApplied,
    ApplicationTransitionNotAllowed,
    InvitationTransitionNotAllowed,
    VacancyArchived,
)
from app.domain.invitation import OPEN, InvitationStatus, transition
from app.domain.vacancy import Vacancy
from app.domain.work import SalaryRange


@dataclass(frozen=True)
class Application:
    """Отклик; `status` — записанный статус, текущий — после `at`. Название, компания и вилка
    вакансии — как сейчас в вакансии: кандидат видит, куда откликался. `revoked_at` — когда
    кандидат отозвал доступ компании."""

    id: uuid.UUID
    vacancy_id: uuid.UUID
    employer_id: uuid.UUID
    candidate_id: uuid.UUID
    vacancy_title: str
    company_name: str
    salary: SalaryRange
    status: InvitationStatus
    applied_at: datetime
    viewed_at: datetime | None
    answered_at: datetime | None
    revoked_at: datetime | None = None

    def expires_at(self, ttl: timedelta) -> datetime:
        return self.applied_at + ttl

    def at(self, now: datetime, ttl: timedelta) -> "Application":
        """Отклик на момент `now`: без ответа дольше `ttl` с отклика — истёк."""
        if self.status in OPEN and now >= self.expires_at(ttl):
            return replace(self, status=_transition(self.status, InvitationStatus.expired))
        return self

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


def _transition(current: InvitationStatus, target: InvitationStatus) -> InvitationStatus:
    try:
        return transition(current, target)
    except InvitationTransitionNotAllowed:
        raise ApplicationTransitionNotAllowed() from None


def check_can_apply(vacancy: Vacancy, existing: Application | None) -> None:
    """Откликнуться можно на опубликованную вакансию и один раз; `existing` — уже поданный
    отклик этого кандидата на неё."""
    if vacancy.is_archived:
        raise VacancyArchived()
    if existing is not None:
        raise AlreadyApplied()


def viewed(application: Application, now: datetime) -> Application:
    """Работодатель открыл отклик: отправленный становится просмотренным, остальное — как было."""
    if application.status is not InvitationStatus.sent:
        return application
    return replace(
        application,
        status=_transition(application.status, InvitationStatus.viewed),
        viewed_at=now,
    )


def answered(application: Application, *, accept: bool, now: datetime) -> Application:
    """Решение работодателя — из отправленного или просмотренного; по закрытому или истёкшему —
    `ApplicationTransitionNotAllowed`."""
    target = InvitationStatus.accepted if accept else InvitationStatus.declined
    return replace(application, status=_transition(application.status, target), answered_at=now)


def revoked(application: Application, now: datetime) -> Application:
    """Кандидат отозвал доступ компании; повторный отзыв ничего не меняет."""
    if application.is_revoked:
        return application
    return replace(application, revoked_at=now)
