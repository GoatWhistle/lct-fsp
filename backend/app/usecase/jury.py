"""Сценарии режима жюри: вход демо-работодателем и свежий тестовый кандидат (mechanics.md, §18).

Режим включает настройка окружения; выключенный не открывает ничего. Учётки создаются теми же
репозиториями, что и обычные, с пометкой `demo`: реальным работодателям они не показываются.
Демо-работодатель один на стенд, с компанией, потребностями и подборками; тестовый кандидат —
свежий на каждый вход: подтверждённый адрес, опрос и экспресс-тест уже начат. Вызовы чужих
сценариев идут по очереди, не вложенно: единица работы блок в блоке не открывает.
"""

import secrets
from dataclasses import dataclass

from app.domain.account import Account, Role
from app.domain.errors import DemoDisabled, EmailTaken
from app.domain.jury import DEMO_COMPANY, DEMO_DOMAIN, DEMO_EMPLOYER_EMAIL, DEMO_NEEDS
from app.domain.selection import SelectionBlock
from app.usecase.account import SignedIn
from app.usecase.attempt import CandidatePath
from app.usecase.company import Companies
from app.usecase.interface import AccountRepository, Clock, SessionTokens, UnitOfWork
from app.usecase.need import Needs
from app.usecase.selection import Selections

# Подборок на выдаче в кабинете немного: первая страница строится целиком.
SELECTION_LIMIT = 20


@dataclass(frozen=True)
class JuryStatus:
    enabled: bool


class JuryMode:
    def __init__(
        self,
        uow: UnitOfWork,
        accounts: AccountRepository,
        companies: Companies,
        needs: Needs,
        selections: Selections,
        paths: CandidatePath,
        sessions: SessionTokens,
        clock: Clock,
        *,
        enabled: bool,
    ) -> None:
        self._uow = uow
        self._accounts = accounts
        self._companies = companies
        self._needs = needs
        self._selections = selections
        self._paths = paths
        self._sessions = sessions
        self._clock = clock
        self._enabled = enabled

    def status(self) -> JuryStatus:
        return JuryStatus(self._enabled)

    def employer(self) -> SignedIn:
        """Вход демо-работодателем: учётка, компания, потребности и подборки заводятся при первом
        входе и дальше не дублируются."""
        self._require()
        account = self._demo_account(DEMO_EMPLOYER_EMAIL, Role.employer)
        if self._companies.get(account.id) is None:
            self._companies.save(account.id, DEMO_COMPANY)
        if not self._needs.all(account.id):
            for form in DEMO_NEEDS:
                self._needs.create(account.id, form)
        for view in self._needs.all(account.id):
            need_id = view.record.need.id
            latest = self._selections.summaries(account.id, need_id, limit=1)
            # Подборка, снятая до засева кандидатов, пуста — строим заново.
            if not latest or not (
                latest[0].totals.get(SelectionBlock.exact)
                or latest[0].totals.get(SelectionBlock.nearby)
            ):
                self._selections.build(account.id, need_id, limit=SELECTION_LIMIT)
        return self._sign_in(account)

    def candidate(self, specialization: str, grade: str) -> SignedIn:
        """Свежий тестовый кандидат: опрос пройден, экспресс-тест на `grade` начат."""
        self._require()
        email = f"candidate-{secrets.token_hex(6)}@{DEMO_DOMAIN}"
        account = self._demo_account(email, Role.candidate)
        self._paths.submit_survey(account.id, specialization=specialization)
        self._paths.start_attempt(account.id, grade=grade, express=True)
        return self._sign_in(account)

    def _require(self) -> None:
        if not self._enabled:
            raise DemoDisabled()

    def _demo_account(self, email: str, role: Role) -> Account:
        """Есть — та же; нет — новая. Параллельный первый вход проигрывает по `EmailTaken` и
        читает победителя."""
        try:
            with self._uow:
                found = self._accounts.by_email(email)
                return found or self._accounts.add_demo(email, role, self._clock.now())
        except EmailTaken:
            with self._uow:
                found = self._accounts.by_email(email)
            assert found is not None
            return found

    def _sign_in(self, account: Account) -> SignedIn:
        return SignedIn(account, self._sessions.issue(account.id, self._clock.now()))
