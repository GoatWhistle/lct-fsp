"""Профили компаний в Postgres — реализация порта `CompanyRepository`. Изменения не
фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.company import Company, CompanyForm, CompanyLogo, CompanySize, DomainVerification
from app.repository.catalog import ref_of
from app.repository.orm.company import Company as CompanyRow
from app.repository.orm.company import CompanyDomainVerification as VerificationRow


class SqlCompanies:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID) -> Company | None:
        row = self._session.get(CompanyRow, user_id, populate_existing=True)
        if row is None:
            return None
        return Company(
            name=row.name,
            industry=ref_of(row.industry),
            description=row.description,
            website=row.website,
            contact_email=row.contact_email,
            contact_phone=row.contact_phone,
            updated_at=row.updated_at,
            verified_domain=row.verified_domain,
            domain_verified_at=row.domain_verified_at,
            size=CompanySize(row.size) if row.size else None,
            it_accredited=row.it_accredited,
            benefits=tuple(row.benefits),
            links=tuple(row.links),
            fsp_partner=row.fsp_partner,
            logo_updated_at=row.logo_updated_at,
        )

    def save(self, user_id: uuid.UUID, form: CompanyForm, now: datetime) -> None:
        fields = {
            "name": form.name,
            "industry_code": form.industry,
            "description": form.description,
            "website": form.website,
            "contact_email": form.contact_email,
            "contact_phone": form.contact_phone,
            "size": form.size.value if form.size else None,
            "it_accredited": form.it_accredited,
            "benefits": list(form.benefits),
            "links": list(form.links),
            "updated_at": now,
        }
        # Одной вставкой с заменой: двойное «Сохранить» при первом заполнении не упрётся в ключ.
        stmt = pg_insert(CompanyRow).values(user_id=user_id, **fields)
        self._session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=fields))

    def add_domain_verification(self, verification: DomainVerification) -> None:
        self._session.execute(
            delete(VerificationRow).where(VerificationRow.user_id == verification.user_id)
        )
        self._session.add(
            VerificationRow(
                token_hash=verification.token_hash,
                user_id=verification.user_id,
                email=verification.email,
                domain=verification.domain,
                created_at=verification.created_at,
                expires_at=verification.expires_at,
            )
        )
        self._session.flush()

    def domain_verification(self, token_hash: str) -> DomainVerification | None:
        row = self._session.get(VerificationRow, token_hash)
        if row is None:
            return None
        return DomainVerification(
            row.user_id, row.email, row.domain, row.token_hash, row.created_at, row.expires_at
        )

    def mark_domain_verified(self, user_id: uuid.UUID, domain: str, now: datetime) -> None:
        self._session.execute(
            update(CompanyRow)
            .where(CompanyRow.user_id == user_id)
            .values(verified_domain=domain, domain_verified_at=now)
        )
        self._session.execute(delete(VerificationRow).where(VerificationRow.user_id == user_id))

    def logo(self, user_id: uuid.UUID) -> CompanyLogo | None:
        row = self._session.get(CompanyRow, user_id, populate_existing=True)
        if row is None or row.logo is None or row.logo_type is None:
            return None
        assert row.logo_updated_at is not None, "логотип без времени загрузки"
        return CompanyLogo(row.logo, row.logo_type, row.logo_updated_at)

    def save_logo(self, user_id: uuid.UUID, logo: CompanyLogo | None) -> None:
        self._session.execute(
            update(CompanyRow)
            .where(CompanyRow.user_id == user_id)
            .values(
                logo=logo.content if logo else None,
                logo_type=logo.media_type if logo else None,
                logo_updated_at=logo.updated_at if logo else None,
            )
        )

    def mark_fsp_partner(self, user_id: uuid.UUID, partner: bool) -> None:
        self._session.execute(
            update(CompanyRow).where(CompanyRow.user_id == user_id).values(fsp_partner=partner)
        )
