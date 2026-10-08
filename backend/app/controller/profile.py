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
    InvitationReaderDep,
    MechanicsDep,
    ProfilePdfRendererDep,
    UnitOfWorkDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.fsp_schemas import FspAchievementOut, FspAnonymizedAchievementOut
from app.controller.path_schemas import CategoryOut, skill_profile_view
from app.controller.profile_schemas import (
    CandidateCardOut,
    DisclosedOut,
    ProfileIn,
    ProfileOut,
    SelfReportedOut,
)
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain import candidate as domain
from app.domain import errors
from app.domain.account import Role
from app.domain.fsp import anonymized
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
    user: CurrentUser, uow: UnitOfWorkDep, candidates: CandidatesDep
) -> ProfileOut | None:
    return _profile_out(usecase.own_profile(uow, candidates, user.id))


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
) -> ProfileOut:
    card = usecase.save_profile(uow, candidates, user.id, _form(body), clock)
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
) -> Response:
    pdf = usecase.profile_pdf(
        uow, candidates, renderer, user.id, clock, grade_confidence=mechanics.grade_confidence
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
    description="Статус грейда, категория, профиль навыков и структурная часть самоописания. "
    "ФИО, контакты и свободный текст — только после принятия приглашения вашей компании; "
    "ожидаемой зарплаты нет никогда. Есть у кандидата с категорией или с заявленным грейдом.",
    responses=error_responses(errors.CandidateNotFound),
)
def get_candidate_card(
    candidate_id: uuid.UUID,
    user: CurrentUser,
    uow: UnitOfWorkDep,
    candidates: CandidatesDep,
    invitations: InvitationReaderDep,
) -> CandidateCardOut:
    return _card_out(usecase.employer_card(uow, candidates, invitations, user.id, candidate_id))


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
    """Карточка для работодателя как её отдало правило раскрытия: раскрытая часть — только у
    раскрытой. Ожидаемая зарплата в схему не входит. Достижения ФСП обезличенно — всегда,
    полностью — только у раскрытой."""
    disclosed = None
    if isinstance(card, domain.AnonymizedCard):
        achievements, details = card.fsp_achievements, None
    else:
        achievements = tuple(anonymized(a) for a in card.fsp_achievements)
        details = [FspAchievementOut.model_validate(a) for a in card.fsp_achievements]
    if isinstance(card, domain.DisclosedCard) and card.profile is not None:
        d = card.profile.disclosed
        disclosed = DisclosedOut(
            full_name=d.full_name,
            contact_email=d.contact_email,
            contact_phone=d.contact_phone,
            telegram=d.telegram,
            about=d.about,
            job_roles=list(d.job_roles),
            soft_skills=list(d.soft_skills),
        )
    return CandidateCardOut(
        id=card.candidate_id,
        category=CategoryOut.model_validate(card.category) if card.category else None,
        grade_status=GradeStatusOut.model_validate(card.grade_status),
        skill_profile=skill_profile_view(card.skill_profile) if card.skill_profile else None,
        self_reported=_self_reported_out(card.self_reported) if card.self_reported else None,
        fsp_achievements=[FspAnonymizedAchievementOut.model_validate(a) for a in achievements],
        disclosed=disclosed,
        fsp_details=details,
    )
