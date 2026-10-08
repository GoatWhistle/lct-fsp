"""Хэширование паролей argon2 — реализация порта `PasswordHasher`."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError


class Argon2Passwords:
    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        # Параметры argon2 — у `hasher`; по умолчанию — рекомендованные библиотекой.
        self._hasher = hasher or PasswordHasher()
        # Хэш случайного пароля: проверка входа на неизвестный адрес идёт столько же, сколько на
        # известный, — по времени ответа не узнать, кто зарегистрирован.
        self._decoy = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        try:
            matches = self._hasher.verify(password_hash or self._decoy, password)
        except VerificationError:
            return False
        return matches and password_hash is not None
