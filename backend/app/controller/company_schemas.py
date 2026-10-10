"""Схемы API профиля компании."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, HttpUrl, StringConstraints, field_validator

from app.controller.schemas import CatalogRef
from app.domain.company import BENEFITS, MAX_LINKS, CompanySize
from app.domain.locale import DEFAULT_LOCALE, Locale


def _text(min_length: int, max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


def http_address(value: str) -> str:
    """Адрес как его ввели, со схемой: HttpUrl перевёл бы домен .рф в punycode."""
    if not value.lower().startswith(("http://", "https://")):
        value = f"https://{value}"
    url = HttpUrl(value)
    if not url.host or "." not in url.host or url.username or url.password:
        raise ValueError("адрес вида example.ru")
    if len(value) > 300:
        raise ValueError("адрес длиннее 300 символов")
    return value


class CompanyIn(BaseModel):
    name: Annotated[str, _text(1, 200)]
    industry: str = Field(description="Сфера деятельности — код из `/api/catalog/industries`")
    description: Annotated[str, _text(1, 3000)] = Field(description="Чем занимается компания")
    website: Annotated[str, _text(0, 300)] | None = Field(
        default=None, description="Без схемы адрес дополняется `https://`"
    )
    contact_email: EmailStr
    contact_phone: Annotated[str, _text(0, 32)] | None = None
    size: CompanySize | None = Field(default=None, description="Сколько человек — диапазоном")
    it_accredited: bool = Field(default=False, description="Аккредитованная ИТ-компания")
    benefits: list[str] = Field(
        default_factory=list, description=f"Что даёт сверх зарплаты: {', '.join(BENEFITS)}"
    )
    links: list[Annotated[str, _text(1, 300)]] = Field(
        default_factory=list,
        max_length=MAX_LINKS,
        description="Соцсети и блоги; площадку фронт узнаёт по адресу",
    )

    @field_validator("website")
    @classmethod
    def website_is_http_url(cls, value: str | None) -> str | None:
        return http_address(value) if value else None

    @field_validator("benefits")
    @classmethod
    def benefits_are_known(cls, value: list[str]) -> list[str]:
        unknown = [code for code in value if code not in BENEFITS]
        if unknown:
            raise ValueError(f"неизвестные бенефиты: {', '.join(unknown)}")
        return list(dict.fromkeys(value))

    @field_validator("links")
    @classmethod
    def links_are_http_urls(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(http_address(link) for link in value))

    @field_validator("contact_email")
    @classmethod
    def email_is_lowercase(cls, value: str) -> str:
        return value.lower()

    @field_validator("contact_phone")
    @classmethod
    def empty_phone_is_none(cls, value: str | None) -> str | None:
        return value or None


class CompanyOut(BaseModel):
    name: str
    industry: CatalogRef
    description: str
    website: str | None
    contact_email: str
    contact_phone: str | None
    updated_at: datetime
    verified_domain: str | None = Field(
        description="Домен, подтверждённый письмом на адрес этого домена; `null` — не подтверждали"
    )
    domain_verified: bool = Field(
        description="Метка доверия: подтверждённый домен совпадает с доменом сайта компании"
    )

    size: CompanySize | None
    it_accredited: bool
    benefits: list[str]
    links: list[str]
    fsp_partner: bool = Field(description="Партнёр ФСП — отмечает федерация, не работодатель")
    logo_url: str | None = Field(description="Логотип; `null` — не загружен")


class DomainCheckIn(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
        description="Адрес на домене сайта компании, например hr@acme.ru",
    )
    locale: Locale = Field(default=DEFAULT_LOCALE, description="Язык письма")


class DomainConfirmIn(BaseModel):
    token: str = Field(min_length=1, max_length=200, description="Токен из письма")
