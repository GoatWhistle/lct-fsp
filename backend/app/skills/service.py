"""Профиль навыков из наблюдений всех сигналов с весами уровней доверия (mechanics.md, §11).

Пока сигнал один — тест: ответы всех попыток кандидата по специализации с весом
`trust_weight_test`. Профиль пересчитывается целиком той же чистой функцией, что и оценка теста.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.models import Presentation, TestAttempt
from app.config import Mechanics
from app.domain.skill import Observation, Prior
from app.skills.irt import estimate
from app.skills.models import SkillProfile, SkillProfileTopic


def specialization_prior(topics: Sequence[str], mechanics: Mechanics) -> Prior:
    """Иерархическое априорное по темам специализации с равными весами тем и поправкой
    погрешности (§3)."""
    return Prior.equal_weights(
        topics,
        theta_sd=mechanics.theta_prior_sd,
        deviation_sd=mechanics.topic_deviation_sd,
        sd_inflation=mechanics.level_sd_inflation,
    )


def presentation_observation(presentation: Presentation, weight: float = 1.0) -> Observation:
    if presentation.correct is None:
        raise ValueError("наблюдение — только отвеченное предъявление")
    return Observation(
        topic=presentation.topic_code,
        correct=presentation.correct,
        discrimination=presentation.discrimination,
        difficulty=presentation.difficulty,
        weight=weight,
    )


def refresh_profile(
    db: Session,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
    mechanics: Mechanics,
    now: datetime,
) -> SkillProfile:
    """Пересчёт профиля по всем ответам; время обновления — переданный момент `now`."""
    answered = db.scalars(
        select(Presentation)
        .join(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.specialization_code == specialization_code,
            Presentation.answered_at.is_not(None),
        )
        .order_by(TestAttempt.number, Presentation.position)
    ).all()
    result = estimate(
        specialization_prior(topics, mechanics),
        [presentation_observation(p, mechanics.trust_weight_test) for p in answered],
    )

    profile = db.scalar(
        select(SkillProfile).where(
            SkillProfile.user_id == user_id,
            SkillProfile.specialization_code == specialization_code,
        )
    )
    if profile is None:
        profile = SkillProfile(user_id=user_id, specialization_code=specialization_code)
        db.add(profile)
    overall = result.overall()
    profile.overall_theta, profile.overall_theta_sd = overall.mean, overall.sd
    profile.observations = len(answered)
    profile.updated_at = now
    profile.last_signal_at = answered[-1].answered_at if answered else None
    rows = {row.topic_code: row for row in profile.topics}
    for topic in topics:
        if topic not in rows:
            rows[topic] = SkillProfileTopic(topic_code=topic)
            profile.topics.append(rows[topic])
        level = result.topic(topic)
        rows[topic].theta, rows[topic].theta_sd = level.mean, level.sd
    return profile
