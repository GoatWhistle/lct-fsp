"""Обратная связь кандидату (mechanics.md, §15): место в подборках за `feedback_period_days` и
что поднимет выше.

Правила — в домене (`app.domain.feedback`); здесь — чтение подборок, профиля навыков на
«сейчас», доступных регулярных заданий, интервал блока по теме (§6) и прогноз уровня темы после
блока по ней. Прогноз —
та же модель навыка, что и профиль: к наблюдениям профиля добавляются `topic_block_items`
ответов по теме со сложностью около уровня с ожидаемым исходом при p = ½. Без кэша: каждый
запрос — пересчёт.
"""

import statistics
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta

from app.domain import bank
from app.domain.attempt import topic_blocks_held
from app.domain.feedback import Feedback, FeedbackRules, Narrowed, feedback
from app.domain.regular_task import CatalogFilter
from app.domain.skill import Normal, Observation, SignalSource
from app.usecase.interface import (
    AttemptRepository,
    Calibration,
    CandidateRepository,
    Clock,
    FspEvidenceReader,
    RegularTaskRepository,
    SelectionRepository,
    SkillModel,
    UnitOfWork,
)
from app.usecase.selection import selection_rules
from app.usecase.skill_profile import (
    ProfileFreshness,
    fsp_evidence,
    profile_observations,
    profile_prior,
)
from settings import Mechanics


def feedback_rules(mechanics: Mechanics) -> FeedbackRules:
    return FeedbackRules(
        min_companies=mechanics.feedback_min_companies,
        period_days=mechanics.feedback_period_days,
        hints_max=mechanics.feedback_hints_max,
        min_gain=mechanics.feedback_min_gain,
        missing_level=selection_rules(mechanics).missing_level,
    )


class CandidateFeedback:
    def __init__(
        self,
        uow: UnitOfWork,
        candidates: CandidateRepository,
        selections: SelectionRepository,
        attempts: AttemptRepository,
        tasks: RegularTaskRepository,
        fsp: FspEvidenceReader,
        calibration: Calibration,
        skill_model: SkillModel,
        clock: Clock,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._candidates = candidates
        self._selections = selections
        self._attempts = attempts
        self._tasks = tasks
        self._fsp = fsp
        self._calibration = calibration
        self._skill_model = skill_model
        self._clock = clock
        self._mechanics = mechanics
        self._rules = feedback_rules(mechanics)
        self._freshness = ProfileFreshness(skill_model, mechanics)

    def own(self, candidate_id: uuid.UUID) -> Feedback:
        """Обратная связь кандидату о нём самом: ни работодателей, ни потребностей, ни чужих
        профилей в ней нет."""
        with self._uow:
            now = self._clock.now()
            person = self._freshness.candidate(self._candidates.get(candidate_id), now)
            selections = self._selections.with_candidate(
                candidate_id, now - timedelta(days=self._rules.period_days)
            )
            stack = (
                frozenset(t.code for t in person.profile.self_reported.stack)
                if person.profile
                else frozenset()
            )
            category, profile = person.category, person.skill_profile
            if category is None or profile is None:
                return feedback(
                    selections,
                    specialization=None,
                    topics=(),
                    levels={},
                    candidate_stack=stack,
                    narrowed=lambda topic: None,
                    task_topics=(),
                    block_held={},
                    fsp_linked=person.fsp is not None,
                    rules=self._rules,
                )
            specialization = category.specialization.code
            levels = {t.topic.code: Normal(t.level.theta, t.level.theta_sd) for t in profile.topics}
            return feedback(
                selections,
                specialization=specialization,
                topics=[t.topic for t in profile.topics],
                levels=levels,
                candidate_stack=stack,
                narrowed=self._narrowing(candidate_id, specialization, levels, now),
                task_topics=self._task_topics(candidate_id, specialization),
                block_held=self._block_held(candidate_id, levels, now),
                fsp_linked=person.fsp is not None,
                rules=self._rules,
            )

    def _task_topics(self, candidate_id: uuid.UUID, specialization: str) -> frozenset[str]:
        """Темы активных заданий специализации, на которые кандидат ещё не ответил."""
        answered = self._tasks.answered_task_ids(candidate_id)
        return frozenset(
            topic.code
            for task in self._tasks.catalog(specialization, CatalogFilter())
            if task.id not in answered
            for topic in task.topics
        )

    def _block_held(
        self, candidate_id: uuid.UUID, topics: Iterable[str], now: datetime
    ) -> dict[str, datetime]:
        """Темы, блок по которым ещё держит интервал, — с датой, когда можно (§6)."""
        return topic_blocks_held(
            self._attempts.attempts(candidate_id),
            topics,
            now,
            timedelta(days=self._mechanics.topic_block_interval_days),
        )

    def _narrowing(
        self,
        candidate_id: uuid.UUID,
        specialization: str,
        levels: dict[str, Normal],
        now: datetime,
    ) -> Narrowed:
        """Прогноз уровня темы после блока по ней; наблюдения профиля читаются один раз и только
        если прогноз спросили."""
        mechanics = self._mechanics
        codes = list(levels)
        history: list[Observation] | None = None

        def narrowed(topic: str) -> Normal | None:
            nonlocal history
            discrimination = self._discrimination(topic)
            if discrimination is None:
                return None
            if history is None:
                history = profile_observations(
                    self._attempts,
                    self._tasks,
                    mechanics,
                    candidate_id,
                    specialization,
                    codes,
                    fsp_evidence(self._attempts, self._fsp, candidate_id),
                )
            # Ожидаемый исход при p = ½: каждое задание — верный и неверный ответ с половинным
            # весом. Исходы ровно поровну при любом `topic_block_items`, μ не сдвигается.
            block = [
                Observation(
                    topic,
                    correct,
                    discrimination,
                    levels[topic].mean,
                    weight=mechanics.trust_weight_test / 2,
                    at=now,
                    source=SignalSource.test,
                )
                for _ in range(mechanics.topic_block_items)
                for correct in (True, False)
            ]
            estimate = self._skill_model.estimate(
                profile_prior(codes, mechanics), [*history, *block], to_mode=True
            )
            return estimate.topic(topic)

        return narrowed

    def _discrimination(self, topic: str) -> float | None:
        """Средняя разделяющая сила семейств темы в выдаче; семейств нет — блоку нечем спросить."""
        params = self._calibration.current(bank.families_for_topics([topic]))
        if not params:
            return None
        return statistics.fmean(p.discrimination for p in params.values())
