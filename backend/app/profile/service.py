"""Профиль кандидата: заполнение, обезличенная карточка для работодателя и PDF-профиль.

Кандидат видит и меняет только свой профиль: эндпоинты берут его из сессии, чужого id они не
принимают. Работодатель получает карточку только кандидата с категорией — выдача строится по
категориям, кандидата без неё для работодателя нет.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assessment.models import CandidateCategory, Industry, Technology
from app.config import Mechanics
from app.domain import candidate
from app.domain.errors import (
    CandidateNotFound,
    CityRequired,
    ProfileNotFound,
    UnknownIndustry,
    UnknownTechnology,
)
from app.domain.skill import Normal
from app.domain.work import WorkFormat
from app.profile.models import CandidateProfile
from app.profile.schemas import ProfileIn
from app.repository.catalog import ref_of
from app.skills.models import SkillProfile
from app.usecase.interface import Clock, ProfilePdfRenderer

PROFILE_ERRORS = (UnknownTechnology, UnknownIndustry, CityRequired)


@dataclass(frozen=True)
class Card:
    candidate_id: uuid.UUID
    category: CandidateCategory
    skill_profile: SkillProfile | None
    profile: CandidateProfile | None


@dataclass(frozen=True)
class ProfilePdf:
    full_name: str
    content: bytes


def get_profile(db: Session, user_id: uuid.UUID) -> CandidateProfile | None:
    return db.get(CandidateProfile, user_id)


def save_profile(
    db: Session, user_id: uuid.UUID, data: ProfileIn, clock: Clock
) -> CandidateProfile:
    stack = _technologies(db, data.stack)
    industries = _industries(db, data.industries)
    if data.city is None and data.work_formats != [WorkFormat.remote]:
        raise CityRequired()
    fields = {
        "full_name": data.full_name,
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "telegram": data.telegram,
        "about": data.about,
        "job_roles": data.job_roles,
        "experience_years": data.experience_years,
        "soft_skills": data.soft_skills,
        "work_formats": [f.value for f in data.work_formats],
        "city": data.city,
        "relocation": data.relocation,
        "salary_from": data.salary_from,
        "updated_at": clock.now(),
    }
    # Вставка с заменой держит строку профиля до конца транзакции: двойное «Сохранить» не
    # упрётся в ключ, а стек второго запроса запишется после первого.
    stmt = pg_insert(CandidateProfile).values(user_id=user_id, **fields)
    db.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=fields))
    profile = db.get_one(CandidateProfile, user_id, populate_existing=True)
    profile.stack = stack
    profile.industries = industries
    db.commit()
    return profile


def card(db: Session, candidate_id: uuid.UUID) -> Card:
    category = db.get(CandidateCategory, candidate_id)
    if category is None:
        raise CandidateNotFound()
    return Card(candidate_id, category, _skill_profile(db, category), get_profile(db, candidate_id))


def profile_pdf(
    db: Session,
    renderer: ProfilePdfRenderer,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    clock: Clock,
) -> ProfilePdf:
    """PDF-профиль кандидата для него самого — раскрыт целиком.

    Профиль навыков — только вместе с категорией и по её специализации, как в карточке:
    оценки незаконченной или неудачной попытки PDF не подтверждает."""
    profile = get_profile(db, user_id)
    if profile is None:
        raise ProfileNotFound()
    category = db.get(CandidateCategory, user_id)
    skill_profile = _skill_profile(db, category) if category else None
    sheet = profile_sheet(profile, category, skill_profile, mechanics)
    return ProfilePdf(profile.full_name, renderer.render(sheet, now=clock.now()))


def profile_sheet(
    profile: CandidateProfile,
    category: CandidateCategory | None,
    skill_profile: SkillProfile | None,
    mechanics: Mechanics,
) -> candidate.ProfileSheet:
    return candidate.ProfileSheet(
        disclosed=candidate.Disclosed(
            full_name=profile.full_name,
            contact_email=profile.contact_email,
            contact_phone=profile.contact_phone,
            telegram=profile.telegram,
            about=profile.about,
            job_roles=tuple(profile.job_roles),
            soft_skills=tuple(profile.soft_skills),
        ),
        self_reported=candidate.SelfReported(
            stack=tuple(ref_of(t) for t in profile.stack),
            experience_years=profile.experience_years,
            work_formats=tuple(WorkFormat(f) for f in profile.work_formats),
            city=profile.city,
            relocation=profile.relocation,
            industries=tuple(ref_of(i) for i in profile.industries),
        ),
        category=(
            candidate.Category(
                ref_of(category.specialization), ref_of(category.grade), category.assigned_at
            )
            if category
            else None
        ),
        skill_profile=_skill_levels(skill_profile, mechanics) if skill_profile else None,
        grade_confidence=mechanics.grade_confidence,
    )


def _skill_levels(profile: SkillProfile, mechanics: Mechanics) -> candidate.SkillProfile:
    def level(theta: float, theta_sd: float) -> candidate.Level:
        return candidate.Level.of(
            Normal(theta, theta_sd), mechanics.grade_thresholds, mechanics.grade_confidence
        )

    rows = sorted(profile.topics, key=lambda row: row.topic.position)
    return candidate.SkillProfile(
        overall=level(profile.overall_theta, profile.overall_theta_sd),
        topics=tuple(
            candidate.TopicLevel(ref_of(r.topic), level(r.theta, r.theta_sd)) for r in rows
        ),
    )


def _skill_profile(db: Session, category: CandidateCategory) -> SkillProfile | None:
    return db.scalar(
        select(SkillProfile).where(
            SkillProfile.user_id == category.user_id,
            SkillProfile.specialization_code == category.specialization_code,
        )
    )


def _technologies(db: Session, codes: list[str]) -> list[Technology]:
    unique = set(codes)
    technologies = list(
        db.scalars(select(Technology).where(Technology.code.in_(unique)).order_by(Technology.name))
    )
    if len(technologies) != len(unique):
        raise UnknownTechnology()
    return technologies


def _industries(db: Session, codes: list[str]) -> list[Industry]:
    unique = set(codes)
    industries = list(
        db.scalars(select(Industry).where(Industry.code.in_(unique)).order_by(Industry.position))
    )
    if len(industries) != len(unique):
        raise UnknownIndustry()
    return industries
