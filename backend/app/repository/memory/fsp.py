"""Снимки достижений ФСП в памяти — для сценарных тестов и стенда валидации. Снимок кладёт тест
или стенд: `put`; дисциплины — из того же справочника, что у прода."""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime

from app.domain.catalog import FspDiscipline
from app.domain.fsp import FspAchievement, FspSnapshot
from app.repository.memory.unit_of_work import MemoryStore


class MemoryFspEvidence:
    def __init__(self, store: MemoryStore, disciplines: Iterable[FspDiscipline]) -> None:
        self._store = store
        self._disciplines = {d.code: d for d in disciplines}

    def put(
        self, user_id: uuid.UUID, achievements: Sequence[FspAchievement], now: datetime
    ) -> None:
        self._store.collection("fsp_snapshots")[user_id] = FspSnapshot(tuple(achievements), now)

    def snapshot(self, user_id: uuid.UUID) -> FspSnapshot | None:
        snapshot: FspSnapshot | None = self._store.collection("fsp_snapshots").get(user_id)
        return snapshot

    def disciplines(self) -> dict[str, FspDiscipline]:
        return dict(self._disciplines)
