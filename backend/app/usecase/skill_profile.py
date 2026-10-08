"""Профиль навыков из наблюдений всех сигналов с весами уровней доверия (mechanics.md, §11).

Сигналы — тест (ответы всех попыток кандидата по специализации с весом `trust_weight_test`),
регулярные задания (`trust_weight_regular_task`) и ФСП (достижения из снимка реестра с весом
`trust_weight_fsp`). Наблюдения идут в модель по времени сигнала; профиль пересчитывается целиком
той же моделью навыка, что и оценка теста, но каждое наблюдение — до сходимости моды (§3) и с
затуханием: между наблюдениями растёт погрешность. Сохраняется на момент последнего сигнала; при
чтении его доводит до «сейчас» `ProfileFreshness`. Оценка теста и категория от профиля не
зависят.
"""

import dataclasses
import heapq
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from app.domain import candidate
from app.domain.catalog import Topic
from app.domain.fsp import Divergence, FspEvidence, divergences, fsp_observations
from app.domain.regular_task import TaskRules, task_observations
from app.domain.selection import PoolCandidate
from app.domain.skill import Normal, Observation, Prior, SignalSource, SkillProfileLevels
from app.usecase.interface import (
    AttemptReader,
    AttemptRepository,
    FspEvidenceReader,
    RegularTaskReader,
    SkillModel,
)
from settings import Mechanics


def specialization_prior(topics: Sequence[str], mechanics: Mechanics) -> Prior:
    """Иерархическое априорное по темам специализации с равными весами тем и поправкой
    погрешности (§3). Без затухания: оценка теста и категория не устаревают."""
    return Prior.equal_weights(
        topics,
        theta_sd=mechanics.theta_prior_sd,
        deviation_sd=mechanics.topic_deviation_sd,
        sd_inflation=mechanics.level_sd_inflation,
    )


def profile_prior(topics: Sequence[str], mechanics: Mechanics) -> Prior:
    """Априорное профиля навыков — то же, что у теста, плюс свежесть `profile_decay_sd_per_year`."""
    return dataclasses.replace(
        specialization_prior(topics, mechanics),
        decay_sd_per_year=mechanics.profile_decay_sd_per_year,
    )


def task_rules(mechanics: Mechanics) -> TaskRules:
    return TaskRules(
        thresholds=mechanics.grade_thresholds,
        rubric_offsets=mechanics.regular_task_rubric_offsets,
        discrimination=mechanics.regular_task_discrimination,
        weight=mechanics.trust_weight_regular_task,
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


@dataclasses.dataclass(frozen=True)
class _Signals:
    # Наблюдения всех сигналов по времени.
    observations: list[Observation]
    # Темы, по которым в профиль вошли ответы на регулярные задания.
    regular_task_topics: frozenset[str]


def _signals(
    attempts: AttemptReader,
    tasks: RegularTaskReader,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
    fsp: FspEvidence | None,
) -> _Signals:
    tests = [
        p.observation(mechanics.trust_weight_test)
        for p in attempts.answered(user_id, specialization_code)
    ]
    rules = task_rules(mechanics)
    answered = [a for a in tasks.answered(user_id, specialization_code) if a.counted]
    by_task = [[o for o in task_observations(a, rules) if o.topic in topics] for a in answered]
    achievements = (
        sorted(
            (
                dataclasses.replace(t.observation, at=t.at)
                for t in fsp_observations(
                    fsp,
                    topics,
                    difficulty=mechanics.fsp_result_difficulty,
                    discrimination=mechanics.fsp_result_discrimination,
                    weight=mechanics.trust_weight_fsp,
                )
            ),
            key=_moment,
        )
        if fsp is not None
        else []
    )
    # Слияние устойчиво: ответы теста одного момента сохраняют порядок попытки.
    return _Signals(
        list(heapq.merge(achievements, tests, *by_task, key=_moment)),
        frozenset(
            o.topic for a, group in zip(answered, by_task, strict=True) if a.confirms for o in group
        ),
    )


def profile_observations(
    attempts: AttemptReader,
    tasks: RegularTaskReader,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
    fsp: FspEvidence | None = None,
) -> list[Observation]:
    """Наблюдения профиля навыков по всем сигналам кандидата на специализацию — по времени, как
    их берёт `refresh_skill_profile`."""
    return _signals(
        attempts, tasks, mechanics, user_id, specialization_code, topics, fsp
    ).observations


def refresh_skill_profile(
    attempts: AttemptReader,
    tasks: RegularTaskReader,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
    fsp: FspEvidence | None = None,
) -> SkillProfileLevels:
    """Профиль по всем сигналам кандидата на специализацию — тест, регулярные задания и ФСП по
    времени; сохраняет его вызывающий."""
    signals = _signals(attempts, tasks, mechanics, user_id, specialization_code, topics, fsp)
    observations = signals.observations
    result = model.estimate(profile_prior(topics, mechanics), observations, to_mode=True)
    sources: defaultdict[str, set[SignalSource]] = defaultdict(set)
    for o in observations:
        sources[o.topic].add(o.source)
    return SkillProfileLevels(
        overall=result.overall(),
        topics={topic: result.topic(topic) for topic in topics},
        observations=len(observations),
        last_signal_at=_moment(observations[-1]) if observations else None,
        regular_task_topics=signals.regular_task_topics,
        sources={topic: frozenset(found) for topic, found in sources.items()},
    )


def _moment(observation: Observation) -> datetime:
    assert observation.at is not None, "наблюдение профиля — с моментом"
    return observation.at


class ProfileFreshness:
    """Доворот сохранённого профиля до «сейчас» (§11, «Свежесть»): без новых сигналов
    погрешность растёт, уровень остаётся. Все, кто читает профиль навыков, — подборка, карточка,
    профиль кандидата, PDF, — видят его через это правило."""

    def __init__(self, model: SkillModel, mechanics: Mechanics) -> None:
        self._model = model
        self._mechanics = mechanics
        # Априорное — по набору тем: в подборке он один на весь пул.
        self._priors: dict[tuple[str, ...], Prior] = {}

    def levels(self, levels: SkillProfileLevels, now: datetime) -> SkillProfileLevels:
        return self._model.advance(
            profile_prior(tuple(levels.topics), self._mechanics), levels, now
        )

    def view(self, profile: candidate.SkillProfile, now: datetime) -> candidate.SkillProfile:
        levels = self.levels(
            SkillProfileLevels(
                overall=Normal(profile.overall.theta, profile.overall.theta_sd),
                topics={
                    t.topic.code: Normal(t.level.theta, t.level.theta_sd) for t in profile.topics
                },
                observations=0,
                last_signal_at=profile.last_signal_at,
            ),
            now,
        )
        return dataclasses.replace(
            profile,
            overall=_level(profile.overall, levels.overall),
            topics=tuple(
                dataclasses.replace(t, level=_level(t.level, levels.topics[t.topic.code]))
                for t in profile.topics
            ),
        )

    def candidate(self, person: candidate.Candidate, now: datetime) -> candidate.Candidate:
        if person.skill_profile is None:
            return person
        return dataclasses.replace(person, skill_profile=self.view(person.skill_profile, now))

    def pool(self, member: PoolCandidate, now: datetime) -> PoolCandidate:
        levels = self.levels(
            SkillProfileLevels(member.overall, member.levels, 0, member.last_signal_at), now
        )
        return dataclasses.replace(member, overall=levels.overall, levels=levels.topics)


def _level(level: candidate.Level, now: Normal) -> candidate.Level:
    if level.theta_sd == now.sd:
        return level
    return dataclasses.replace(level, theta_sd=now.sd)


def rebuild_skill_profiles(
    attempts: AttemptRepository,
    tasks: RegularTaskReader,
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
            attempts, tasks, model, mechanics, user_id, specialization, topics, evidence
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
