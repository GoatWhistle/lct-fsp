import uuid

from sqlalchemy.orm import Session

from app.assessment.models import Industry
from app.assessment.service import UnknownIndustry
from app.company.models import Company
from app.company.schemas import CompanyIn


def get_company(db: Session, user_id: uuid.UUID) -> Company | None:
    return db.get(Company, user_id)


def save_company(db: Session, user_id: uuid.UUID, data: CompanyIn) -> Company:
    if db.get(Industry, data.industry) is None:
        raise UnknownIndustry()
    company = db.get(Company, user_id) or Company(user_id=user_id)
    company.name = data.name
    company.industry_code = data.industry
    company.description = data.description
    company.website = data.website
    company.contact_email = data.contact_email
    company.contact_phone = data.contact_phone
    db.add(company)
    db.commit()
    return company
