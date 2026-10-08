"""Профиль кандидата: форма, PDF-профиль и карточка кандидата для работодателя.

Что показать, решает правило раскрытия в сценарии; здесь карточка только сериализуется.
"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Response

from app.controller.deps import (
    ROLE_RESPONSES,
    CandidatesDep,
    ClockDep,
    CurrentUser,
    MechanicsDep,
    ProfileFreshnessDep,
    ProfilePdfRendererDep,
    UnitOfWorkDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.path_schemas import CategoryOut, skill_profile_view
from app.controller.profile_schemas import (
    CandidateCardOut,
    ProfileIn,
    ProfileOut,
    SelfReportedOut,
)
from app.controller.schemas import CatalogRef
from app.domain import candidate as domain
from app.domain import errors
from app.domain.account import Role
from app.usecase import candidate as usecase

PROFILE_ERRORS = (errors.UnknownTechnology, errors.UnknownIndustry, errors.CityRequired)

router = APIRouter(
    prefix="/api/candidate/profile",
    tags=["candidate-profile"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)

employer_router = APIRouter(
    prefix="/api/employer/candidates",
    tags=["employer-candidates"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)


@router.get(
    "",
    summary="Профиль кандидата",
    description="Только свой: кандидат определяется по сессии. `null` — профиль ещё не заполнен.",
)
def get_profile(
    user: CurrentUser,
    uow: UnitOfWorkDep,
    candidates: CandidatesDep,
    clock: ClockDep,
    freshness: ProfileFreshnessDep,
) -> ProfileOut | None:
    return _profile_out(usecase.own_profile(uow, candidates, user.id, clock, freshness))


@router.put(
    "",
    summary="Заполнить или изменить профиль",
    description="Заменяет профиль целиком. Самоописание — низший уровень доверия: категорию "
    "определяет только тест.",
    responses=error_responses(*PROFILE_ERRORS),
)
def save_profile(
    body: ProfileIn,
    user: CurrentUser,
    uow: UnitOfWorkDep,
    candidates: CandidatesDep,
    clock: ClockDep,
    freshness: ProfileFreshnessDep,
) -> ProfileOut:
    card = usecase.save_profile(uow, candidates, user.id, _form(body), clock, freshness)
    out = _profile_out(card)
    assert out is not None, "анкета только что сохранена"
    return out


@router.get(
    "/pdf",
    summary="Стандартизированный PDF-профиль",
    description="Данные формы, категория и профиль навыков её специализации, если тест пройден. "
    "Ожидаемой зарплаты в PDF нет.",
    response_class=Response,
    responses={
        200: {
            "description": "PDF-файл",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        **error_responses(errors.ProfileNotFound),
    },
)
def download_pdf(
    user: CurrentUser,
    uow: UnitOfWorkDep,
    candidates: CandidatesDep,
    mechanics: MechanicsDep,
    renderer: ProfilePdfRendererDep,
    clock: ClockDep,
    freshness: ProfileFreshnessDep,
) -> Response:
    pdf = usecase.profile_pdf(
        uow,
        candidates,
        renderer,
        user.id,
        clock,
        freshness,
        grade_confidence=mechanics.grade_confidence,
    )
    filename = quote(f"Профиль кандидата — {pdf.full_name}.pdf")
    return Response(
        pdf.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"profile.pdf\"; filename*=UTF-8''{filename}"
            ),
            # Персональные данные — не оседают в кэшах по дороге.
            "Cache-Control": "no-store",
        },
    )


@employer_router.get(
    "/{candidate_id}",
    summary="Карточка кандидата",
    description="Обезличенная: категория, профиль навыков и структурная часть самоописания. Без "
    "ФИО, контактов, свободного текста и ожидаемой зарплаты. Есть только у кандидата с "
    "категорией.",
    responses=error_responses(errors.CandidateNotFound),
)
def get_candidate_card(
    candidate_id: uuid.UUID,
    user: CurrentUser,
    uow: UnitOfWorkDep,
    candidates: CandidatesDep,
    clock: ClockDep,
    freshness: ProfileFreshnessDep,
) -> CandidateCardOut:
    card = usecase.employer_card(uow, candidates, user.id, candidate_id, clock, freshness)
    return _card_out(card)


def _form(body: ProfileIn) -> domain.ProfileForm:
    return domain.ProfileForm(
        full_name=body.full_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        telegram=body.telegram,
        about=body.about,
        job_roles=tuple(body.job_roles),
        soft_skills=tuple(body.soft_skills),
        stack=tuple(body.stack),
        experience_years=body.experience_years,
        work_formats=tuple(body.work_formats),
        city=body.city,
        relocation=body.relocation,
        industries=tuple(body.industries),
        expected_salary=body.salary_from,
    )


def _self_reported_out(self_reported: domain.SelfReported) -> SelfReportedOut:
    return SelfReportedOut(
        stack=[CatalogRef.model_validate(t) for t in self_reported.stack],
        experience_years=self_reported.experience_years,
        work_formats=list(self_reported.work_formats),
        city=self_reported.city,
        relocation=self_reported.relocation,
        industries=[CatalogRef.model_validate(i) for i in self_reported.industries],
    )


def _profile_out(card: domain.DisclosedCard) -> ProfileOut | None:
    """Анкета своей карточки; `None` — анкета не заполнена."""
    profile, salary = card.profile, card.expected_salary
    if profile is None or salary is None:
        return None
    disclosed = profile.disclosed
    return ProfileOut(
        **_self_reported_out(profile.self_reported).model_dump(),
        full_name=disclosed.full_name,
        contact_email=disclosed.contact_email,
        contact_phone=disclosed.contact_phone,
        telegram=disclosed.telegram,
        about=disclosed.about,
        job_roles=list(disclosed.job_roles),
        soft_skills=list(disclosed.soft_skills),
        salary_from=salary,
        updated_at=profile.updated_at,
    )


def _card_out(card: domain.AnonymizedCard | domain.DisclosedCard) -> CandidateCardOut:
    """Карточка для работодателя. Раскрытой части в схеме ответа пока нет: раскрывать нечем —
    ни приглашений, ни откликов ещё не существует."""
    return CandidateCardOut(
        id=card.candidate_id,
        category=CategoryOut.model_validate(card.category),
        skill_profile=skill_profile_view(card.skill_profile) if card.skill_profile else None,
        self_reported=_self_reported_out(card.self_reported) if card.self_reported else None,
    )
