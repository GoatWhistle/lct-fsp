import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.identity.models import Role


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Не короче 8 символов")
    role: Role = Field(description="Кандидат или работодатель; сменить потом нельзя")


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=1, max_length=128, description="Токен из ссылки в письме")


class ResendVerificationIn(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
