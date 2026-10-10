"""Профиль компании работодателя: кто приглашает. Одна учётка работодателя — одна компания.

Метка доверия — домен сайта компании, подтверждённый письмом на адрес этого домена (mechanics.md,
§14). Метка добровольная: без неё все сценарии работают. Подтверждён домен, а не сайт: смена сайта
на другой домен метку снимает, пока новый домен не подтвердят.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from app.domain.catalog import CatalogRef
from app.domain.errors import (
    CompanyWebsiteRequired,
    DomainEmailMismatch,
    TokenExpired,
    TokenInvalid,
)


@dataclass(frozen=True)
class CompanyForm:
    name: str
    # Сфера деятельности — код из того же справочника, что интересные сферы кандидата.
    industry: str
    description: str
    website: str | None
    contact_email: str
    contact_phone: str | None


@dataclass(frozen=True)
class Company:
    name: str
    industry: CatalogRef
    description: str
    website: str | None
    contact_email: str
    contact_phone: str | None
    updated_at: datetime
    # Подтверждённый письмом домен и когда; метка — только пока он совпадает с доменом сайта.
    verified_domain: str | None = None
    domain_verified_at: datetime | None = None

    @property
    def domain_verified(self) -> bool:
        return self.verified_domain is not None and self.verified_domain == site_domain(
            self.website
        )


@dataclass(frozen=True)
class DomainVerification:
    """Выданная ссылка подтверждения домена: адрес, домен, хэш токена и срок."""

    user_id: uuid.UUID
    email: str
    domain: str
    token_hash: str
    created_at: datetime
    expires_at: datetime


def site_domain(website: str | None) -> str | None:
    """Домен сайта без `www.` и порта, в нижнем регистре; адрес без схемы тоже понимается."""
    if not website or not website.strip():
        return None
    raw = website.strip()
    host = urlsplit(raw if "://" in raw else f"//{raw}").hostname
    if not host or "." not in host:
        return None
    host = host.lower().rstrip(".")
    return host.removeprefix("www.")


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower().rstrip(".")


def check_domain_email(email: str, website: str | None) -> str:
    """Домен, который подтвердит письмо на `email`. Адрес — на домене сайта или на домене, чей
    поддомен — сайт (`hr@acme.ru` для `careers.acme.ru`); иначе `DomainEmailMismatch`. Без сайта —
    `CompanyWebsiteRequired`."""
    domain = site_domain(website)
    if domain is None:
        raise CompanyWebsiteRequired()
    mail = email_domain(email)
    if "@" not in email or "." not in mail:
        raise DomainEmailMismatch()
    if domain != mail and not domain.endswith(f".{mail}"):
        raise DomainEmailMismatch()
    return domain


def domain_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_domain_verification(
    user_id: uuid.UUID, email: str, domain: str, token: str, now: datetime, ttl: timedelta
) -> DomainVerification:
    return DomainVerification(
        user_id, email.strip().lower(), domain, domain_token_hash(token), now, now + ttl
    )


def check_domain_verification(
    found: DomainVerification | None, now: datetime
) -> DomainVerification:
    if found is None:
        raise TokenInvalid()
    if now >= found.expires_at:
        raise TokenExpired()
    return found
