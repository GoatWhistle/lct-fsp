"""Профиль компании работодателя: кто приглашает. Одна учётка работодателя — одна компания."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.catalog import CatalogRef


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
