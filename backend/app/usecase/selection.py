"""Сценарии подборки (mechanics.md, §12–13): построить по потребности, открыть, список.

Перестроение — тот же сценарий «построить» по потребности подборки: каждый вызов — новая
подборка. Время, соль ничьих и P(принятия) приходят через порты, фиксирует единица работы.
"""

import math
import uuid
from datetime import timedelta

from app.domain.selection import (
    Page,
    SelectionDraft,
    SelectionRules,
    Summary,
    acceptance_features,
    arrange,
    need_snapshot,
    score,
    showcase,
)
from app.domain.skill import Normal
from app.usecase.interface import (
    AcceptanceModel,
    CandidatePool,
    Clock,
    NeedReader,
    SeedSource,
    SelectionRepository,
    SkillModel,
    UnitOfWork,
)
from app.usecase.skill_profile import ProfileFreshness
from settings import Mechanics


def selection_rules(mechanics: Mechanics) -> SelectionRules:
    spread = math.hypot(mechanics.theta_prior_sd, mechanics.topic_deviation_sd)
    return SelectionRules(
        stack_cap=mechanics.self_reported_stack_cap,
        nearby_grade_distance=mechanics.nearby_grade_distance,
        verdict_bands=tuple(mechanics.confidence_language_bands),
        low_data_sd=mechanics.topic_low_data_sd,
        stale_after=timedelta(days=mechanics.profile_stale_days),
        missing_level=Normal(0.0, mechanics.level_sd_inflation * spread),
    )


class Selections:
    def __init__(
        self,
        uow: UnitOfWork,
        needs: NeedReader,
        pool: CandidatePool,
        selections: SelectionRepository,
        acceptance: AcceptanceModel,
        skill_model: SkillModel,
        clock: Clock,
        seeds: SeedSource,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._needs = needs
        self._pool = pool
        self._selections = selections
        self._acceptance = acceptance
        self._clock = clock
        self._seeds = seeds
        self._mechanics = mechanics
        self._rules = selection_rules(mechanics)
        self._freshness = ProfileFreshness(skill_model, mechanics)

    def build(self, user_id: uuid.UUID, need_id: uuid.UUID, *, limit: int) -> Page:
        """Строит подборку по текущей потребности и профилям навыков на «сейчас» и сохраняет её;
        отдаёт первую страницу. Тот же seed на тех же входах даёт ту же выдачу."""
        mechanics, rules = self._mechanics, self._rules
        with self._uow:
            now = self._clock.now()
            need = self._needs.get(user_id, need_id)
            snapshot = need_snapshot(
                need,
                requirement=mechanics.grade_thresholds[need.grade.code],
                importance_weights=mechanics.need_importance_weights,
                key_min_technologies=mechanics.need_key_topic_min_technologies,
            )
            pool = [
                self._freshness.pool(member, now)
                for member in self._pool.in_reach(
                    need.specialization.code,
                    need.grade.rank,
                    rules.nearby_grade_distance,
                    [t.code for t in need.stack],
                )
            ]
            scored = score(snapshot, need.grade.rank, pool, rules)
            showcased = showcase(
                snapshot,
                self._pool.unconfirmed(
                    need.specialization.code, need.grade.code, [t.code for t in need.stack]
                ),
            )
            acceptance = self._acceptance.predict(
                [acceptance_features(snapshot, item) for item in scored]
            )
            now = self._clock.now()
            entries = arrange(
                scored,
                acceptance,
                showcased=showcased,
                salt=self._seeds.seed(),
                now=now,
                rules=rules,
            )
            draft = SelectionDraft(user_id, need.id, snapshot, rules.stack_cap, now)
            selection = self._selections.add(draft, entries)
            return self._selections.page(user_id, selection.id, offset=0, limit=limit)

    def open(self, user_id: uuid.UUID, selection_id: uuid.UUID, *, offset: int, limit: int) -> Page:
        """Сохранённая выдача — та же при каждом открытии; чужая подборка — `SelectionNotFound`."""
        with self._uow:
            return self._selections.page(user_id, selection_id, offset=offset, limit=limit)

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        """Список подборок работодателя, новые сверху."""
        with self._uow:
            return self._selections.summaries(user_id, need_id, limit=limit)
