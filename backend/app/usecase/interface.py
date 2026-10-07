"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, сборка — в
`backend/main.py`.
"""

from collections.abc import Iterable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.domain.candidate import ProfileSheet
from app.domain.mail import Mail
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


class Mailer(Protocol):
    """Почта — внешняя система. Отправка не роняет сценарий: письмо, которое не ушло,
    кандидат запрашивает повторно."""

    def send(self, mail: Mail) -> None: ...


class ProfilePdfRenderer(Protocol):
    """Рендер PDF-профиля. Показывает проекцию как есть: что в неё попало, решил сценарий."""

    def render(self, sheet: ProfileSheet, *, now: datetime) -> bytes:
        """PDF; `now` — дата формирования в подвале и метаданных."""
        ...


class Clock(Protocol):
    """Источник «сейчас»: сроки, интервалы, время ответа и временные метки берутся отсюда.

    Сценарий читает момент один раз и передаёт его в домен значением.
    """

    def now(self) -> datetime:
        """Текущий момент — aware `datetime` в UTC."""
        ...


class SeedSource(Protocol):
    """Источник seed механики: выбор задания, экземпляр задания, соль ничьих в выдаче.

    Сценарий берёт seed здесь и строит из него генератор; домен получает готовое значение.
    """

    def seed(self) -> int:
        """Очередной seed — неотрицательное целое меньше 2⁶³: столько держит колонка seed."""
        ...


class UnitOfWork(Protocol):
    """Единица работы — граница транзакции: блок `with uow:` в сценарии. Обычно вызов сценария —
    один блок; отдельным блоком идёт только то, что по механике не отменяет основной шаг
    (калибровка после ответа, mechanics.md §7).

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
