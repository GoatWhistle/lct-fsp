"""Профиль навыков из наблюдений всех сигналов с весами уровней доверия (mechanics.md, §11).

Сигналы сейчас — тест (ответы всех попыток кандидата по специализации с весом
`trust_weight_test`) и ФСП (достижения из снимка реестра с весом `trust_weight_fsp`). Наблюдения
идут в модель по времени сигнала; профиль пересчитывается целиком той же моделью навыка, что и
оценка теста, но каждое наблюдение — до сходимости моды (§3). Оценка теста и категория от
профиля не зависят.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from app.domain.catalog import Topic
from app.domain.fsp import (
    Divergence,
    FspEvidence,
    TimedObservation,
    divergences,
    fsp_observations,
)
from app.domain.skill import Prior, SignalSource, SkillProfileLevels
from app.usecase.interface import AttemptReader, AttemptRepository, FspEvidenceReader, SkillModel
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


def fsp_evidence(
    attempts: AttemptRepository, fsp: FspEvidenceReader, user_id: uuid.UUID
) -> FspEvidence | None:
    """Снимок достижений кандидата со справочником дисциплин и темами ролей; `None` — снимка
    нет: профиль — ровно то, что дают остальные сигналы."""
    snapshot = fsp.snapshot(user_id)
    if snapshot is None:
        return None
    roles = {a.team_role for a in snapshot.achievements if a.team_role}
    return FspEvidence(
        achievements=snapshot.achievements,
        disciplines=fsp.disciplines(),
        role_topics={
            role: tuple(t.code for t in attempts.specialization_topics(role) or ())
            for role in roles
        },
    )


def refresh_skill_profile(
    attempts: AttemptReader,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
    fsp: FspEvidence | None = None,
) -> SkillProfileLevels:
    """Профиль по всем сигналам кандидата на специализацию; сохраняет его вызывающий."""
    answered = attempts.answered(user_id, specialization_code)
    timed = [
        TimedObservation(p.answered_at, p.observation(mechanics.trust_weight_test))
        for p in answered
    ]
    if fsp is not None:
        timed += fsp_observations(
            fsp,
            topics,
            difficulty=mechanics.fsp_result_difficulty,
            discrimination=mechanics.fsp_result_discrimination,
            weight=mechanics.trust_weight_fsp,
        )
    # Сортировка устойчива: ответы теста одного момента сохраняют порядок попытки.
    timed.sort(key=lambda t: t.at)
    observations = [t.observation for t in timed]
    result = model.estimate(specialization_prior(topics, mechanics), observations, to_mode=True)
    sources: defaultdict[str, set[SignalSource]] = defaultdict(set)
    for o in observations:
        sources[o.topic].add(o.source)
    return SkillProfileLevels(
        overall=result.overall(),
        topics={topic: result.topic(topic) for topic in topics},
        observations=len(observations),
        last_signal_at=timed[-1].at if timed else None,
        sources={topic: frozenset(found) for topic, found in sources.items()},
    )


def rebuild_skill_profiles(
    attempts: AttemptRepository,
    fsp: FspEvidenceReader,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    now: datetime,
) -> None:
    """Пересчёт всех профилей кандидата после сигнала вне теста: привязки, отвязки или нового
    снимка ФСП. Профиля нет — пересчитывать нечего: он появится с первым тестом."""
    evidence = fsp_evidence(attempts, fsp, user_id)
    for specialization in attempts.profiled_specializations(user_id):
        topics = [t.code for t in attempts.specialization_topics(specialization) or ()]
        levels = refresh_skill_profile(
            attempts, model, mechanics, user_id, specialization, topics, evidence
        )
        attempts.save_profile(user_id, specialization, levels, now)


def fsp_divergences(
    attempts: AttemptRepository,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    evidence: FspEvidence,
) -> list[Divergence]:
    """Расхождения ФСП и теста по всем специализациям с ответами кандидата. Уровень теста по
    теме — оценка теста: все ответы с весом 1, без ФСП."""
    found = []
    for specialization in attempts.profiled_specializations(user_id):
        topics: Sequence[Topic] = attempts.specialization_topics(specialization) or ()
        answered = attempts.answered(user_id, specialization)
        if not answered:
            continue
        codes = [t.code for t in topics]
        estimate = model.estimate(
            specialization_prior(codes, mechanics), [p.observation() for p in answered]
        )
        found += divergences(
            evidence,
            topics,
            {code: estimate.topic(code).mean for code in codes},
            difficulty=mechanics.fsp_result_difficulty,
            threshold=mechanics.fsp_divergence_theta,
        )
    return found
