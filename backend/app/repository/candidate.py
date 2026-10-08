"""Кандидаты в Postgres — реализация порта `CandidateRepository`."""

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Row, Select, and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain import candidate
from app.domain.catalog import CatalogRef
from app.domain.errors import UnknownIndustry, UnknownTechnology
from app.domain.work import WorkFormat
from app.repository.orm import (
    CandidateCategory,
    CandidateProfile,
    Grade,
    Industry,
    SkillProfile,
    SkillProfileTopic,
    Specialization,
    Technology,
    Topic,
    candidate_industries,
    candidate_technologies,
)


class SqlCandidateRepository:
    """Уровни словами считаются здесь же, по порогам грейдов и порогу уверенности из
    `config/mechanics.yaml`: их передаёт сборка."""

    def __init__(
        self, session: Session, grade_thresholds: Mapping[str, float], grade_confidence: float
    ) -> None:
        self.session = session
        self._thresholds = tuple(grade_thresholds.items())
        self._confidence = grade_confidence

    def get(self, candidate_id: uuid.UUID) -> candidate.Candidate:
        found = self._load([candidate_id]).get(candidate_id)
        return found or candidate.Candidate(candidate_id, None, None, None, None)

    def save_profile(
        self, candidate_id: uuid.UUID, form: candidate.ProfileForm, now: datetime
    ) -> None:
        stack = self._technologies(form.stack)
        industries = self._industries(form.industries)
        fields = {
            "full_name": form.full_name,
            "contact_email": form.contact_email,
            "contact_phone": form.contact_phone,
            "telegram": form.telegram,
            "about": form.about,
            "job_roles": list(form.job_roles),
            "experience_years": form.experience_years,
            "soft_skills": list(form.soft_skills),
            "work_formats": [f.value for f in form.work_formats],
            "city": form.city,
            "relocation": form.relocation,
            "salary_from": form.expected_salary,
            "updated_at": now,
        }
        # Вставка с заменой держит строку профиля до конца транзакции: двойное «Сохранить» не
        # упрётся в ключ, а стек второго запроса запишется после первого.
        stmt = pg_insert(CandidateProfile).values(user_id=candidate_id, **fields)
        self.session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=fields))
        row = self.session.get_one(CandidateProfile, candidate_id, populate_existing=True)
        row.stack = stack
        row.industries = industries
        self.session.flush()

    def _load(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, candidate.Candidate]:
        """Кандидаты, у которых есть хоть что-то, — по запросу на часть, без запроса на
        кандидата."""
        db = self.session
        categories = {
            user_id: candidate.Category(
                CatalogRef(specialization_code, specialization_name),
                CatalogRef(grade_code, grade_name),
                assigned_at,
            )
            for (
                user_id,
                assigned_at,
                specialization_code,
                specialization_name,
                grade_code,
                grade_name,
            ) in db.execute(
                select(
                    CandidateCategory.user_id,
                    CandidateCategory.assigned_at,
                    Specialization.code,
                    Specialization.name,
                    Grade.code,
                    Grade.name,
                )
                .join(Specialization, Specialization.code == CandidateCategory.specialization_code)
                .join(Grade, Grade.code == CandidateCategory.grade_code)
                .where(CandidateCategory.user_id.in_(ids))
            )
        }
        profiles = {
            row.user_id: row
            for row in db.execute(
                select(*_PROFILE_COLUMNS).where(CandidateProfile.user_id.in_(ids))
            )
        }
        stacks = self._refs(
            select(candidate_technologies.c.user_id, Technology.code, Technology.name)
            .join(Technology, Technology.code == candidate_technologies.c.technology_code)
            .where(candidate_technologies.c.user_id.in_(ids))
            .order_by(Technology.name)
        )
        industries = self._refs(
            select(candidate_industries.c.user_id, Industry.code, Industry.name)
            .join(Industry, Industry.code == candidate_industries.c.industry_code)
            .where(candidate_industries.c.user_id.in_(ids))
            .order_by(Industry.position)
        )
        skill_profiles = self._skill_profiles(ids)

        result = {}
        for candidate_id in categories.keys() | profiles.keys() | skill_profiles.keys():
            row = profiles.get(candidate_id)
            profile = (
                _profile(row, stacks.get(candidate_id, ()), industries.get(candidate_id, ()))
                if row
                else None
            )
            result[candidate_id] = candidate.Candidate(
                id=candidate_id,
                profile=profile,
                expected_salary=row.salary_from if row else None,
                category=categories.get(candidate_id),
                skill_profile=skill_profiles.get(candidate_id),
            )
        return result

    def _refs(self, query: Select[uuid.UUID, str, str]) -> dict[uuid.UUID, list[CatalogRef]]:
        refs: dict[uuid.UUID, list[CatalogRef]] = defaultdict(list)
        for user_id, code, name in self.session.execute(query):
            refs[user_id].append(CatalogRef(code, name))
        return refs

    def _skill_profiles(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, candidate.SkillProfile]:
        """Профили навыков специализации категории; темы — в порядке справочника. Профиль и его
        темы — разными запросами: строк тем в разы больше, чем профилей."""
        in_category = and_(
            CandidateCategory.user_id == SkillProfile.user_id,
            CandidateCategory.specialization_code == SkillProfile.specialization_code,
        )
        heads = self.session.execute(
            select(
                SkillProfile.user_id,
                SkillProfile.overall_theta,
                SkillProfile.overall_theta_sd,
                SkillProfile.updated_at,
                SkillProfile.last_signal_at,
            )
            .join(CandidateCategory, in_category)
            .where(SkillProfile.user_id.in_(ids))
        ).all()
        levels: dict[uuid.UUID, list[tuple[str, float, float]]] = defaultdict(list)
        for user_id, code, theta, theta_sd in self.session.execute(
            select(
                SkillProfile.user_id,
                SkillProfileTopic.topic_code,
                SkillProfileTopic.theta,
                SkillProfileTopic.theta_sd,
            )
            .join(SkillProfileTopic, SkillProfileTopic.profile_id == SkillProfile.id)
            .join(CandidateCategory, in_category)
            .where(SkillProfile.user_id.in_(ids))
        ):
            levels[user_id].append((code, theta, theta_sd))
        codes = {code for rows in levels.values() for code, _, _ in rows}
        topics = {
            code: (position, CatalogRef(code, name))
            for code, name, position in self.session.execute(
                select(Topic.code, Topic.name, Topic.position).where(Topic.code.in_(codes))
            )
        }
        return {
            user_id: candidate.SkillProfile(
                overall=self._level(theta, theta_sd),
                topics=tuple(
                    candidate.TopicLevel(topics[code][1], self._level(t_theta, t_sd))
                    for code, t_theta, t_sd in sorted(
                        levels[user_id], key=lambda row: topics[row[0]][0]
                    )
                ),
                updated_at=updated_at,
                last_signal_at=last_signal_at,
            )
            for user_id, theta, theta_sd, updated_at, last_signal_at in heads
        }

    def _level(self, theta: float, theta_sd: float) -> candidate.Level:
        return candidate.Level(theta, theta_sd, self._thresholds, self._confidence)

    def _technologies(self, codes: Sequence[str]) -> list[Technology]:
        unique = set(codes)
        technologies = list(
            self.session.scalars(
                select(Technology).where(Technology.code.in_(unique)).order_by(Technology.name)
            )
        )
        if len(technologies) != len(unique):
            raise UnknownTechnology()
        return technologies

    def _industries(self, codes: Sequence[str]) -> list[Industry]:
        unique = set(codes)
        industries = list(
            self.session.scalars(
                select(Industry).where(Industry.code.in_(unique)).order_by(Industry.position)
            )
        )
        if len(industries) != len(unique):
            raise UnknownIndustry()
        return industries


_PROFILE_COLUMNS = (
    CandidateProfile.user_id,
    CandidateProfile.full_name,
    CandidateProfile.contact_email,
    CandidateProfile.contact_phone,
    CandidateProfile.telegram,
    CandidateProfile.about,
    CandidateProfile.job_roles,
    CandidateProfile.soft_skills,
    CandidateProfile.experience_years,
    CandidateProfile.work_formats,
    CandidateProfile.city,
    CandidateProfile.relocation,
    CandidateProfile.salary_from,
    CandidateProfile.updated_at,
)


def _profile(
    row: Row[*tuple[Any, ...]], stack: Sequence[CatalogRef], industries: Sequence[CatalogRef]
) -> candidate.CandidateProfile:
    return candidate.CandidateProfile(
        disclosed=candidate.Disclosed(
            full_name=row.full_name,
            contact_email=row.contact_email,
            contact_phone=row.contact_phone,
            telegram=row.telegram,
            about=row.about,
            job_roles=tuple(row.job_roles),
            soft_skills=tuple(row.soft_skills),
        ),
        self_reported=candidate.SelfReported(
            stack=tuple(stack),
            experience_years=row.experience_years,
            work_formats=tuple(WorkFormat(f) for f in row.work_formats),
            city=row.city,
            relocation=row.relocation,
            industries=tuple(industries),
        ),
        updated_at=row.updated_at,
    )
