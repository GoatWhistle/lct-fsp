"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, сборка — в
`backend/main.py`.
"""

import random
import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.domain import bank
from app.domain.adaptive import Blueprint, Choice, Option
from app.domain.attempt import (
    AnsweredPresentation,
    Attempt,
    PathState,
    Presentation,
    Survey,
)
from app.domain.calibration import AnchorAnswer, CalibratedFamily, Link, Parameters, Response
from app.domain.candidate import Candidate, ProfileForm, ProfileSheet
from app.domain.candidate import SkillProfile as SkillProfileView
from app.domain.catalog import Topic
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
from app.domain.skill import Normal, Observation, Prior, SkillEstimate, SkillProfileLevels


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


class AttemptRepository(AttemptReader, Protocol):
    """Путь кандидата на запись: опросы, попытки, предъявления, категория и профиль навыков —
    дополняет порт чтения `AttemptReader`. Номера записей кандидата считает сам под блокировкой
    `lock_candidate`. Пишет только внутри единицы работы и сам не фиксирует. Сейчас — Postgres
    (`app.repository.attempt`) и in-memory (`app.repository.memory.attempt`)."""

    def lock_candidate(self, user_id: uuid.UUID) -> None:
        """Шаги пути одного кандидата идут по очереди: двойной клик не создаст две попытки."""
        ...

    def specialization_topics(self, code: str) -> tuple[Topic, ...] | None:
        """Темы специализации в порядке справочника; None — специализации нет."""
        ...

    def state(self, user_id: uuid.UUID) -> PathState:
        """Записи пути: последний опрос, последняя попытка с предъявлениями, категория."""
        ...

    def survey(self, survey_id: uuid.UUID) -> Survey: ...

    def add_survey(self, user_id: uuid.UUID, specialization_code: str, now: datetime) -> Survey:
        """Новый опрос кандидата; прежний остаётся историей."""
        ...

    def attempt_in_progress(self, user_id: uuid.UUID) -> Attempt | None:
        """Неостановленная попытка кандидата — одна или ни одной."""
        ...

    def add_attempt(
        self,
        user_id: uuid.UUID,
        survey: Survey,
        grade_code: str,
        continues: Attempt | None,
        now: datetime,
    ) -> Attempt:
        """Новая попытка; `continues` — попытка, чью оценку продолжает дотест каскада."""
        ...

    def add_presentation(
        self,
        attempt: Attempt,
        *,
        family_code: str,
        topic_code: str,
        seed: int,
        params: Mapping[str, object],
        discrimination: float,
        difficulty: float,
        level_before: Normal,
        shown_at: datetime,
    ) -> Presentation:
        """Показ нового задания — следующим по позиции; добавляется и в `attempt`."""
        ...

    def save_answer(self, presentation: Presentation) -> None:
        """Записывает ответ предъявления: response, correct, answered_at, response_time_ms."""
        ...

    def finish_attempt(self, attempt: Attempt) -> None:
        """Записывает остановку: finished_at, оценку, исход, грейд исхода и дату повтора."""
        ...

    def save_rest_levels(self, presentations: Sequence[Presentation]) -> None:
        """Записывает итоговые оценки темы без ответа — их ждёт переоценка семейств."""
        ...

    def add_category(self, attempt: Attempt, now: datetime) -> None:
        """Категория по присвоившей её попытке: специализация × грейд исхода."""
        ...

    def chain(self, attempt: Attempt) -> list[Attempt]:
        """Попытки определения категории от первой до `attempt` — без запроса на звено."""
        ...

    def exposure(
        self, specialization_code: str, current_attempt_id: uuid.UUID, window: int
    ) -> tuple[int, dict[str, int]]:
        """Окно показов: последние `window − 1` попыток специализации до текущей. Возвращает
        число попыток в окне и в скольких из них показано семейство."""
        ...

    def seen(self, user_id: uuid.UUID, current_attempt_id: uuid.UUID) -> dict[str, datetime]:
        """Семейства, которые кандидат видел в прошлых попытках, — с началом последней из них."""
        ...

    def profile(self, user_id: uuid.UUID, specialization_code: str) -> SkillProfileView | None:
        """Сохранённый профиль навыков с уровнями словами; темы — в порядке справочника."""
        ...

    def save_profile(
        self,
        user_id: uuid.UUID,
        specialization_code: str,
        levels: SkillProfileLevels,
        now: datetime,
    ) -> None:
        """Профиль кандидата по специализации — новый или поверх прежнего."""
        ...


class ItemSelector(Protocol):
    """Выбор следующего задания (mechanics.md, §6). Сейчас — максимум информации Фишера со
    случайным выбором из top-k и потолком доли показов (`app.adapter.adaptive`); размер пула и
    потолок реализация получает через конструктор.
    """

    def choose(
        self,
        blueprint: Blueprint,
        counts: Mapping[str, int],
        estimate: SkillEstimate,
        options: Sequence[Option],
        attempts_in_window: int,
        rng: random.Random,
    ) -> Choice | None:
        """Семейство следующего задания: `counts` — заданий по темам в текущей попытке,
        `estimate` — оценка для выбора заданий, `options` — семейства без скомпрометированных и
        уже показанных в этой попытке, `attempts_in_window` — попыток в окне показов. None —
        спрашивать нечего."""
        ...


class Calibration(Protocol):
    """Калибровка семейств (mechanics.md, §7). Сейчас — Эло со связкой шкалы по якорям и
    пакетной переоценкой (`app.adapter.calibration`); параметры из конфига механик реализация
    получает через конструктор, хранит состояние `CalibrationRepository`.

    Вызывается из сценария ответа: шаг по ответу, после остановки попытки — пересчёт связки и
    переоценка. Вынос калибровки из пути ответа — отдельная работа (окна, lct-65).
    """

    def current(self, families: Sequence[bank.Family]) -> dict[str, Parameters]:
        """Текущие параметры семейств в выдаче; до первого ответа — экспертные. Выведенных из
        выдачи в ответе нет."""
        ...

    def lock(self, codes: Iterable[str]) -> None:
        """Блокировка строк семейств до конца единицы работы — по порядку кодов: так
        транзакции, которые берут несколько семейств, не ждут друг друга по кругу."""
        ...

    def learn(
        self, specialization: str, family_code: str, level_before: Normal, correct: bool
    ) -> None:
        """Шаг Эло по ответу: сложность семейства сдвигается по неожиданности ответа."""
        ...

    def relink(self, specialization: str, now: datetime) -> None:
        """Пересчёт связок шкалы специализации по ответам на якорные семейства."""
        ...

    def refit_due(self, codes: Iterable[str], specialization: str, now: datetime) -> None:
        """Пакетная переоценка семейств из `codes`, набравших ответы с итоговыми оценками."""
        ...


class CalibrationRepository(Protocol):
    """Хранение калибровки: состояние семейств и связки шкалы. Пишет только внутри единицы
    работы и сам не фиксирует. Сейчас — Postgres (`app.repository.calibration`) и in-memory
    (`app.repository.memory.calibration`)."""

    def parameters(self, codes: Collection[str]) -> dict[str, CalibratedFamily]:
        """Состояния семейств, у которых они есть; без блокировки."""
        ...

    def locked(self, code: str, start: Parameters) -> CalibratedFamily:
        """Состояние семейства с блокировкой до конца единицы работы; записи нет — создаётся
        со стартовыми параметрами `start`."""
        ...

    def save(self, family: CalibratedFamily) -> None:
        """Записывает состояние, взятое через `locked`."""
        ...

    def links(self, specialization: str) -> tuple[Link, Link]:
        """Связки шкалы: по оценкам до ответа (для Эло) и без ответа (для переоценки);
        пока попыток не было — тождественные."""
        ...

    def save_links(self, specialization: str, before: Link, rest: Link, now: datetime) -> None:
        """Заменяет связки шкалы специализации."""
        ...

    def anchor_answers(
        self, specialization: str, anchors: Collection[str], window_attempts: int
    ) -> list[AnchorAnswer]:
        """Ответы на якорные семейства из последних `window_attempts` попыток специализации."""
        ...

    def rest_answers(self, code: str) -> list[Response]:
        """Ответы на семейство с итоговой оценкой кандидата — из остановленных попыток."""
        ...

    def ready_responses(self, code: str) -> int:
        """Сколько ответов на семейство уже с итоговой оценкой."""
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
