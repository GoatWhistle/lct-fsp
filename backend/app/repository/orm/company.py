"""Профиль компании работодателя: кто приглашает. Одна учётка работодателя — одна компания."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repository.database import Base
from app.repository.orm.catalog import Industry


class Company(Base):
    __tablename__ = "companies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # Сфера деятельности — из того же справочника, что интересные сферы кандидата.
    industry_code: Mapped[str] = mapped_column(ForeignKey("industries.code"))
    description: Mapped[str] = mapped_column(String(3000))
    website: Mapped[str | None] = mapped_column(String(300))
    contact_email: Mapped[str] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime]
    # Метка доверия: домен, подтверждённый письмом на адрес этого домена, и когда.
    verified_domain: Mapped[str | None] = mapped_column(String(253))
    domain_verified_at: Mapped[datetime | None]
    size: Mapped[str | None] = mapped_column(String(16))
    it_accredited: Mapped[bool] = mapped_column(Boolean, server_default="false")
    benefits: Mapped[list[str]] = mapped_column(ARRAY(String(32)), server_default="{}")
    links: Mapped[list[str]] = mapped_column(ARRAY(String(300)), server_default="{}")
    fsp_partner: Mapped[bool] = mapped_column(Boolean, server_default="false")
    logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_type: Mapped[str | None] = mapped_column(String(32))
    logo_updated_at: Mapped[datetime | None]

    industry: Mapped[Industry] = relationship()


class CompanyDomainVerification(Base):
    """Ссылка подтверждения домена компании: хранится хэш токена, сам токен — только в письме."""

    __tablename__ = "company_domain_verifications"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.user_id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    domain: Mapped[str] = mapped_column(String(253))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
