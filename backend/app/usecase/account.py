"""Сценарии учётки: регистрация, подтверждение адреса, вход и учётка по токену входа.

Правила — в `app.domain.account`; хэширование паролей, токен входа, почта и время — за портами.
Письмо уходит после фиксации: ссылка в нём уже записана.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.account import (
    Account,
    Role,
    check_verification,
    issue_verification,
    normalize_email,
    sign_in,
    verification_token_hash,
)
from app.domain.errors import EmailTaken, NotAuthenticated
from app.domain.locale import DEFAULT_LOCALE, Locale
from app.domain.mail import Mail
from app.usecase.interface import (
    AccountRepository,
    Clock,
    EmailVerificationRepository,
    Mailer,
    MailTemplates,
    PasswordHasher,
    SessionTokens,
    UnitOfWork,
)


@dataclass(frozen=True)
class VerificationLinks:
    """Ссылка подтверждения в письме: адрес фронта и срок ссылки."""

    frontend_url: str
    ttl_hours: int


@dataclass(frozen=True)
class SignedIn:
    account: Account
    session_token: str


class Accounts:
    def __init__(
        self,
        uow: UnitOfWork,
        accounts: AccountRepository,
        verifications: EmailVerificationRepository,
        passwords: PasswordHasher,
        sessions: SessionTokens,
        mailer: Mailer,
        clock: Clock,
        links: VerificationLinks,
        templates: MailTemplates,
    ) -> None:
        self._uow = uow
        self._accounts = accounts
        self._verifications = verifications
        self._passwords = passwords
        self._sessions = sessions
        self._mailer = mailer
        self._clock = clock
        self._links = links
        self._templates = templates

    def register(
        self, email: str, password: str, role: Role, locale: Locale = DEFAULT_LOCALE
    ) -> Account:
        """Учётка выбранной роли и письмо со ссылкой подтверждения; адрес занят — `EmailTaken`."""
        email = normalize_email(email)
        # Хэш — до транзакции: argon2 долгий, соединение с базой на это время не занимается.
        password_hash = self._passwords.hash(password)
        with self._uow:
            if self._accounts.by_email(email) is not None:
                raise EmailTaken()
            now = self._clock.now()
            account = self._accounts.add(email, password_hash, role, now)
            mail = self._verification(account, now, locale)
        self._mailer.send(mail)
        return account

    def resend_verification(self, email: str, locale: Locale = DEFAULT_LOCALE) -> None:
        """Для чужих и уже подтверждённых адресов молча ничего не делает — не раскрываем учётки."""
        with self._uow:
            account = self._accounts.by_email(normalize_email(email))
            if account is None or account.email_verified:
                return
            mail = self._verification(account, self._clock.now(), locale)
        self._mailer.send(mail)

    def verify_email(self, token: str) -> Account:
        with self._uow:
            found = self._verifications.by_hash(verification_token_hash(token))
            now = self._clock.now()
            verification = check_verification(found, now)
            account = self._accounts.mark_verified(verification.user_id, now)
            self._verifications.revoke(account.id)
            return account

    def sign_in(self, email: str, password: str) -> SignedIn:
        """Вход: учётка и токен входа со сроком от текущего момента."""
        with self._uow:
            credentials = self._accounts.credentials(normalize_email(email))
        password_hash = credentials.password_hash if credentials else None
        account = sign_in(credentials, self._passwords.verify(password_hash, password))
        return SignedIn(account, self._sessions.issue(account.id, self._clock.now()))

    def session_account(self, token: str | None) -> Account:
        """Учётка по токену входа; подделанный, истёкший или чужой токен — `NotAuthenticated`."""
        user_id: uuid.UUID | None = None
        if token:
            user_id = self._sessions.read(token, self._clock.now())
        with self._uow:
            account = self._accounts.get(user_id) if user_id else None
        if account is None:
            raise NotAuthenticated()
        return account

    def _verification(self, account: Account, now: datetime, locale: Locale) -> Mail:
        token = secrets.token_urlsafe(32)
        ttl_hours = self._links.ttl_hours
        self._verifications.add(
            issue_verification(account.id, token, now, timedelta(hours=ttl_hours))
        )
        link = f"{self._links.frontend_url}/verify-email?token={token}"
        return self._templates.verification(account.email, link, ttl_hours, locale)
