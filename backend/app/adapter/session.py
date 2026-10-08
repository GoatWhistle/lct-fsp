"""Токен входа — подписанный JWT, реализация порта `SessionTokens`."""

import uuid
from datetime import datetime, timedelta

import jwt

_ALGORITHM = "HS256"


class JwtSessions:
    """Подпись — секретом стенда, срок — `ttl` от момента выпуска."""

    def __init__(self, secret: str, ttl: timedelta) -> None:
        self._secret = secret
        self._ttl = ttl

    def issue(self, user_id: uuid.UUID, now: datetime) -> str:
        payload = {"sub": str(user_id), "iat": now, "exp": now + self._ttl}
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def read(self, token: str, now: datetime) -> uuid.UUID | None:
        try:
            # iat не проверяем: синхронизация отводит часы сервера назад на секунды, и только что
            # выданный токен оказался бы «из будущего». Срок держит exp — по переданному моменту,
            # а не по часам библиотеки; подлинность — подпись.
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={"require": ["exp"], "verify_iat": False, "verify_exp": False},
            )
            if now.timestamp() >= payload["exp"]:
                return None
            return uuid.UUID(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError, TypeError):
            return None
