"""Потребности, пул кандидатов и подборки в памяти — для сценарных тестов и стенда валидации.

Данные кладёт тест или стенд: `put` у потребностей, `add` и `add_unconfirmed` у пула.
Досягаемость в пуле — та же доменная функция `block_of`, что задаёт блоки подборки.
"""

import dataclasses
import uuid
from collections.abc import Collection, Sequence
from datetime import datetime

from app.domain.candidate import grade_status
from app.domain.errors import NeedNotFound, SelectionNotFound
from app.domain.feedback import CandidateSelection
from app.domain.search import CandidateFacts, CandidateFilters
from app.domain.selection import (
    Need,
    PoolCandidate,
    Selection,
    SelectionDraft,
    SelectionEntry,
    Summary,
    UnconfirmedCandidate,
    block_of,
    block_totals,
)
from app.domain.skill import SkillProfileLevels
from app.repository.memory.unit_of_work import MemoryStore


class MemoryNeeds:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def put(self, user_id: uuid.UUID, need: Need) -> None:
        self._store.collection("needs")[need.id] = (user_id, need)

    def get(self, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
        owner, need = self._store.collection("needs").get(need_id, (None, None))
        if need is None or owner != user_id:
            raise NeedNotFound()
        assert isinstance(need, Need)
        return need


class MemoryCandidatePool:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, candidate: PoolCandidate) -> None:
        self._store.collection("pool")[candidate.candidate_id] = candidate

    def in_reach(
        self, specialization: str, grade_rank: int, distance: int, technologies: Collection[str]
    ) -> list[PoolCandidate]:
        wanted = frozenset(technologies)
        return [
            dataclasses.replace(c, stack=c.stack & wanted)
            for c in self._store.collection("pool").values()
            if c.specialization == specialization
            and block_of(grade_rank, c.grade.rank, distance) is not None
        ]

    def add_unconfirmed(self, candidate: UnconfirmedCandidate) -> None:
        self._store.collection("unconfirmed")[candidate.candidate_id] = candidate

    def unconfirmed(
        self, specialization: str, grade: str, technologies: Collection[str]
    ) -> list[UnconfirmedCandidate]:
        wanted = frozenset(technologies)
        # Категория — только в `add`: кандидат с ней в нижний блок не попадает, как и в Postgres.
        categorized = self._store.collection("pool")
        return [
            dataclasses.replace(c, stack=c.stack & wanted)
            for c in self._store.collection("unconfirmed").values()
            if c.specialization == specialization
            and c.claimed.code == grade
            and c.candidate_id not in categorized
        ]

    def facts(self, candidate_ids: Collection[uuid.UUID]) -> list[CandidateFacts]:
        wanted = frozenset(candidate_ids)
        return [f for f in self.searchable() if f.candidate_id in wanted]

    def searchable(self) -> list[CandidateFacts]:
        categorized = self._store.collection("pool")
        found = [_pool_facts(c) for c in categorized.values()]
        found.extend(
            _unconfirmed_facts(c)
            for c in self._store.collection("unconfirmed").values()
            if c.candidate_id not in categorized
        )
        return found


def _pool_facts(candidate: PoolCandidate) -> CandidateFacts:
    status = grade_status(candidate.grade, candidate.claimed)
    assert status is not None
    return CandidateFacts(
        candidate_id=candidate.candidate_id,
        specialization=candidate.specialization,
        status=status,
        stack=candidate.stack,
        # Достижений в пуле нет — есть темы, подтверждённые ФСП.
        fsp_confirmed=bool(candidate.fsp_topics),
        profile=SkillProfileLevels(
            candidate.overall, candidate.levels, 0, candidate.last_signal_at
        ),
    )


def _unconfirmed_facts(candidate: UnconfirmedCandidate) -> CandidateFacts:
    status = grade_status(None, candidate.claimed)
    assert status is not None
    return CandidateFacts(
        candidate.candidate_id, candidate.specialization, status, candidate.stack, False, None
    )


class MemorySelections:
    """Подборки по порядку сохранения; id — по номеру: на стенде прогон воспроизводим."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, draft: SelectionDraft, entries: Sequence[SelectionEntry]) -> Selection:
        selections = self._store.collection("selections")
        selection = Selection(**vars(draft), id=uuid.UUID(int=len(selections) + 1))
        selections[selection.id] = (selection, tuple(entries))
        return selection

    def get(
        self, user_id: uuid.UUID, selection_id: uuid.UUID
    ) -> tuple[Selection, tuple[SelectionEntry, ...]]:
        selection, entries = self._store.collection("selections").get(selection_id, (None, ()))
        if selection is None or selection.user_id != user_id:
            raise SelectionNotFound()
        return selection, entries

    def save_filters(self, selection_id: uuid.UUID, filters: CandidateFilters) -> None:
        selections = self._store.collection("selections")
        selection, entries = selections[selection_id]
        selections[selection_id] = (dataclasses.replace(selection, filters=filters), entries)

    def set_shortlisted(
        self, selection_id: uuid.UUID, candidate_id: uuid.UUID, shortlisted: bool
    ) -> None:
        selections = self._store.collection("selections")
        selection, entries = selections[selection_id]
        marked = set(selection.shortlist) - {candidate_id}
        if shortlisted:
            marked.add(candidate_id)
        listed = tuple(e.candidate_id for e in entries if e.candidate_id in marked)
        selections[selection_id] = (dataclasses.replace(selection, shortlist=listed), entries)

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        # Среди подборок одного момента новее та, что сохранена позже: id — по номеру.
        stored = sorted(
            self._store.collection("selections").values(),
            key=lambda s: (s[0].created_at, s[0].id.int),
            reverse=True,
        )
        return [
            Summary(selection, block_totals(entries))
            for selection, entries in stored
            if selection.user_id == user_id and need_id in (None, selection.need_id)
        ][:limit]

    def with_candidate(self, candidate_id: uuid.UUID, since: datetime) -> list[CandidateSelection]:
        found = []
        for selection, entries in self._store.collection("selections").values():
            own = next((e for e in entries if e.candidate_id == candidate_id), None)
            if own is None or selection.created_at < since:
                continue
            found.append(
                CandidateSelection(
                    selection_id=selection.id,
                    owner=selection.user_id,
                    need_id=selection.need_id,
                    need=selection.need,
                    stack_cap=selection.stack_cap,
                    created_at=selection.created_at,
                    position=own.position,
                    block=own.block,
                    neighbors=tuple(
                        e.match_score
                        for e in entries
                        if e.block is own.block
                        and e.candidate_id != candidate_id
                        and e.match_score is not None
                    ),
                )
            )
        return sorted(found, key=lambda s: (s.created_at, s.selection_id.int))
