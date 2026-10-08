"""Сценарии подборки (mechanics.md, §12–13): построить по потребности или черновику, открыть,
список.

Перестроение — тот же сценарий «построить» по потребности подборки: каждый вызов — новая
подборка. Время, соль ничьих и P(принятия) приходят через порты, фиксирует единица работы.
"""

import math
import uuid
from datetime import timedelta

from app.domain.need import NeedForm, need_content
from app.domain.selection import (
    NeedContent,
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
    CatalogRepository,
    Clock,
    NeedReader,
    SeedSource,
    SelectionRepository,
    UnitOfWork,
)
from app.usecase.need import terms_of
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
        catalog: CatalogRepository,
        pool: CandidatePool,
        selections: SelectionRepository,
        acceptance: AcceptanceModel,
        clock: Clock,
        seeds: SeedSource,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._needs = needs
        self._catalog = catalog
        self._pool = pool
        self._selections = selections
        self._acceptance = acceptance
        self._clock = clock
        self._seeds = seeds
        self._mechanics = mechanics
        self._rules = selection_rules(mechanics)

    def build(self, user_id: uuid.UUID, need_id: uuid.UUID, *, limit: int) -> Page:
        """Строит подборку по текущей потребности и профилям навыков и сохраняет её; отдаёт
        первую страницу. Тот же seed на тех же входах даёт ту же выдачу."""
        with self._uow:
            return self._build(user_id, need_id, self._needs.get(user_id, need_id), limit)

    def build_draft(self, user_id: uuid.UUID, form: NeedForm, *, limit: int) -> Page:
        """Подборка по черновику потребности до сохранения — форма после правки человеком. Та же
        выдача, что у сохранённой потребности с теми же полями; подборка не ссылается на
        потребность. Правка черновика и новый вызов — новая подборка, прежняя остаётся."""
        with self._uow:
            need = need_content(terms_of(form, self._catalog), self._clock.now())
            return self._build(user_id, None, need, limit)

    def _build(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, need: NeedContent, limit: int
    ) -> Page:
        mechanics, rules = self._mechanics, self._rules
        snapshot = need_snapshot(
            need,
            requirement=mechanics.grade_thresholds[need.grade.code],
            importance_weights=mechanics.need_importance_weights,
            key_min_technologies=mechanics.need_key_topic_min_technologies,
        )
        pool = self._pool.in_reach(
            need.specialization.code,
            need.grade.rank,
            rules.nearby_grade_distance,
            [t.code for t in need.stack],
        )
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
        draft = SelectionDraft(user_id, need_id, snapshot, rules.stack_cap, now)
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
