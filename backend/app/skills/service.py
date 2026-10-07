"""Запись профиля навыков в базу. Сам профиль считает сценарий `app.usecase.skill_profile`."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.skill import SkillProfileLevels
from app.skills.models import SkillProfile, SkillProfileTopic


def store_profile(
    db: Session,
    user_id: uuid.UUID,
    specialization_code: str,
    levels: SkillProfileLevels,
    now: datetime,
) -> SkillProfile:
    """Профиль кандидата по специализации — новый или поверх прежнего; время обновления —
    переданный момент `now`."""
    profile = db.scalar(
        select(SkillProfile).where(
            SkillProfile.user_id == user_id,
            SkillProfile.specialization_code == specialization_code,
        )
    )
    if profile is None:
        profile = SkillProfile(user_id=user_id, specialization_code=specialization_code)
        db.add(profile)
    profile.overall_theta, profile.overall_theta_sd = levels.overall.mean, levels.overall.sd
    profile.observations = levels.observations
    profile.updated_at = now
    profile.last_signal_at = levels.last_signal_at
    rows = {row.topic_code: row for row in profile.topics}
    for topic, level in levels.topics.items():
        if topic not in rows:
            rows[topic] = SkillProfileTopic(topic_code=topic)
            profile.topics.append(rows[topic])
        rows[topic].theta, rows[topic].theta_sd = level.mean, level.sd
    return profile
