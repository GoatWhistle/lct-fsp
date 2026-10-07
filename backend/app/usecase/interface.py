"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, сборка — в
`backend/main.py`.
"""

import uuid
from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.domain.attempt import AnsweredPresentation
from app.domain.candidate import Candidate, ProfileForm, ProfileSheet
from app.domain.mail import Mail
from app.domain.selection import (
    AcceptanceFeatures,
    Need,
    Page,
    PoolCandidate,
    Selection,
    SelectionDraft,
    SelectionEntry,
    Summary,
)
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


class AttemptReader(Protocol):
    """Чтение попыток теста. Только чтение: записанное в текущей единице работы видно, но
    фиксирует его единица работы. Сейчас — Postgres (`app.repository.attempt`)."""

    def answered(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> Sequence[AnsweredPresentation]:
        """Отвеченные предъявления кандидата по специализации во всех попытках — в порядке
        ответа: по номеру попытки, внутри неё — по позиции."""
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


class CandidateRepository(Protocol):
    """Кандидаты — анкета, ожидаемая зарплата, категория и профиль навыков её специализации.

    Отдаёт кандидата целиком: что из этого увидит зритель, решает правило раскрытия
    (`app.domain.candidate.disclosure`), а не хранилище. Пишет только внутри единицы работы и
    сам не фиксирует. Сейчас — Postgres (`app.repository.candidate`).
    """

    def get(self, candidate_id: uuid.UUID) -> Candidate:
        """Кандидат по id. Чего у него нет, то `None`; у неизвестного id нет ничего."""
        ...

    def save_profile(self, candidate_id: uuid.UUID, form: ProfileForm, now: datetime) -> None:
        """Заменяет анкету целиком; `now` — время правки. Стек и сферы не из справочника —
        `UnknownTechnology` и `UnknownIndustry`."""
        ...


class AcceptanceModel(Protocol):
    """Модель принятия (mechanics.md, §13): P(кандидат примет приглашение) по признакам.

    Отдаёт только P — скор соответствия, вклады и порядок считает домен. Сейчас модели нет:
    заглушка `app.adapter.acceptance` отдаёт `None` — множитель 1, в выдаче `null`.
    """

    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        """P(принятия) в [0, 1] по порядку `features`; `None` — модель не знает."""
        ...


class NeedRepository(Protocol):
    """Потребности работодателя — для подборки."""

    def get(self, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
        """Потребность работодателя `user_id`; чужая или несуществующая — `NeedNotFound`."""
        ...


class CandidatePool(Protocol):
    """Кандидаты с категорией по тесту и профилем навыков её специализации."""

    def in_reach(
        self, specialization: str, grade_rank: int, distance: int, technologies: Collection[str]
    ) -> list[PoolCandidate]:
        """Категория — `specialization`, ранг грейда — не дальше `distance` от `grade_rank`
        (`app.domain.selection.block_of`). Стек кандидата — только из `technologies`, технологий
        потребности. Порядок не важен: его задаёт подборка."""
        ...


class SelectionRepository(Protocol):
    """Сохранённые подборки: снимок потребности и выдача. Формат хранения снимка и объяснения
    не зависит от схем API: сохранённые подборки открываются без миграции данных."""

    def add(self, draft: SelectionDraft, entries: Sequence[SelectionEntry]) -> Selection:
        """Сохраняет подборку с выдачей и даёт ей id."""
        ...

    def page(self, user_id: uuid.UUID, selection_id: uuid.UUID, *, offset: int, limit: int) -> Page:
        """Страница выдачи по местам; чужая или несуществующая подборка — `SelectionNotFound`."""
        ...

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        """Подборки работодателя, новые сверху; `need_id` — только по этой потребности."""
        ...
