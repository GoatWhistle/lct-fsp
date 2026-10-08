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
        # Блок без отката упал на середине: записи могут быть недописаны.
        self.broken = False

    def collection(self, name: str) -> dict[Hashable, Any]:
        return self._collections.setdefault(name, {})

    def snapshot(self) -> Snapshot:
        return copy.deepcopy(self._collections)

    def restore(self, snapshot: Snapshot) -> None:
        for name, records in self._collections.items():
            records.clear()
            records.update(snapshot.get(name, {}))


class MemoryUnitOfWork:
    """Реализация порта `UnitOfWork`. Записанное видно сразу, откат — восстановление снимка.

    Снимок — копия всего хранилища на каждый блок. Стенду валидации на тысячах попыток она не по
    карману, и он берёт единицу работы без отката (`rollback=False`): исключение в блоке портит
    хранилище, и следующий вход в любую его единицу работы — `RuntimeError`. Прогон стенда
    обрывается, а не продолжается на недописанных записях.
    """

    def __init__(self, store: MemoryStore, *, rollback: bool = True) -> None:
        self.store = store
        self._rollback = rollback
        self._snapshot: Snapshot | None = None
        self._open = False

    def __enter__(self) -> Self:
        if self._open:
            raise RuntimeError("единица работы уже открыта")
        if self.store.broken:
            raise RuntimeError("хранилище испорчено блоком без отката, который упал")
        self._open = True
        self._snapshot = self.store.snapshot() if self._rollback else None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        snapshot, self._snapshot, self._open = self._snapshot, None, False
        if exc_type is None:
            return
        if snapshot is not None:
            self.store.restore(snapshot)
        else:
            self.store.broken = True
