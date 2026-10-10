"""Профиль компании: описание, направление деятельности, контакты и метка доверия — домен сайта,
подтверждённый письмом на адрес этого домена."""

from fastapi import APIRouter, status

from app.controller.company_schemas import CompanyIn, CompanyOut, DomainCheckIn, DomainConfirmIn
from app.controller.deps import ROLE_RESPONSES, CompaniesDep, CurrentUser, role_guard
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.domain.account import Role
from app.domain.company import Company, CompanyForm
from app.domain.errors import (
    CompanyProfileRequired,
    CompanyWebsiteRequired,
    DomainEmailMismatch,
    TokenExpired,
    TokenInvalid,
    UnknownIndustry,
)

router = APIRouter(
    prefix="/api/employer/company",
    tags=["employer-company"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

# Ссылку из письма открывает тот, кто читает корпоративную почту: вход не нужен.
domain_router = APIRouter(prefix="/api/company-domain", tags=["employer-company"])


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


@router.post(
    "/domain",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Подтвердить домен сайта компании",
    description="Письмо со ссылкой на адрес вида имя@домен-сайта. Метка добровольная: без неё "
    "все сценарии работают. Новая ссылка гасит прежние.",
    responses=error_responses(CompanyProfileRequired, CompanyWebsiteRequired, DomainEmailMismatch),
)
def request_domain_check(body: DomainCheckIn, user: CurrentUser, companies: CompaniesDep) -> None:
    companies.request_domain_check(user.id, body.email, body.locale)


@domain_router.post(
    "/confirm",
    summary="Подтверждение домена по токену из письма",
    responses=error_responses(TokenInvalid, TokenExpired),
)
def confirm_domain(body: DomainConfirmIn, companies: CompaniesDep) -> CompanyOut:
    return _company_out(companies.confirm_domain(body.token))


def _company_out(company: Company) -> CompanyOut:
    return CompanyOut(
        name=company.name,
        industry=CatalogRef.model_validate(company.industry),
        description=company.description,
        website=company.website,
        contact_email=company.contact_email,
        contact_phone=company.contact_phone,
        updated_at=company.updated_at,
        verified_domain=company.verified_domain,
        domain_verified=company.domain_verified,
    )
