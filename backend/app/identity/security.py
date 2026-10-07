import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def new_email_token() -> tuple[str, str]:
    """Токен для ссылки в письме и его хэш для базы."""
    token = secrets.token_urlsafe(32)
    return token, hash_email_token(token)


def hash_email_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_access_token(user_id: uuid.UUID, secret: str, ttl: timedelta, now: datetime) -> str:
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def read_access_token(token: str, secret: str, now: datetime) -> uuid.UUID | None:
    try:
        # iat не проверяем: синхронизация отводит часы сервера назад на секунды, и только что
        # выданный токен оказался бы «из будущего». Срок держит exp — по переданному моменту, а
        # не по часам библиотеки; подлинность — подпись.
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"require": ["exp"], "verify_iat": False, "verify_exp": False},
        )
        if now.timestamp() >= payload["exp"]:
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
