"""Профиль компании: описание, направление деятельности, контакты."""

from fastapi import APIRouter

from app.company import service
from app.company.models import Company
from app.company.schemas import CompanyIn, CompanyOut
from app.controller.deps import ClockDep
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.db import DbSession
from app.domain.errors import UnknownIndustry
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role

router = APIRouter(
    prefix="/api/employer/company",
    tags=["employer-company"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)


@router.get(
    "",
    summary="Профиль компании",
    description="`null` — профиль ещё не заполнен.",
)
def get_company(user: CurrentUser, db: DbSession) -> CompanyOut | None:
    company = service.get_company(db, user.id)
    return _company_out(company) if company else None


@router.put(
    "",
    summary="Заполнить или изменить профиль компании",
    responses=error_responses(UnknownIndustry),
)
def save_company(body: CompanyIn, user: CurrentUser, db: DbSession, clock: ClockDep) -> CompanyOut:
    return _company_out(service.save_company(db, user.id, body, clock))


def _company_out(company: Company) -> CompanyOut:
    return CompanyOut(
        name=company.name,
        industry=CatalogRef.model_validate(company.industry),
        description=company.description,
        website=company.website,
        contact_email=company.contact_email,
        contact_phone=company.contact_phone,
        updated_at=company.updated_at,
    )
