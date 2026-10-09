"""Схемы API учётки."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.account import Role
from app.domain.locale import DEFAULT_LOCALE, Locale


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Не короче 8 символов")
    role: Role = Field(description="Кандидат или работодатель; сменить потом нельзя")
    locale: Locale = Field(default=DEFAULT_LOCALE, description="Язык письма подтверждения")


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=1, max_length=128, description="Токен из ссылки в письме")


class ResendVerificationIn(BaseModel):
    email: EmailStr
    locale: Locale = Field(default=DEFAULT_LOCALE, description="Язык письма подтверждения")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
    demo: bool = Field(
        default=False, description="Тестовая учётка режима жюри: ей доступен экспресс-тест"
    )
