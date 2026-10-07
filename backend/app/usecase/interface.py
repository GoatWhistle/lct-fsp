"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, сборка — в
`backend/main.py`.
"""

from collections.abc import Iterable
from types import TracebackType
from typing import Protocol, Self

from app.domain.skill import Observation, Prior, SkillEstimate


class SkillModel(Protocol):
    """Модель навыка (mechanics.md, §3): уровень по темам из априорного и наблюдений.

    Сейчас — IRT 2PL с иерархическим априорным, модуль `app.skills.irt`. Оценка детерминирована:
    те же априорное и наблюдения в том же порядке дают ту же оценку.
    """

    def initial(self, prior: Prior) -> SkillEstimate:
        """Оценка без наблюдений — только по априорному."""
        ...

    def estimate(self, prior: Prior, observations: Iterable[Observation]) -> SkillEstimate:
        """Оценка по априорному и упорядоченным наблюдениям."""
        ...


class UnitOfWork(Protocol):
    """Единица работы — граница транзакции: один вызов сценария — один блок `with uow:`.

    Выход из блока без исключения фиксирует всё записанное в нём, с исключением — откатывает и
    пробрасывает исключение дальше. Блоки идут по очереди, вложенный вход — ошибка. Кроме
    единицы работы изменения не фиксирует никто: ни репозитории, ни сценарии. Сейчас — Postgres
    (`app.repository.unit_of_work`) и in-memory для тестов и стенда валидации
    (`app.repository.memory`).
    """

    def __enter__(self) -> Self:
        """Начало блока; вложенный вход — `RuntimeError`."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Фиксация без исключения, откат с исключением; исключение не глотается."""
        ...
