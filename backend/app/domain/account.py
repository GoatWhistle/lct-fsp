"""Учётки: роль, подтверждение адреса и вход по email и паролю.

Адрес хранится в нижнем регистре: один адрес — одна учётка. Войти можно только с подтверждённым
адресом. Подтверждение — одноразовая ссылка со сроком: в хранилище лежит только хэш токена,
утечка таблицы не даёт подтвердить чужой адрес; подтверждение гасит все ссылки учётки.
"""

import enum
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.errors import EmailNotVerified, InvalidCredentials, TokenExpired, TokenInvalid
from app.domain.mail import Mail


class Role(enum.StrEnum):
    candidate = "candidate"
    employer = "employer"


def normalize_email(email: str) -> str:
    return email.lower()


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    email: str
    role: Role
    email_verified_at: datetime | None

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


@dataclass(frozen=True)
class Credentials:
    """Учётка с хэшем пароля — только для проверки входа."""

    account: Account
    password_hash: str


def sign_in(credentials: Credentials | None, password_matches: bool) -> Account:
    """Вход: неверный пароль и неизвестный адрес неразличимы; про подтверждение адреса
    говорится только тому, кто знает пароль."""
    if credentials is None or not password_matches:
        raise InvalidCredentials()
    if not credentials.account.email_verified:
        raise EmailNotVerified()
    return credentials.account


@dataclass(frozen=True)
class EmailVerification:
    """Выданная ссылка подтверждения адреса: хэш токена и срок."""

    user_id: uuid.UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime


def verification_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_verification(
    user_id: uuid.UUID, token: str, now: datetime, ttl: timedelta
) -> EmailVerification:
    return EmailVerification(user_id, verification_token_hash(token), now, now + ttl)


def check_verification(found: EmailVerification | None, now: datetime) -> EmailVerification:
    """Ссылка, по которой можно подтвердить адрес: неизвестная или уже использованная —
    `TokenInvalid`, истёкшая — `TokenExpired`."""
    if found is None:
        raise TokenInvalid()
    if now >= found.expires_at:
        raise TokenExpired()
    return found


def verification_mail(email: str, link: str, ttl_hours: int) -> Mail:
    return Mail(
        to=email,
        subject="Подтвердите адрес почты",
        text=(
            "Здравствуйте!\n\n"
            "Чтобы завершить регистрацию, откройте ссылку:\n"
            f"{link}\n\n"
            f"Ссылка действует {ttl_hours} ч. Если вы не регистрировались — "
            "просто удалите письмо.\n"
        ),
    )
