"""Учётки и ссылки подтверждения адреса в Postgres — реализации портов `AccountRepository` и
`EmailVerificationRepository`. Изменения не фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.account import Account, Credentials, EmailVerification, Role
from app.domain.errors import EmailTaken, FspIdTaken
from app.repository.orm.account import EmailVerificationToken, User


def _account_of(row: User) -> Account:
    return Account(
        row.id,
        row.email,
        row.role,
        row.email_verified_at,
        fsp_id=row.fsp_id,
        has_password=row.password_hash is not None,
    )


class SqlAccounts:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID) -> Account | None:
        row = self._session.get(User, user_id)
        return _account_of(row) if row else None

    def by_email(self, email: str) -> Account | None:
        row = self._row(email)
        return _account_of(row) if row else None

    def credentials(self, email: str) -> Credentials | None:
        row = self._row(email)
        return Credentials(_account_of(row), row.password_hash) if row else None

    def add(self, email: str, password_hash: str, role: Role, now: datetime) -> Account:
        row = User(email=email, password_hash=password_hash, role=role, created_at=now)
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            # Тот же адрес успел зарегистрироваться параллельным запросом.
            raise EmailTaken() from None
        return _account_of(row)

    def by_fsp_id(self, fsp_id: str) -> Account | None:
        row = self._session.scalar(select(User).where(User.fsp_id == fsp_id))
        return _account_of(row) if row else None

    def add_fsp(self, email: str, fsp_id: str, now: datetime) -> Account:
        row = User(
            email=email,
            password_hash=None,
            role=Role.candidate,
            email_verified_at=now,
            fsp_id=fsp_id,
            created_at=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            # Адрес или ФСП ID заняли параллельным запросом — разбираемся, что именно.
            if self._row(email) is not None:
                raise EmailTaken() from None
            raise FspIdTaken() from None
        return _account_of(row)

    def link_fsp(self, user_id: uuid.UUID, fsp_id: str) -> Account:
        row = self._session.get_one(User, user_id)
        try:
            with self._session.begin_nested():
                row.fsp_id = fsp_id
                self._session.flush()
        except IntegrityError:
            # Тот же ФСП ID успели привязать к другой учётке параллельным запросом.
            self._session.refresh(row)
            raise FspIdTaken() from None
        return _account_of(row)

    def unlink_fsp(self, user_id: uuid.UUID) -> Account:
        row = self._session.get_one(User, user_id)
        row.fsp_id = None
        self._session.flush()
        return _account_of(row)

    def mark_verified(self, user_id: uuid.UUID, now: datetime) -> Account:
        row = self._session.get_one(User, user_id)
        row.email_verified_at = now
        return _account_of(row)

    def _row(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))


class SqlEmailVerifications:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, verification: EmailVerification) -> None:
        self._session.add(
            EmailVerificationToken(
                user_id=verification.user_id,
                token_hash=verification.token_hash,
                created_at=verification.created_at,
                expires_at=verification.expires_at,
            )
        )

    def by_hash(self, token_hash: str) -> EmailVerification | None:
        row = self._session.scalar(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        if row is None:
            return None
        return EmailVerification(row.user_id, row.token_hash, row.created_at, row.expires_at)

    def revoke(self, user_id: uuid.UUID) -> None:
        self._session.execute(
            delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
        )
