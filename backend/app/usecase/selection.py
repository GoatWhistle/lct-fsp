"""Сценарии подборки (mechanics.md, §12–13): построить по потребности или черновику, открыть,
список, уточнить фильтрами, шортлист — и поиск по банку кандидатов.

Перестроение — тот же сценарий «построить» по потребности подборки: каждый вызов — новая
подборка. Время, соль ничьих и P(принятия) приходят через порты, фиксирует единица работы.

Фильтры на входе — доменная `CandidateFilters`: форма работодателя и чат-поиск зовут
`refine` и `search` одинаково, своей фильтрации у них нет.
"""

import dataclasses
import math
import uuid
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta

from app.domain.acceptance import SalaryHint, salary_hint
from app.domain.errors import NotInSelection
from app.domain.need import NeedForm, need_content
from app.domain.search import (
    CandidateFacts,
    CandidateFilters,
    SearchPage,
    admits,
    search_order,
)
from app.domain.selection import (
    AcceptanceDetails,
    AcceptanceFeatures,
    NeedContent,
    NeedSnapshot,
    Page,
    Scored,
    Selection,
    SelectionDraft,
    SelectionEntry,
    SelectionOrder,
    SelectionRules,
    Shortlist,
    Summary,
    acceptance_features,
    arrange,
    block_totals,
    in_order,
    need_snapshot,
    page_of,
    score,
    showcase,
)
from app.domain.skill import Normal
from app.domain.work import SalaryRange
from app.usecase.interface import (
    AcceptanceModel,
    CandidatePool,
    CatalogRepository,
    Clock,
    NeedReader,
    SeedSource,
    SelectionRepository,
    SkillModel,
    UnitOfWork,
)
from app.usecase.need import terms_of
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


def row_facts(
    entry: SelectionEntry, specialization: str, current: CandidateFacts | None
) -> CandidateFacts:
    """Факты для фильтра строки подборки: грейд и статус — те, что показывает строка, со
    снимком на момент построения; специализация — потребности. Стек, ФСП и профиль — сейчас;
    кандидата без статуса сейчас фильтры по ним не пропускают."""
    return CandidateFacts(
        candidate_id=entry.candidate_id,
        specialization=specialization,
        status=entry.status,
        stack=current.stack if current else frozenset(),
        fsp_confirmed=current.fsp_confirmed if current else False,
        profile=current.profile if current else None,
    )


def _shortlist(selection: Selection, entries: Sequence[SelectionEntry]) -> Shortlist:
    listed = set(selection.shortlist)
    return Shortlist(selection, tuple(e for e in entries if e.candidate_id in listed))


class Selections:
    def __init__(
        self,
        uow: UnitOfWork,
        needs: NeedReader,
        catalog: CatalogRepository,
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
        self._catalog = catalog
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
        now = self._clock.now()
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
        features = self._acceptance_features(user_id, snapshot, scored, now)
        acceptance = self._acceptance.predict(features)
        details = [
            None if why is None else AcceptanceDetails(f, why)
            for f, why in zip(features, self._acceptance.explain(features), strict=True)
        ]
        entries = arrange(
            scored,
            acceptance,
            details=details,
            showcased=showcased,
            salt=self._seeds.seed(),
            now=now,
            rules=rules,
        )
        draft = SelectionDraft(user_id, need_id, snapshot, rules.stack_cap, now)
        selection = self._selections.add(draft, entries)
        return page_of(
            Summary(selection, block_totals(entries)), entries, None, offset=0, limit=limit
        )

    def _acceptance_features(
        self, user_id: uuid.UUID, need: NeedSnapshot, scored: Sequence[Scored], now: datetime
    ) -> list[AcceptanceFeatures]:
        """Признаки модели принятия: к потребности и кандидату — загрузка кандидата на «сейчас» и
        сфера компании работодателя."""
        if not scored:
            return []
        ttl = timedelta(days=self._mechanics.invitation_ttl_days)
        load = self._pool.open_invitations(
            [item.candidate.candidate_id for item in scored], now - ttl
        )
        industry = self._needs.company_industry(user_id)
        return [
            acceptance_features(
                need,
                item,
                market_salary=self._mechanics.market_salary_median,
                open_invitations=load.get(item.candidate.candidate_id, 0),
                company_industry=industry,
            )
            for item in scored
        ]

    def open(
        self,
        user_id: uuid.UUID,
        selection_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        order: SelectionOrder = SelectionOrder.mutual,
    ) -> Page:
        """Сохранённая выдача — та же при каждом открытии — через последние применённые фильтры;
        чужая подборка — `SelectionNotFound`. `order` — вид выдачи: по S × P или только по S."""
        with self._uow:
            selection, entries = self._selections.get(user_id, selection_id)
            return self._page(selection, entries, offset=offset, limit=limit, order=order)

    def salary_hint(
        self,
        user_id: uuid.UUID,
        selection_id: uuid.UUID,
        candidate_id: uuid.UUID,
        salary: SalaryRange,
    ) -> SalaryHint | None:
        """Вероятность принятия при вилке `salary` и вилка до целевой вероятности — по признакам
        строки на момент построения подборки. `None` — модели нет, у потребности не было вилки
        или кандидат в нижнем блоке: P нет, подсказки нет. Кандидата нет в выдаче —
        `NotInSelection`."""
        with self._uow:
            _, entries = self._selections.get(user_id, selection_id)
        entry = next((e for e in entries if e.candidate_id == candidate_id), None)
        if entry is None:
            raise NotInSelection()
        if entry.acceptance is None:
            return None
        mechanics = self._mechanics
        return salary_hint(
            entry.acceptance.features,
            salary,
            self._acceptance.predict,
            target=mechanics.acceptance_target_probability,
            step=mechanics.salary_hint_rounding_rub,
            market_ratio=mechanics.salary_hint_market_ratio,
        )

    def refine(
        self,
        user_id: uuid.UUID,
        selection_id: uuid.UUID,
        filters: CandidateFilters,
        *,
        offset: int,
        limit: int,
        order: SelectionOrder = SelectionOrder.mutual,
    ) -> Page:
        """Заменяет фильтры подборки и отдаёт выдачу через них. Выдача только сужается: скоры и
        порядок — сохранённые (или только по S, если `order` так просит); пустые фильтры —
        исходная выдача."""
        with self._uow:
            selection, entries = self._selections.get(user_id, selection_id)
            self._selections.save_filters(selection.id, filters)
            selection = dataclasses.replace(selection, filters=filters)
            return self._page(selection, entries, offset=offset, limit=limit, order=order)

    def shortlist(
        self, user_id: uuid.UUID, selection_id: uuid.UUID, candidate_id: uuid.UUID, listed: bool
    ) -> Shortlist:
        """Отмечает кандидата выдачи или снимает отметку. Кандидата нет в выдаче подборки —
        `NotInSelection`."""
        with self._uow:
            selection, entries = self._selections.get(user_id, selection_id)
            if all(e.candidate_id != candidate_id for e in entries):
                raise NotInSelection()
            self._selections.set_shortlisted(selection.id, candidate_id, listed)
            return _shortlist(*self._selections.get(user_id, selection_id))

    def shortlisted(self, user_id: uuid.UUID, selection_id: uuid.UUID) -> Shortlist:
        """Шортлист в порядке выдачи — без фильтров подборки."""
        with self._uow:
            return _shortlist(*self._selections.get(user_id, selection_id))

    def search(self, filters: CandidateFilters, *, offset: int, limit: int) -> SearchPage:
        """Поиск по всему банку без потребности: подтверждённые — по уверенности в уровне
        грейда категории, неподтверждённые — ниже всех."""
        with self._uow:
            found = self._pool.searchable()
        now = self._clock.now()
        admitted = [f for f in self._fresh(found, now) if self._admits(filters, f)]
        hits = search_order(admitted, self._mechanics.grade_thresholds)
        return SearchPage(
            filters=filters,
            total=len(hits),
            unconfirmed_total=sum(h.facts.status.confirmed is None for h in hits),
            hits=tuple(hits[offset : offset + limit]),
            offset=offset,
        )

    def _page(
        self,
        selection: Selection,
        entries: Sequence[SelectionEntry],
        *,
        offset: int,
        limit: int,
        order: SelectionOrder = SelectionOrder.mutual,
    ) -> Page:
        summary = Summary(selection, block_totals(entries))
        filters = selection.filters
        entries = in_order(entries, order)
        if filters.empty:
            return page_of(summary, entries, None, offset=offset, limit=limit)
        current = {
            f.candidate_id: f
            for f in self._fresh(
                self._pool.facts([e.candidate_id for e in entries]), self._clock.now()
            )
        }
        specialization = selection.need.specialization.code
        admitted = {
            e.candidate_id
            for e in entries
            if self._admits(filters, row_facts(e, specialization, current.get(e.candidate_id)))
        }
        return page_of(summary, entries, admitted, offset=offset, limit=limit)

    def _admits(self, filters: CandidateFilters, facts: CandidateFacts) -> bool:
        return admits(filters, facts, confident_sd=self._mechanics.search_confident_sd)

    def _fresh(self, found: Collection[CandidateFacts], now: datetime) -> list[CandidateFacts]:
        """Профили навыков — на «сейчас»: погрешность без новых сигналов растёт."""
        return [
            f
            if f.profile is None
            else dataclasses.replace(f, profile=self._freshness.levels(f.profile, now))
            for f in found
        ]

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        """Список подборок работодателя, новые сверху."""
        with self._uow:
            return self._selections.summaries(user_id, need_id, limit=limit)
