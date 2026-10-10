"""Сценарии приглашений (mechanics.md, §14): работодатель отправляет и видит отправленные с
остатком бюджета, кандидат видит входящие, открывает их, отвечает и отзывает доступ по
принятому.

Чужое приглашение для зрителя не существует — `InvitationNotFound`, а не отказ в доступе: так не
раскрывается, что такое есть. Статус на момент чтения выводит домен (`Invitation.at`), поэтому
каждый сценарий читает «сейчас» один раз и проводит приглашения через него. Приглашают только
кандидата с категорией — без неё работодатель его не видит; приглашает компания — без профиля
компании кандидату не показать, кто зовёт.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.errors import (
    CandidateNotFound,
    CompanyProfileRequired,
    InvitationNotFound,
    VacancyTestSpecializationMismatch,
)
from app.domain.invitation import (
    Invitation,
    InvitationBudget,
    InvitationTerms,
    answered,
    budget_week,
    check_can_send,
    revoked,
    viewed,
)
from app.domain.selection import Need
from app.domain.vacancy_test import VacancyTestPlan
from app.usecase.candidate import revoke_company_access
from app.usecase.interface import (
    ApplicationRepository,
    CandidateRepository,
    Clock,
    CompanyRepository,
    InvitationRepository,
    NeedReader,
    UnitOfWork,
    VacancyTestRepository,
)


@dataclass(frozen=True)
class SentInvitations:
    budget: InvitationBudget
    invitations: list[Invitation]


class Invitations:
    def __init__(
        self,
        uow: UnitOfWork,
        invitations: InvitationRepository,
        applications: ApplicationRepository,
        candidates: CandidateRepository,
        companies: CompanyRepository,
        clock: Clock,
        *,
        weekly_budget: int,
        ttl_days: int,
        needs: NeedReader | None = None,
        vacancy_tests: VacancyTestRepository | None = None,
        test_plan: Callable[[Need], VacancyTestPlan] | None = None,
    ) -> None:
        self._uow = uow
        self._invitations = invitations
        self._applications = applications
        self._candidates = candidates
        self._companies = companies
        self._clock = clock
        self._weekly_budget = weekly_budget
        self.ttl = timedelta(days=ttl_days)
        self._needs = needs
        self._vacancy_tests = vacancy_tests
        self._test_plan = test_plan

    def send(
        self,
        employer_id: uuid.UUID,
        candidate_id: uuid.UUID,
        terms: InvitationTerms,
        *,
        test_need_id: uuid.UUID | None = None,
    ) -> Invitation:
        """Новое приглашение: кандидат с категорией, профиль компании заполнен, прошлое
        приглашение этому кандидату закрыто, бюджет недели не исчерпан. `test_need_id` —
        потребность, по которой к приглашению прикладывается тест по вакансии (§6): своя, той
        же специализации, что категория кандидата."""
        with self._uow:
            now = self._clock.now()
            company = self._companies.get(employer_id)
            if company is None:
                raise CompanyProfileRequired()
            category = self._candidates.get(candidate_id).category
            if category is None:
                raise CandidateNotFound()
            plan = None
            if test_need_id is not None:
                assert self._needs is not None and self._test_plan is not None
                need = self._needs.get(employer_id, test_need_id)
                if need.specialization.code != category.specialization.code:
                    raise VacancyTestSpecializationMismatch()
                plan = (need.title, self._test_plan(need))
            self._invitations.lock_company(employer_id)
            latest = self._invitations.latest(employer_id, candidate_id)
            check_can_send(self._budget(employer_id, now), latest, now, self.ttl)
            invitation = self._invitations.add(employer_id, candidate_id, company.name, terms, now)
            if plan is not None:
                assert self._vacancy_tests is not None
                self._vacancy_tests.add(invitation.id, plan[0], plan[1], now)
            return invitation

    def sent(self, employer_id: uuid.UUID) -> SentInvitations:
        """Отправленные компанией и остаток бюджета на текущую неделю."""
        with self._uow:
            now = self._clock.now()
            return SentInvitations(
                self._budget(employer_id, now),
                [i.at(now, self.ttl) for i in self._invitations.by_employer(employer_id)],
            )

    def sent_one(self, employer_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        with self._uow:
            invitation = self._invitations.get(invitation_id)
            if invitation is None or invitation.employer_id != employer_id:
                raise InvitationNotFound()
            return invitation.at(self._clock.now(), self.ttl)

    def inbox(self, candidate_id: uuid.UUID) -> list[Invitation]:
        """Входящие кандидата."""
        with self._uow:
            now = self._clock.now()
            return [i.at(now, self.ttl) for i in self._invitations.by_candidate(candidate_id)]

    def view(self, candidate_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        """Кандидат открыл приглашение: отправленное становится просмотренным."""
        with self._uow:
            now = self._clock.now()
            current = self._own(candidate_id, invitation_id, now)
            result = viewed(current, now)
            if result != current:
                self._invitations.save(result)
            return result

    def answer(
        self, candidate_id: uuid.UUID, invitation_id: uuid.UUID, *, accept: bool
    ) -> Invitation:
        """Принять или отклонить; ответ на закрытое — `InvitationTransitionNotAllowed`."""
        with self._uow:
            now = self._clock.now()
            result = answered(self._own(candidate_id, invitation_id, now), accept=accept, now=now)
            self._invitations.save(result)
            return result

    def revoke(self, candidate_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        """Отозвать доступ компании по принятому приглашению; повторно — ничего не меняет, по
        неприятому — `InvitationNotAccepted`. Отзыв закрывает и другие принятые приглашения той же
        компании этому кандидату, и его отклики на её вакансии: иначе любое из них раскрывало бы
        данные дальше."""
        with self._uow:
            now = self._clock.now()
            current = self._own(candidate_id, invitation_id, now)
            result = revoked(current, now)
            # Повторный отзыв ничего не меняет — и не закрывает доступ, открытый после первого.
            if current.is_revoked:
                return result
            revoke_company_access(
                self._invitations, self._applications, candidate_id, result.employer_id, now
            )
            return result

    def _own(self, candidate_id: uuid.UUID, invitation_id: uuid.UUID, now: datetime) -> Invitation:
        """Приглашение кандидата на момент `now` — под блокировкой до конца блока."""
        invitation = self._invitations.get(invitation_id, for_update=True)
        if invitation is None or invitation.candidate_id != candidate_id:
            raise InvitationNotFound()
        return invitation.at(now, self.ttl)

    def _budget(self, employer_id: uuid.UUID, now: datetime) -> InvitationBudget:
        start, end = budget_week(now)
        used = self._invitations.sent_since(employer_id, start)
        return InvitationBudget(limit=self._weekly_budget, used=used, resets_at=end)
