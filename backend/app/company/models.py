"""Профиль компании работодателя: кто приглашает. Одна учётка работодателя — одна компания."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.assessment.models import Industry
from app.db import Base


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

    industry: Mapped[Industry] = relationship()
