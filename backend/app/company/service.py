import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assessment.models import Industry
from app.company.models import Company
from app.company.schemas import CompanyIn
from app.db import utcnow
from app.domain.errors import UnknownIndustry
from app.repository.unit_of_work import SqlUnitOfWork


def get_company(db: Session, user_id: uuid.UUID) -> Company | None:
    return db.get(Company, user_id)


def save_company(uow: SqlUnitOfWork, user_id: uuid.UUID, data: CompanyIn) -> Company:
    with uow:
        db = uow.session
        if db.get(Industry, data.industry) is None:
            raise UnknownIndustry()
        fields = {
            "name": data.name,
            "industry_code": data.industry,
            "description": data.description,
            "website": data.website,
            "contact_email": data.contact_email,
            "contact_phone": data.contact_phone,
            "updated_at": utcnow(),
        }
        # Одной вставкой с заменой: двойное «Сохранить» при первом заполнении не упрётся в ключ.
        stmt = pg_insert(Company).values(user_id=user_id, **fields)
        db.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=fields))
        return db.get_one(Company, user_id, populate_existing=True)
