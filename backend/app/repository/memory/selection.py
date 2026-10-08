"""Потребности, пул кандидатов и подборки в памяти — для сценарных тестов и стенда валидации.

Данные кладёт тест или стенд: `put` у потребностей, `add` и `add_unconfirmed` у пула.
Досягаемость в пуле — та же доменная функция `block_of`, что задаёт блоки подборки.
"""

import dataclasses
import uuid
from collections.abc import Collection, Sequence

from app.domain.errors import NeedNotFound, SelectionNotFound
from app.domain.selection import (
    Need,
    Page,
    PoolCandidate,
    Selection,
    SelectionDraft,
    SelectionEntry,
    Summary,
    UnconfirmedCandidate,
    block_of,
    block_totals,
)
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


class MemorySelections:
    """Подборки по порядку сохранения; id — по номеру: на стенде прогон воспроизводим."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, draft: SelectionDraft, entries: Sequence[SelectionEntry]) -> Selection:
        selections = self._store.collection("selections")
        selection = Selection(**vars(draft), id=uuid.UUID(int=len(selections) + 1))
        selections[selection.id] = (selection, tuple(entries))
        return selection

    def page(self, user_id: uuid.UUID, selection_id: uuid.UUID, *, offset: int, limit: int) -> Page:
        selection, entries = self._store.collection("selections").get(selection_id, (None, ()))
        if selection is None or selection.user_id != user_id:
            raise SelectionNotFound()
        return Page(selection, block_totals(entries), entries[offset : offset + limit], offset)

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
