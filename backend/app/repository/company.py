"""Профили компаний в Postgres — реализация порта `CompanyRepository`. Изменения не
фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.company import Company, CompanyForm
from app.repository.catalog import ref_of
from app.repository.orm.company import Company as CompanyRow


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
        )

    def save(self, user_id: uuid.UUID, form: CompanyForm, now: datetime) -> None:
        fields = {
            "name": form.name,
            "industry_code": form.industry,
            "description": form.description,
            "website": form.website,
            "contact_email": form.contact_email,
            "contact_phone": form.contact_phone,
            "updated_at": now,
        }
        # Одной вставкой с заменой: двойное «Сохранить» при первом заполнении не упрётся в ключ.
        stmt = pg_insert(CompanyRow).values(user_id=user_id, **fields)
        self._session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=fields))
