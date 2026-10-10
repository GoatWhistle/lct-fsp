"""Профиль компании: описание, направление деятельности, условия, ссылки, логотип, контакты и
метка доверия — домен сайта, подтверждённый письмом на адрес этого домена."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.controller.company_schemas import CompanyIn, CompanyOut, DomainCheckIn, DomainConfirmIn
from app.controller.deps import ROLE_RESPONSES, CompaniesDep, CurrentUser, role_guard
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.domain import errors
from app.domain.account import Role
from app.domain.company import LOGO_MAX_BYTES, LOGO_TYPES, Company, CompanyForm
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
logos = APIRouter(prefix="/api/companies", tags=["employer-company"])


@router.get(
    "",
    summary="Профиль компании",
    description="`null` — профиль ещё не заполнен.",
)
def get_company(user: CurrentUser, companies: CompaniesDep) -> CompanyOut | None:
    company = companies.get(user.id)
    return _company_out(user.id, company) if company else None


@router.put(
    "",
    summary="Заполнить или изменить профиль компании",
    description="Партнёрство с ФСП и логотип этим запросом не меняются.",
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
        size=body.size,
        it_accredited=body.it_accredited,
        benefits=tuple(body.benefits),
        links=tuple(body.links),
    )
    return _company_out(user.id, companies.save(user.id, form))


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
    employer_id, company = companies.confirm_domain(body.token)
    return _company_out(employer_id, company)


async def logo_body(request: Request) -> bytes:
    """Тело не больше лимита: больше — ошибка, не дочитывая файл в память."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > LOGO_MAX_BYTES:
        raise errors.LogoTooLarge()
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > LOGO_MAX_BYTES:
            raise errors.LogoTooLarge()
    return bytes(body)


@router.put(
    "/logo",
    summary="Загрузить логотип",
    description="Тело — картинка как есть: PNG, JPEG или WebP, до 512 КБ. Сначала профиль.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}} for media in LOGO_TYPES
            },
        }
    },
    responses=error_responses(errors.LogoTooLarge, errors.LogoUnsupported, errors.CompanyRequired),
)
def upload_logo(
    request: Request,
    content: Annotated[bytes, Depends(logo_body)],
    user: CurrentUser,
    companies: CompaniesDep,
) -> CompanyOut:
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    return _company_out(user.id, companies.save_logo(user.id, content, media_type))


@router.delete(
    "/logo",
    summary="Убрать логотип",
    responses=error_responses(errors.CompanyRequired),
)
def remove_logo(user: CurrentUser, companies: CompaniesDep) -> CompanyOut:
    return _company_out(user.id, companies.remove_logo(user.id))


@logos.get(
    "/{employer_id}/logo",
    summary="Логотип компании",
    description="Для любой вошедшей учётки: кандидат видит его в приглашении и вакансии.",
    response_class=Response,
    responses={200: {"content": {media: {} for media in LOGO_TYPES}}, 404: {}},
)
def get_logo(employer_id: uuid.UUID, user: CurrentUser, companies: CompaniesDep) -> Response:
    logo = companies.logo(employer_id)
    if logo is None:
        return Response(status_code=404)
    return Response(
        content=logo.content,
        media_type=logo.media_type,
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


def _logo_url(employer_id: uuid.UUID, company: Company) -> str | None:
    if company.logo_updated_at is None:
        return None
    return f"/api/companies/{employer_id}/logo?v={int(company.logo_updated_at.timestamp())}"


def _company_out(employer_id: uuid.UUID, company: Company) -> CompanyOut:
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
        size=company.size,
        it_accredited=company.it_accredited,
        benefits=list(company.benefits),
        links=list(company.links),
        fsp_partner=company.fsp_partner,
        logo_url=_logo_url(employer_id, company),
    )
