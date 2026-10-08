"""Профиль навыков из наблюдений всех сигналов с весами уровней доверия (mechanics.md, §11).

Пока сигнал один — тест: ответы всех попыток кандидата по специализации с весом
`trust_weight_test`. Профиль пересчитывается целиком той же моделью навыка, что и оценка теста.
"""

import uuid
from collections.abc import Sequence

from app.domain.skill import Prior, SkillProfileLevels
from app.usecase.interface import AttemptReader, SkillModel
from settings import Mechanics


def specialization_prior(topics: Sequence[str], mechanics: Mechanics) -> Prior:
    """Иерархическое априорное по темам специализации с равными весами тем и поправкой
    погрешности (§3)."""
    return Prior.equal_weights(
        topics,
        theta_sd=mechanics.theta_prior_sd,
        deviation_sd=mechanics.topic_deviation_sd,
        sd_inflation=mechanics.level_sd_inflation,
    )


def refresh_skill_profile(
    attempts: AttemptReader,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
) -> SkillProfileLevels:
    """Профиль по всем ответам кандидата на специализацию; сохраняет его вызывающий."""
    answered = attempts.answered(user_id, specialization_code)
    result = model.estimate(
        specialization_prior(topics, mechanics),
        [p.observation(mechanics.trust_weight_test) for p in answered],
    )
    return SkillProfileLevels(
        overall=result.overall(),
        topics={topic: result.topic(topic) for topic in topics},
        observations=len(answered),
        last_signal_at=answered[-1].answered_at if answered else None,
    )
