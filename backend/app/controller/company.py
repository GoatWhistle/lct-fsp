"""Профиль компании: описание, направление деятельности, контакты."""

from fastapi import APIRouter

from app.controller.company_schemas import CompanyIn, CompanyOut
from app.controller.deps import ROLE_RESPONSES, CompaniesDep, CurrentUser, role_guard
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.domain.account import Role
from app.domain.company import Company, CompanyForm
from app.domain.errors import UnknownIndustry

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
def get_company(user: CurrentUser, companies: CompaniesDep) -> CompanyOut | None:
    company = companies.get(user.id)
    return _company_out(company) if company else None


@router.put(
    "",
    summary="Заполнить или изменить профиль компании",
    responses=error_responses(UnknownIndustry),
)
def save_company(body: CompanyIn, user: CurrentUser, companies: CompaniesDep) -> CompanyOut:
    form = CompanyForm(
        name=body.name,
        industry=body.industry,
        description=body.description,
        website=body.website,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
    )
    return _company_out(companies.save(user.id, form))


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
