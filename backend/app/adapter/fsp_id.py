"""ФСП ID — реализации порта `FspIdProvider`.

`OidcFspId` — OpenID Connect: authorization code + PKCE (S256), конфиденциальный клиент. Адреса
берутся из discovery при каждом входе: недоступный ФСП ID виден сразу, а не после ухода браузера на
мёртвую страницу. ID-токен проверяется по ключам ФСП ID: подпись, `iss`, `aud`, срок и `nonce`
входа. Сейчас за ним — локальный Keycloak, который изображает ФСП ID; настоящий ФСП ID — смена
адреса и ключей в настройках.

`server_url` — адрес, по которому до ФСП ID ходит сам бэкенд, если он не совпадает с
публичным `issuer`: в docker compose браузер видит Keycloak на `localhost`, а бэкенд — по имени
сервиса.
"""

import secrets
from typing import cast

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.httpx_client import OAuth2Client
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, KeySetSerialization

from app.domain.errors import FspIdRejected, FspIdUnavailable
from app.domain.fsp import FspAuthorization, FspIdentity

_ENDPOINTS = ("authorization_endpoint", "token_endpoint", "jwks_uri")
# Расхождение часов бэкенда и ФСП ID, которое прощается при проверке срока токена, с.
_CLOCK_LEEWAY_SECONDS = 60


class OidcFspId:
    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        server_url: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._server_url = (server_url or issuer).rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout_seconds

    def authorization_url(self, authorization: FspAuthorization) -> str:
        endpoint = self._metadata()["authorization_endpoint"]
        with self._client() as client:
            url, _ = client.create_authorization_url(
                endpoint,
                state=authorization.state,
                code_verifier=authorization.code_verifier,
                nonce=authorization.nonce,
            )
        return str(url)

    def identify(self, code: str, authorization: FspAuthorization) -> FspIdentity:
        metadata = self._metadata()
        try:
            with self._client() as client:
                token = client.fetch_token(
                    metadata["token_endpoint"],
                    code=code,
                    code_verifier=authorization.code_verifier,
                )
                keys = client.get(metadata["jwks_uri"])
                keys.raise_for_status()
                jwks = keys.json()
        except (httpx.HTTPError, ValueError) as error:
            raise FspIdUnavailable() from error
        except AuthlibBaseError as error:
            # Код истёк, уже обменян или выдан другому входу.
            raise FspIdRejected() from error
        return self._identity(token.get("id_token"), jwks, authorization.nonce)

    def _identity(self, id_token: object, jwks: object, nonce: str) -> FspIdentity:
        if not isinstance(id_token, str) or not isinstance(jwks, dict):
            raise FspIdRejected()
        try:
            decoded = jwt.decode(id_token, KeySet.import_key_set(cast(KeySetSerialization, jwks)))
            jwt.JWTClaimsRegistry(
                leeway=_CLOCK_LEEWAY_SECONDS,
                iss={"essential": True, "value": self._issuer},
                aud={"essential": True, "value": self._client_id},
                sub={"essential": True},
                exp={"essential": True},
                nonce={"essential": True, "value": nonce},
            ).validate(decoded.claims)
        except (JoseError, ValueError, KeyError, TypeError) as error:
            # Подпись, срок, издатель, получатель или nonce не те — или ключи ФСП ID испорчены.
            raise FspIdRejected() from error
        claims = decoded.claims
        email = claims.get("email")
        return FspIdentity(
            sub=str(claims["sub"]),
            email=email if isinstance(email, str) else None,
            email_verified=claims.get("email_verified") is True,
        )

    def _metadata(self) -> dict[str, str]:
        """Адреса из discovery; ФСП ID не ответил или ответил не discovery — `FspIdUnavailable`."""
        url = f"{self._server_url}/.well-known/openid-configuration"
        try:
            response = httpx.get(url, timeout=self._timeout)
            response.raise_for_status()
            found = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise FspIdUnavailable() from error
        if not isinstance(found, dict):
            raise FspIdUnavailable()
        metadata = {key: found.get(key) for key in _ENDPOINTS}
        if not all(isinstance(value, str) for value in metadata.values()):
            raise FspIdUnavailable()
        return cast(dict[str, str], metadata)

    def _client(self) -> OAuth2Client:
        return OAuth2Client(
            client_id=self._client_id,
            client_secret=self._client_secret,
            scope="openid email profile",
            redirect_uri=self._redirect_uri,
            code_challenge_method="S256",
            timeout=self._timeout,
        )


class MemoryFspId:
    """ФСП ID в памяти для тестов: тест выдаёт код за участника — `issue`, `available = False` —
    ФСП ID не отвечает. Код привязан к `state` своего входа, как PKCE привязывает его к
    `code_verifier`: чужому входу он не подойдёт."""

    def __init__(self) -> None:
        self.available = True
        self._codes: dict[str, tuple[FspIdentity, str]] = {}

    def issue(self, identity: FspIdentity, state: str) -> str:
        code = secrets.token_urlsafe(16)
        self._codes[code] = (identity, state)
        return code

    def authorization_url(self, authorization: FspAuthorization) -> str:
        if not self.available:
            raise FspIdUnavailable()
        return f"https://fsp-id.test/auth?state={authorization.state}"

    def identify(self, code: str, authorization: FspAuthorization) -> FspIdentity:
        if not self.available:
            raise FspIdUnavailable()
        identity, state = self._codes.pop(code, (None, ""))
        if identity is None or state != authorization.state:
            raise FspIdRejected()
        return identity
