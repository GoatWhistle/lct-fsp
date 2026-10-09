"""Учётки и выданные подтверждения адреса."""

import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.account import Role
from app.repository.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Храним в нижнем регистре: один адрес — одна учётка.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    # Нет у учётки, созданной входом через ФСП ID: она входит только через него.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, create_constraint=True, length=16, name="role")
    )
    email_verified_at: Mapped[datetime | None]
    # ФСП ID — `sub` из ФСП ID; один ID — одна учётка.
    fsp_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime]
    # Тестовая учётка режима жюри: в выдаче и поиске реальных работодателей её нет.
    is_demo: Mapped[bool] = mapped_column(default=False, server_default="false")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # В базе только хэш: утечка таблицы не даёт подтвердить чужой адрес.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime]
