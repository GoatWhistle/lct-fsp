"""Профиль кандидата: форма, PDF-профиль и карточка кандидата для работодателя.

Что показать, решает правило раскрытия в сценарии; здесь карточка только сериализуется.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response

from app.controller.deps import (
    ROLE_RESPONSES,
    CandidatesDep,
    ClockDep,
    CurrentUser,
    ExperienceLimitsDep,
    InvitationReaderDep,
    MechanicsDep,
    ProfileFreshnessDep,
    ProfilePdfRendererDep,
    ResumeDraftsDep,
    UnitOfWorkDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.fsp_schemas import FspAchievementOut, FspAnonymizedAchievementOut
from app.controller.path_schemas import CategoryOut, skill_profile_view
from app.controller.profile_schemas import (
    CandidateCardOut,
    CardSelfReportedOut,
    DisclosedOut,
    ExperienceEntryOut,
    GradeHintOut,
    ProfileIn,
    ProfileOut,
    ResumeDraftOut,
    SelfReportedOut,
    TechnologyYearsOut,
)
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain import candidate as domain
from app.domain import errors
from app.domain.account import Role
from app.domain.experience import (
    ExperienceEntry,
    ExperienceInput,
    Month,
    technology_years,
)
from app.domain.fsp import anonymized
from app.domain.resume_draft import CheckedResumeDraft, GradeHint
from app.usecase import candidate as usecase

PROFILE_ERRORS = (
    errors.UnknownTechnology,
    errors.UnknownIndustry,
    errors.CityRequired,
    errors.ExperiencePlaceRequired,
    errors.ExperiencePeriodInvalid,
    errors.ExperienceStartInFuture,
    errors.ExperienceTooLong,
)

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
    card = usecase.own_profile(uow, candidates, user.id, clock, freshness)
    return _profile_out(card, clock.now().date())


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
    experience_limits: ExperienceLimitsDep,
) -> ProfileOut:
    card = usecase.save_profile(
        uow,
        candidates,
        user.id,
        _form(body),
        clock,
        freshness,
        experience_limits=experience_limits,
    )
    out = _profile_out(card, clock.now().date())
    assert out is not None, "анкета только что сохранена"
    return out


async def resume_body(request: Request, mechanics: MechanicsDep) -> bytes:
    """Тело запроса не больше лимита: больше — ошибка, не дочитывая файл в память."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > mechanics.resume_max_bytes:
        raise errors.ResumeTooLarge()
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > mechanics.resume_max_bytes:
            raise errors.ResumeTooLarge()
    return bytes(body)


@router.post(
    "/resume",
    summary="Разобрать резюме из PDF",
    description="Тело — PDF как есть (`Content-Type: application/pdf`). Ответ — черновик анкеты "
    "«система поняла так»: ФИО, контакты, стек из справочника, роли, стаж, софт-скиллы и "
    "подсказка грейда. Скрытый текст PDF — белый, прозрачный, крошечный, за краем страницы — в "
    "разбор не идёт. Разбор локальный, наружу файл не уходит; ни файл, ни черновик не "
    "сохраняются — профиль меняет только `PUT /api/candidate/profile`.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
    responses=error_responses(
        errors.ResumeTooLarge, errors.ResumeUnreadable, errors.ResumeWithoutText
    ),
)
def parse_resume(
    pdf: Annotated[bytes, Depends(resume_body)], drafts: ResumeDraftsDep
) -> ResumeDraftOut:
    return _resume_out(drafts.parse(pdf))


@router.get(
    "/grade-hint",
    summary="Подсказка грейда",
    description="По стажу и ролям сохранённого профиля — для шага выбора грейда. Грейд не "
    "выбирает и на категорию не влияет. `null` — профиль не заполнен.",
)
def get_grade_hint(user: CurrentUser, drafts: ResumeDraftsDep) -> GradeHintOut | None:
    hint = drafts.grade_hint(user.id)
    return _grade_hint_out(hint) if hint else None


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
    description="Статус грейда, категория, профиль навыков и структурная часть самоописания — "
    "без полей, скрытых кандидатом, пока карточка обезличена. "
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
    clock: ClockDep,
    freshness: ProfileFreshnessDep,
) -> CandidateCardOut:
    card = usecase.employer_card(
        uow, candidates, invitations, user.id, candidate_id, clock, freshness
    )
    return _card_out(card, clock.now().date())


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
        hidden=frozenset(body.hidden),
        experience=tuple(
            ExperienceInput(
                place=e.place,
                role=e.role,
                start=Month.parse(e.start),
                end=Month.parse(e.end) if e.end else None,
                stack=tuple(e.stack),
                summary=e.summary,
            )
            for e in body.experience
        ),
    )


def _grade_hint_out(hint: GradeHint) -> GradeHintOut:
    refs = CatalogRef.model_validate
    return GradeHintOut(
        grade=refs(hint.grade),
        by_experience=refs(hint.by_experience) if hint.by_experience else None,
        by_roles=refs(hint.by_roles) if hint.by_roles else None,
    )


def _resume_out(draft: CheckedResumeDraft) -> ResumeDraftOut:
    return ResumeDraftOut(
        full_name=draft.full_name,
        contact_email=draft.contact_email,
        contact_phone=draft.contact_phone,
        telegram=draft.telegram,
        stack=[CatalogRef.model_validate(t) for t in draft.stack],
        job_roles=list(draft.job_roles),
        experience_years=draft.experience_years,
        soft_skills=list(draft.soft_skills),
        experience=_experience_out(draft.experience),
        confidence=dict(draft.confidence),
        uncertain=sorted(draft.uncertain),
        grade_hint=_grade_hint_out(draft.grade_hint) if draft.grade_hint else None,
    )


def _experience_out(entries: Sequence[ExperienceEntry]) -> list[ExperienceEntryOut]:
    return [
        ExperienceEntryOut(
            place=e.place,
            role=e.role,
            start=str(e.start),
            end=str(e.end) if e.end else None,
            stack=[CatalogRef.model_validate(t) for t in e.stack],
            summary=e.summary,
        )
        for e in entries
    ]


def _technology_years_out(
    entries: Sequence[ExperienceEntry], today: date
) -> list[TechnologyYearsOut]:
    return [
        TechnologyYearsOut(technology=CatalogRef.model_validate(y.technology), years=y.years)
        for y in technology_years(entries, today)
    ]


def _self_reported_out(self_reported: domain.SelfReported) -> SelfReportedOut:
    return SelfReportedOut(
        stack=[CatalogRef.model_validate(t) for t in self_reported.stack],
        experience_years=self_reported.experience_years,
        work_formats=list(self_reported.work_formats),
        city=self_reported.city,
        relocation=self_reported.relocation,
        industries=[CatalogRef.model_validate(i) for i in self_reported.industries],
    )


def _profile_out(card: domain.DisclosedCard, today: date) -> ProfileOut | None:
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
        experience=_experience_out(disclosed.experience),
        technology_years=_technology_years_out(disclosed.experience, today),
        salary_from=salary,
        updated_at=profile.updated_at,
        hidden=list(profile.hidden),
    )


def _card_self_reported_out(
    self_reported: domain.SelfReported | domain.VisibleSelfReported,
) -> CardSelfReportedOut:
    """Самоописание карточки: у раскрытой — полностью, у обезличенной — без скрытого."""
    if isinstance(self_reported, domain.SelfReported):
        self_reported = domain.VisibleSelfReported.of(self_reported, frozenset())
    refs = CatalogRef.model_validate
    s = self_reported
    return CardSelfReportedOut(
        stack=[refs(t) for t in s.stack] if s.stack is not None else None,
        experience_years=s.experience_years,
        work_formats=list(s.work_formats),
        city=s.city,
        relocation=s.relocation,
        industries=[refs(i) for i in s.industries] if s.industries is not None else None,
        hidden=list(s.hidden),
    )


def _card_out(card: domain.AnonymizedCard | domain.DisclosedCard, today: date) -> CandidateCardOut:
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
            experience=_experience_out(d.experience),
            technology_years=_technology_years_out(d.experience, today),
        )
    return CandidateCardOut(
        id=card.candidate_id,
        category=CategoryOut.model_validate(card.category) if card.category else None,
        grade_status=GradeStatusOut.model_validate(card.grade_status),
        skill_profile=skill_profile_view(card.skill_profile) if card.skill_profile else None,
        self_reported=(_card_self_reported_out(card.self_reported) if card.self_reported else None),
        fsp_achievements=[FspAnonymizedAchievementOut.model_validate(a) for a in achievements],
        disclosed=disclosed,
        fsp_details=details,
    )
