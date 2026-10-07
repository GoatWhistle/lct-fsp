"""Единица работы над in-memory хранилищем: откат возвращает снимок на начало блока."""

import copy
from collections.abc import Hashable
from types import TracebackType
from typing import Any, Self

Snapshot = dict[str, dict[Hashable, Any]]


class MemoryStore:
    """Данные in-memory репозиториев — коллекции по имени. Коллекция — словарь по ключу записи.

    Репозитории берут коллекцию через `collection` на каждую операцию и не держат копий
    записей: откат меняет содержимое коллекций на месте.
    """

    def __init__(self) -> None:
        self._collections: Snapshot = {}

    def collection(self, name: str) -> dict[Hashable, Any]:
        return self._collections.setdefault(name, {})

    def snapshot(self) -> Snapshot:
        return copy.deepcopy(self._collections)

    def restore(self, snapshot: Snapshot) -> None:
        for name, records in self._collections.items():
            records.clear()
            records.update(snapshot.get(name, {}))


class MemoryUnitOfWork:
    """Реализация порта `UnitOfWork`. Записанное видно сразу, откат — восстановление снимка."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self._snapshot: Snapshot | None = None

    def __enter__(self) -> Self:
        if self._snapshot is not None:
            raise RuntimeError("единица работы уже открыта")
        self._snapshot = self.store.snapshot()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        snapshot, self._snapshot = self._snapshot, None
        if exc_type is not None and snapshot is not None:
            self.store.restore(snapshot)
