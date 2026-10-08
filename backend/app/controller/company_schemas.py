"""Схемы API профиля компании."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, HttpUrl, StringConstraints, field_validator

from app.controller.schemas import CatalogRef


def _text(min_length: int, max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


class CompanyIn(BaseModel):
    name: Annotated[str, _text(1, 200)]
    industry: str = Field(description="Сфера деятельности — код из `/api/catalog/industries`")
    description: Annotated[str, _text(1, 3000)] = Field(description="Чем занимается компания")
    website: Annotated[str, _text(0, 300)] | None = Field(
        default=None, description="Без схемы адрес дополняется `https://`"
    )
    contact_email: EmailStr
    contact_phone: Annotated[str, _text(0, 32)] | None = None

    @field_validator("website")
    @classmethod
    def website_is_http_url(cls, value: str | None) -> str | None:
        """Хранится адрес как его ввели, со схемой: HttpUrl перевёл бы домен .рф в punycode."""
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")):
            value = f"https://{value}"
        url = HttpUrl(value)
        if not url.host or "." not in url.host or url.username or url.password:
            raise ValueError("адрес сайта вида example.ru")
        if len(value) > 300:
            raise ValueError("адрес сайта длиннее 300 символов")
        return value

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
