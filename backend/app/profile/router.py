"""Профиль кандидата: форма, PDF-профиль и обезличенная карточка для работодателя."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Response

from app.assessment.schemas import CategoryOut, skill_profile_out
from app.config import Mechanics, MechanicsDep
from app.controller.deps import ClockDep, ProfilePdfRendererDep
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.db import DbSession
from app.domain import errors
from app.domain.work import WorkFormat
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role
from app.profile import service
from app.profile.models import CandidateProfile
from app.profile.schemas import CandidateCardOut, ProfileIn, ProfileOut, SelfReportedOut

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
def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut | None:
    profile = service.get_profile(db, user.id)
    return _profile_out(profile) if profile else None


@router.put(
    "",
    summary="Заполнить или изменить профиль",
    description="Заменяет профиль целиком. Самоописание — низший уровень доверия: категорию "
    "определяет только тест.",
    responses=error_responses(*service.PROFILE_ERRORS),
)
def save_profile(body: ProfileIn, user: CurrentUser, db: DbSession, clock: ClockDep) -> ProfileOut:
    return _profile_out(service.save_profile(db, user.id, body, clock))


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
    db: DbSession,
    mechanics: MechanicsDep,
    renderer: ProfilePdfRendererDep,
    clock: ClockDep,
) -> Response:
    pdf = service.profile_pdf(db, renderer, mechanics, user.id, clock)
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
    candidate_id: uuid.UUID, db: DbSession, mechanics: MechanicsDep
) -> CandidateCardOut:
    return _card_out(service.card(db, candidate_id), mechanics)


def _self_reported_out(profile: CandidateProfile) -> SelfReportedOut:
    return SelfReportedOut(
        stack=[CatalogRef.model_validate(t) for t in profile.stack],
        experience_years=profile.experience_years,
        work_formats=[WorkFormat(f) for f in profile.work_formats],
        city=profile.city,
        relocation=profile.relocation,
        industries=[CatalogRef.model_validate(i) for i in profile.industries],
    )


def _profile_out(profile: CandidateProfile) -> ProfileOut:
    return ProfileOut(
        **_self_reported_out(profile).model_dump(),
        full_name=profile.full_name,
        contact_email=profile.contact_email,
        contact_phone=profile.contact_phone,
        telegram=profile.telegram,
        about=profile.about,
        job_roles=profile.job_roles,
        soft_skills=profile.soft_skills,
        salary_from=profile.salary_from,
        updated_at=profile.updated_at,
    )


def _card_out(card: service.Card, mechanics: Mechanics) -> CandidateCardOut:
    return CandidateCardOut(
        id=card.candidate_id,
        category=CategoryOut.model_validate(card.category),
        skill_profile=(
            skill_profile_out(card.skill_profile, mechanics) if card.skill_profile else None
        ),
        self_reported=_self_reported_out(card.profile) if card.profile else None,
    )
