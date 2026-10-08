"""Сценарии ФСП ID: вход и привязка через ФСП ID, отвязка, обновление достижений и их показ
кандидату (mechanics.md, §11).

ФСП ID, реестр ФСП, токен входа и модель навыка — за портами. Вход через ФСП ID создаёт или находит
учётку кандидата; учётку с тем же email он не трогает — её владелец привязывает ID сам, войдя по
email: автопривязка по адресу отдала бы учётку тому, кто завёл адрес в ФСП ID. Реестр опрашивается
до транзакции; не ответил — остаётся прошлый снимок, вход и привязка не ломаются. Каждый новый
снимок, привязка и отвязка пересчитывают профили навыков; оценку теста и категорию — никогда.
"""

import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass

from app.domain.account import Account, Role, normalize_email
from app.domain.errors import (
    EmailTaken,
    FspAlreadyLinked,
    FspAuthorizationInvalid,
    FspEmailTaken,
    FspEmailUnverified,
    FspIdRejected,
    FspIdTaken,
    FspNotLinked,
    FspRegistryUnavailable,
    FspUnlinkForbidden,
    NotAuthenticated,
    WrongRole,
)
from app.domain.fsp import (
    Divergence,
    FspAchievement,
    FspAuthorization,
    FspHistory,
    FspIdentity,
    FspIntent,
)
from app.usecase.account import SignedIn
from app.usecase.interface import (
    AccountRepository,
    AttemptRepository,
    Clock,
    FspIdProvider,
    FspRegistry,
    FspRepository,
    RegularTaskReader,
    SessionTokens,
    SkillModel,
    UnitOfWork,
)
from app.usecase.skill_profile import fsp_divergences, fsp_evidence, rebuild_skill_profiles
from settings import Mechanics

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FspStarted:
    """Куда отправить браузер и что запомнить до его возвращения."""

    url: str
    authorization: FspAuthorization


@dataclass(frozen=True)
class FspStatus:
    """ФСП ID глазами кандидата. `history` — `None`, если ID не привязан; `divergences` видит
    только он сам."""

    fsp_id: str | None
    can_unlink: bool
    history: FspHistory | None
    divergences: tuple[Divergence, ...]


class FspAccounts:
    def __init__(
        self,
        uow: UnitOfWork,
        accounts: AccountRepository,
        attempts: AttemptRepository,
        fsp: FspRepository,
        tasks: RegularTaskReader,
        provider: FspIdProvider,
        registry: FspRegistry,
        sessions: SessionTokens,
        model: SkillModel,
        clock: Clock,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._accounts = accounts
        self._attempts = attempts
        self._fsp = fsp
        self._tasks = tasks
        self._provider = provider
        self._registry = registry
        self._sessions = sessions
        self._model = model
        self._clock = clock
        self._mechanics = mechanics

    def start(self, intent: FspIntent, user: Account | None) -> FspStarted:
        """Начало входа или привязки. Привязывает только вошедший кандидат; ФСП ID не
        отвечает — `FspIdUnavailable`."""
        linking = _candidate(user) if intent == FspIntent.link else None
        authorization = FspAuthorization(
            state=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            nonce=secrets.token_urlsafe(32),
            intent=intent,
            user_id=linking.id if linking else None,
        )
        return FspStarted(self._provider.authorization_url(authorization), authorization)

    def complete(
        self,
        authorization: FspAuthorization | None,
        *,
        state: str | None,
        code: str | None,
        user: Account | None,
    ) -> SignedIn | None:
        """Возврат из ФСП ID. `state` сверяется с начатым входом: чужой или устаревший —
        `FspAuthorizationInvalid`; нет кода — вход отменён в ФСП ID, `FspIdRejected`. Привязка —
        только к учётке, которая её начала, и до обмена кода. Вход отдаёт учётку и токен входа,
        привязка — `None`."""
        if (
            authorization is None
            or state is None
            or not hmac.compare_digest(state.encode(), authorization.state.encode())
        ):
            raise FspAuthorizationInvalid()
        linking = None
        if authorization.intent == FspIntent.link:
            linking = _candidate(user)
            if linking.id != authorization.user_id:
                raise FspAuthorizationInvalid()
        if not code:
            raise FspIdRejected()
        identity = self._provider.identify(code, authorization)
        achievements = self._fetch(identity.sub)
        if linking is not None:
            self._link(linking, identity.sub, achievements)
            return None
        account = self._sign_in(identity, achievements)
        return SignedIn(account, self._sessions.issue(account.id, self._clock.now()))

    def status(self, user: Account) -> FspStatus:
        with self._uow:
            return self._status(user.id)

    def refresh(self, user: Account) -> FspStatus:
        """«Обновить достижения»: новый снимок из реестра. Реестр не ответил —
        `FspRegistryUnavailable`, прошлый снимок остаётся."""
        with self._uow:
            account = self._account(user.id)
        if account.fsp_id is None:
            raise FspNotLinked()
        achievements = self._registry.achievements(account.fsp_id)
        with self._uow:
            now = self._clock.now()
            self._fsp.save_snapshot(account.id, achievements, now)
            self._rebuild(account.id)
            return self._status(account.id)

    def unlink(self, user: Account) -> FspStatus:
        """Отвязка: снимок и наблюдения ФСП уходят из профиля, ID освобождается. Учётке без
        пароля отвязывать нельзя — она входит только через ФСП ID."""
        with self._uow:
            account = self._account(user.id)
            if account.fsp_id is None:
                raise FspNotLinked()
            if not account.has_password:
                raise FspUnlinkForbidden()
            self._accounts.unlink_fsp(account.id)
            self._fsp.delete_snapshot(account.id)
            self._rebuild(account.id)
            return self._status(account.id)

    def _sign_in(self, identity: FspIdentity, achievements: list[FspAchievement] | None) -> Account:
        with self._uow:
            now = self._clock.now()
            account = self._accounts.by_fsp_id(identity.sub)
            if account is None:
                account = self._register(identity)
            if account.role != Role.candidate:
                raise WrongRole()
            if achievements is not None:
                self._fsp.save_snapshot(account.id, achievements, now)
                self._rebuild(account.id)
            return account

    def _register(self, identity: FspIdentity) -> Account:
        """Новый ФСП ID — новая учётка кандидата. Адрес из ФСП ID должен быть подтверждён;
        занятый адрес не привязывается автоматически."""
        if not identity.email or not identity.email_verified:
            raise FspEmailUnverified()
        email = normalize_email(identity.email)
        if self._accounts.by_email(email) is not None:
            raise FspEmailTaken()
        try:
            return self._accounts.add_fsp(email, identity.sub, self._clock.now())
        except EmailTaken:
            raise FspEmailTaken() from None

    def _link(self, user: Account, fsp_id: str, achievements: list[FspAchievement] | None) -> None:
        with self._uow:
            account = self._account(user.id)
            owner = self._accounts.by_fsp_id(fsp_id)
            if owner is not None and owner.id != account.id:
                raise FspIdTaken()
            if account.fsp_id is not None and account.fsp_id != fsp_id:
                raise FspAlreadyLinked()
            if owner is None:
                self._accounts.link_fsp(account.id, fsp_id)
            if achievements is not None:
                self._fsp.save_snapshot(account.id, achievements, self._clock.now())
            self._rebuild(account.id)

    def _fetch(self, fsp_id: str) -> list[FspAchievement] | None:
        """Достижения из реестра; не ответил — `None`: вход и привязка идут дальше, остаётся
        прошлый снимок."""
        try:
            return self._registry.achievements(fsp_id)
        except FspRegistryUnavailable:
            log.warning("Реестр ФСП не ответил — остаётся прошлый снимок достижений")
            return None

    def _rebuild(self, user_id: uuid.UUID) -> None:
        rebuild_skill_profiles(
            self._attempts,
            self._tasks,
            self._fsp,
            self._model,
            self._mechanics,
            user_id,
            self._clock.now(),
        )

    def _status(self, user_id: uuid.UUID) -> FspStatus:
        account = self._account(user_id)
        if account.fsp_id is None:
            return FspStatus(None, account.has_password, None, ())
        history = self._fsp.history(user_id) or FspHistory((), None)
        evidence = fsp_evidence(self._attempts, self._fsp, user_id)
        found = (
            fsp_divergences(self._attempts, self._model, self._mechanics, user_id, evidence)
            if evidence is not None
            else []
        )
        return FspStatus(account.fsp_id, account.has_password, history, tuple(found))

    def _account(self, user_id: uuid.UUID) -> Account:
        account = self._accounts.get(user_id)
        if account is None:
            raise NotAuthenticated()
        return account


def _candidate(user: Account | None) -> Account:
    """ФСП ID привязывает только вошедший кандидат."""
    if user is None:
        raise NotAuthenticated()
    if user.role != Role.candidate:
        raise WrongRole()
    return user
