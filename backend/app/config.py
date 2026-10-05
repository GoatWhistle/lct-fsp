"""Конфигурация: окружение стенда и параметры механик.

`Settings` — где что лежит (БД, почта, секреты, адреса); читается из переменных окружения
и `.env`. `Mechanics` — как ведут себя механики (сроки, пороги, лимиты); читается из
YAML-файла в репо, чтобы прогон стенда валидации фиксировал параметры вместе с кодом.
Новая механика добавляет свой раздел в `Mechanics` и в `config/mechanics.yaml`.
"""

from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://lct:lct@localhost:5432/lct"
    # Подпись входа; на стенде — своя случайная строка (`openssl rand -hex 32`).
    secret_key: str = Field(default="dev-only-secret-key-change-me-on-deploy", min_length=32)
    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "Подбор ФСП <no-reply@lct.local>"

    mechanics_file: Path = BACKEND_DIR / "config" / "mechanics.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IdentityMechanics(_Section):
    email_token_ttl_hours: int = Field(gt=0, description="Срок жизни ссылки подтверждения")
    session_ttl_hours: int = Field(gt=0, description="Срок жизни входа")


class Mechanics(_Section):
    identity: IdentityMechanics

    @classmethod
    def from_yaml(cls, path: Path) -> "Mechanics":
        with path.open(encoding="utf-8") as f:
            return cls.model_validate(yaml.safe_load(f))


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_mechanics(request: Request) -> Mechanics:
    mechanics: Mechanics = request.app.state.mechanics
    return mechanics


SettingsDep = Annotated[Settings, Depends(get_settings)]
MechanicsDep = Annotated[Mechanics, Depends(get_mechanics)]
