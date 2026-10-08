"""Профиль навыков из наблюдений всех сигналов с весами уровней доверия (mechanics.md, §11).

Сигналы — тест (ответы всех попыток кандидата по специализации с весом `trust_weight_test`) и
регулярные задания (`trust_weight_regular_task`). Профиль пересчитывается целиком той же
моделью навыка, что и оценка теста, но с затуханием: между наблюдениями растёт погрешность.
Сохраняется на момент последнего сигнала; при чтении его доводит до «сейчас» `ProfileFreshness`.
"""

import dataclasses
import heapq
import uuid
from collections.abc import Sequence
from datetime import datetime

from app.domain import candidate
from app.domain.regular_task import TaskRules, task_observations
from app.domain.selection import PoolCandidate
from app.domain.skill import Normal, Observation, Prior, SkillProfileLevels
from app.usecase.interface import AttemptReader, RegularTaskReader, SkillModel
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


def refresh_skill_profile(
    attempts: AttemptReader,
    tasks: RegularTaskReader,
    model: SkillModel,
    mechanics: Mechanics,
    user_id: uuid.UUID,
    specialization_code: str,
    topics: Sequence[str],
) -> SkillProfileLevels:
    """Профиль по всем ответам кандидата на специализацию — тест и регулярные задания по
    времени; сохраняет его вызывающий."""
    tests = [
        p.observation(mechanics.trust_weight_test)
        for p in attempts.answered(user_id, specialization_code)
    ]
    rules = task_rules(mechanics)
    answered = [a for a in tasks.answered(user_id, specialization_code) if a.counted]
    by_task = [[o for o in task_observations(a, rules) if o.topic in topics] for a in answered]
    observations = list(heapq.merge(tests, *by_task, key=lambda o: _moment(o)))
    result = model.estimate(profile_prior(topics, mechanics), observations)
    return SkillProfileLevels(
        overall=result.overall(),
        topics={topic: result.topic(topic) for topic in topics},
        observations=len(observations),
        last_signal_at=_moment(observations[-1]) if observations else None,
        regular_task_topics=frozenset(
            o.topic for a, group in zip(answered, by_task, strict=True) if a.confirms for o in group
        ),
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
