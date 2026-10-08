"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, выбор реализаций —
в точках сборки `backend/main.py` и `backend/validation/main.py`.
"""

import random
import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.domain import bank
from app.domain.account import Account, Credentials, EmailVerification, Role
from app.domain.adaptive import Blueprint, Choice, Option
from app.domain.attempt import (
    AnsweredPresentation,
    Attempt,
    AttemptPurpose,
    CategoryChange,
    PathState,
    Presentation,
    Survey,
)
from app.domain.calibration import (
    AnchorAnswer,
    CalibratedFamily,
    ExpertGap,
    Link,
    Parameters,
    Response,
)
from app.domain.candidate import Candidate, ProfileForm, ProfileSheet
from app.domain.candidate import SkillProfile as SkillProfileView
from app.domain.catalog import (
    Catalog,
    CatalogPart,
    CatalogPlan,
    FspDiscipline,
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
)
from app.domain.company import Company, CompanyForm
from app.domain.conversation import Message, Side
from app.domain.feedback import CandidateSelection
from app.domain.fsp import (
    FspAchievement,
    FspAuthorization,
    FspHistory,
    FspIdentity,
    FspSnapshot,
)
from app.domain.invitation import Invitation, InvitationTerms
from app.domain.mail import Mail
from app.domain.need import NeedRecord, NeedTerms
from app.domain.need_draft import NeedDraft, OutOfCatalog
from app.domain.regular_task import (
    AnsweredTask,
    CatalogFilter,
    OwnAnswer,
    RegularTask,
    TaskAnswer,
    TaskTerms,
)
from app.domain.search import CandidateFacts, CandidateFilters
from app.domain.selection import (
    AcceptanceFeatures,
    Need,
    PoolCandidate,
    Selection,
    SelectionDraft,
    SelectionEntry,
    Summary,
    UnconfirmedCandidate,
)
from app.domain.skill import Normal, Observation, Prior, SkillEstimate, SkillProfileLevels


class SkillModel(Protocol):
    """Модель навыка (mechanics.md, §3): уровень по темам из априорного и наблюдений.

    Сейчас — IRT 2PL с иерархическим априорным, модуль `app.adapter.irt`. Оценка детерминирована:
    те же априорное и наблюдения в том же порядке дают ту же оценку.
    """

    def initial(self, prior: Prior) -> SkillEstimate:
        """Оценка без наблюдений — только по априорному."""
        ...

    def estimate(
        self, prior: Prior, observations: Iterable[Observation], *, to_mode: bool = False
    ) -> SkillEstimate:
        """Оценка по априорному и упорядоченным наблюдениям — на момент последнего из них. Оценка
        теста — шаг на наблюдение, профиль навыков — `to_mode`: каждое наблюдение до сходимости
        моды (§3, §11). С затуханием в априорном (`decay_sd_per_year`) между наблюдениями растёт
        погрешность."""
        ...

    def advance(
        self, prior: Prior, levels: SkillProfileLevels, now: datetime
    ) -> SkillProfileLevels:
        """Сохранённый профиль, посчитанный на момент последнего сигнала, — на момент `now`:
        без новых сигналов погрешность растёт (mechanics.md, §11, «Свежесть»)."""
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


class RegularTaskReader(Protocol):
    """Чтение ответов на регулярные задания — для профиля навыков. Сейчас — Postgres
    (`app.repository.regular_task`) и in-memory (`app.repository.memory.regular_task`)."""

    def answered(self, user_id: uuid.UUID, specialization_code: str) -> Sequence[AnsweredTask]:
        """Ответы кандидата на задания специализации — и снятых тоже: их наблюдения остаются в
        профиле. По времени ответа."""
        ...


class RegularTaskRepository(RegularTaskReader, Protocol):
    """Регулярные задания работодателей и ответы кандидатов (mechanics.md, §11). Пишет только
    внутри единицы работы и сам не фиксирует."""

    def add(self, author_id: uuid.UUID, terms: TaskTerms, now: datetime) -> RegularTask: ...

    def get(self, task_id: uuid.UUID, *, lock: bool = False) -> RegularTask | None:
        """Задание по id — любого автора, и снятое тоже. `lock` — блокировка до конца единицы
        работы: правка и первый ответ не проходят одновременно."""
        ...

    def replace(self, task_id: uuid.UUID, terms: TaskTerms, now: datetime) -> None:
        """Заменяет условие задания целиком; без ответов — это проверил сценарий."""
        ...

    def withdraw(self, task_id: uuid.UUID, now: datetime) -> None:
        """Снимает задание из каталога; повторное снятие момент не меняет."""
        ...

    def by_author(self, author_id: uuid.UUID) -> list[RegularTask]:
        """Задания работодателя, новые сверху, и снятые тоже."""
        ...

    def catalog(self, specialization_code: str, filters: CatalogFilter) -> list[RegularTask]:
        """Активные задания специализации всех грейдов; порядок задаёт домен."""
        ...

    def answer(self, task_id: uuid.UUID, candidate_id: uuid.UUID) -> TaskAnswer | None:
        """Ответ кандидата на задание — один или ни одного."""
        ...

    def add_answer(
        self,
        task_id: uuid.UUID,
        candidate_id: uuid.UUID,
        response: str,
        correct: bool | None,
        now: datetime,
    ) -> TaskAnswer:
        """Новый ответ; второй ответ того же кандидата — `TaskAlreadyAnswered`."""
        ...

    def answers(self, task_id: uuid.UUID) -> list[TaskAnswer]:
        """Ответы на задание по времени ответа."""
        ...

    def get_answer(self, answer_id: uuid.UUID) -> TaskAnswer | None: ...

    def answered_task_ids(self, candidate_id: uuid.UUID) -> set[uuid.UUID]:
        """Задания, на которые кандидат уже ответил."""
        ...

    def own_answers(self, candidate_id: uuid.UUID) -> list[OwnAnswer]:
        """Ответы кандидата с заданиями, новые сверху."""
        ...

    def grade(self, answer_id: uuid.UUID, rubric: int, now: datetime) -> TaskAnswer:
        """Оценка ответа по рубрике; что оценивать можно, проверил сценарий."""
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

    def profiled_specializations(self, user_id: uuid.UUID) -> list[str]:
        """Специализации, по которым у кандидата есть профиль навыков, — их пересчитывает новый
        сигнал вне теста."""
        ...

    def state(self, user_id: uuid.UUID) -> PathState:
        """Записи пути: последний опрос, последняя попытка пути с предъявлениями — без блоков по
        теме, — категория."""
        ...

    def survey(self, survey_id: uuid.UUID) -> Survey: ...

    def add_survey(self, user_id: uuid.UUID, specialization_code: str, now: datetime) -> Survey:
        """Новый опрос кандидата; прежний остаётся историей."""
        ...

    def attempt_in_progress(self, user_id: uuid.UUID) -> Attempt | None:
        """Неостановленная попытка кандидата любого назначения — одна или ни одной."""
        ...

    def add_attempt(
        self,
        user_id: uuid.UUID,
        survey: Survey,
        grade_code: str,
        continues: Attempt | None,
        now: datetime,
        purpose: AttemptPurpose = AttemptPurpose.determination,
        topic_code: str | None = None,
    ) -> Attempt:
        """Новая попытка; `continues` — попытка, чью оценку продолжает дотест каскада,
        `topic_code` — тема блока по теме."""
        ...

    def attempts(self, user_id: uuid.UUID) -> list[Attempt]:
        """Все попытки кандидата по номеру, и блоки по теме тоже, — для истории, правила
        ожидания и интервала блока; предъявления реализация может не загружать."""
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
        """Категория по присвоившей её попытке: специализация × грейд исхода. В журнал
        категории — запись первичного определения."""
        ...

    def raise_category(self, attempt: Attempt, now: datetime) -> None:
        """Грейд категории — по прошедшей попытке вверх; в журнал — смена вверх."""
        ...

    def lower_category(self, user_id: uuid.UUID, grade_code: str, now: datetime) -> None:
        """Грейд категории ниже — по той же оценке, без попытки; в журнал — смена вниз."""
        ...

    def category_changes(self, user_id: uuid.UUID) -> list[CategoryChange]:
        """Журнал категории кандидата по порядку записей."""
        ...

    def chain(self, attempt: Attempt) -> list[Attempt]:
        """Попытки определения категории от первой до `attempt` — без запроса на звено."""
        ...

    def exposure(
        self, specialization_code: str, current_attempt_id: uuid.UUID, window: int
    ) -> tuple[int, dict[str, int]]:
        """Окно показов без текущей попытки: последние `window − 1` попыток специализации, где
        было хотя бы одно предъявление, включая идущие. Возвращает число попыток в окне и в
        скольких из них показано семейство."""
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

    Калибрует сценарий калибровки (`app.usecase.calibration`) после фиксации ответа: шаг по
    ответу, после остановки попытки — пересчёт связки и переоценка. Путь кандидата берёт у
    порта только текущие параметры семейств.
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
        """Пакетная переоценка семейств из `codes`, набравших ответы с итоговыми оценками.
        Опорная сложность легче экспертной больше допустимого — семейство выводится из выдачи."""
        ...

    def expert_gaps(self, families: Sequence[bank.Family]) -> dict[str, ExpertGap]:
        """Семейства, чья опорная сложность разошлась с экспертной больше допустимого, в обе
        стороны: легче — выведены из выдачи, тяжелее — в выдаче с пометкой."""
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
        """Ответы на якорные семейства из окна связки — последних `window_attempts`
        остановленных попыток специализации."""
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


class RequestUnitOfWork(UnitOfWork, Protocol):
    """Единица работы одного HTTP-запроса: живёт от начала до конца запроса, блоки сценариев
    идут в ней по очереди. Сейчас — Postgres (`app.repository.unit_of_work`)."""

    def close(self) -> None:
        """Конец запроса: соединение возвращается в пул."""
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


class NeedReader(Protocol):
    """Потребности работодателя — для подборки. Сейчас — Postgres (`app.repository.need`) и
    in-memory (`app.repository.memory.selection`)."""

    def get(self, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
        """Потребность работодателя `user_id`; чужая или несуществующая — `NeedNotFound`: чужая
        для работодателя не существует, чтобы не раскрывать, что такая есть."""
        ...


class NeedRepository(NeedReader, Protocol):
    """Потребности в кабинете работодателя: список, заведение, правка, удаление. Пишет только
    внутри единицы работы и сам не фиксирует. Сейчас — Postgres (`app.repository.need`)."""

    def records(self, user_id: uuid.UUID) -> list[NeedRecord]:
        """Потребности работодателя, новые сверху."""
        ...

    def record(self, user_id: uuid.UUID, need_id: uuid.UUID) -> NeedRecord:
        """Потребность работодателя; чужая или несуществующая — `NeedNotFound`."""
        ...

    def ensure(self, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
        """Потребность есть и принадлежит работодателю, иначе `NeedNotFound`."""
        ...

    def add(self, user_id: uuid.UUID, terms: NeedTerms, now: datetime) -> uuid.UUID:
        """Новая потребность; `now` — время заведения и правки."""
        ...

    def replace(
        self, user_id: uuid.UUID, need_id: uuid.UUID, terms: NeedTerms, now: datetime
    ) -> None:
        """Заменяет потребность целиком, включая правки важности; `now` — время правки."""
        ...

    def delete(self, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
        """Удаляет потребность; подборки по ней остаются со снимком."""
        ...


class CandidatePool(Protocol):
    """Кандидаты подборки: с категорией по тесту и профилем навыков её специализации — и без
    категории, заявившие грейд, для нижнего блока."""

    def in_reach(
        self, specialization: str, grade_rank: int, distance: int, technologies: Collection[str]
    ) -> list[PoolCandidate]:
        """Категория — `specialization`, ранг грейда — не дальше `distance` от `grade_rank`
        (`app.domain.selection.block_of`). Стек кандидата — только из `technologies`, технологий
        потребности. Порядок не важен: его задаёт подборка."""
        ...

    def unconfirmed(
        self, specialization: str, grade: str, technologies: Collection[str]
    ) -> list[UnconfirmedCandidate]:
        """Без категории: последний опрос — `specialization`, заявлен ровно грейд `grade`. Стек —
        только из `technologies`. Порядок не важен."""
        ...

    def facts(self, candidate_ids: Collection[uuid.UUID]) -> list[CandidateFacts]:
        """Что фильтры знают о кандидатах из `candidate_ids` — сейчас, а не на момент подборки.
        Кандидата без статуса грейда в ответе нет; профиль навыков — на момент последнего
        сигнала. Порядок не важен."""
        ...

    def searchable(self) -> list[CandidateFacts]:
        """То же по всей базе: все кандидаты с категорией или заявленным грейдом."""
        ...


class SelectionRepository(Protocol):
    """Сохранённые подборки: снимок потребности и выдача. Формат хранения снимка и объяснения
    не зависит от схем API: сохранённые подборки открываются без миграции данных."""

    def add(self, draft: SelectionDraft, entries: Sequence[SelectionEntry]) -> Selection:
        """Сохраняет подборку с выдачей и даёт ей id."""
        ...

    def get(
        self, user_id: uuid.UUID, selection_id: uuid.UUID
    ) -> tuple[Selection, tuple[SelectionEntry, ...]]:
        """Подборка с фильтрами и шортлистом и вся её выдача по местам; чужая или
        несуществующая — `SelectionNotFound`."""
        ...

    def save_filters(self, selection_id: uuid.UUID, filters: CandidateFilters) -> None:
        """Заменяет фильтры подборки; выдачу не трогает."""
        ...

    def set_shortlisted(
        self, selection_id: uuid.UUID, candidate_id: uuid.UUID, shortlisted: bool
    ) -> None:
        """Отмечает кандидата выдачи или снимает отметку; повтор ничего не меняет. Что кандидат
        в выдаче, проверяет сценарий."""
        ...

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        """Подборки работодателя, новые сверху; `need_id` — только по этой потребности."""
        ...

    def with_candidate(self, candidate_id: uuid.UUID, since: datetime) -> list[CandidateSelection]:
        """Подборки с `created_at` не раньше `since`, в выдаче которых есть кандидат, — по
        времени построения: его место и блок, снимок потребности и сохранённые скоры остальных
        кандидатов того же блока. Для обратной связи кандидату (mechanics.md, §15)."""
        ...


class AccountRepository(Protocol):
    """Учётки. Адрес приходит уже в нижнем регистре. Пишет только внутри единицы работы и сам не
    фиксирует. Сейчас — Postgres (`app.repository.account`)."""

    def get(self, user_id: uuid.UUID) -> Account | None: ...

    def by_email(self, email: str) -> Account | None: ...

    def by_fsp_id(self, fsp_id: str) -> Account | None: ...

    def add_fsp(self, email: str, fsp_id: str, now: datetime) -> Account:
        """Учётка кандидата без пароля по входу через ФСП ID: адрес подтверждён в момент `now`.
        Адрес занят — `EmailTaken`, ФСП ID занят — `FspIdTaken`, в том числе параллельным
        запросом."""
        ...

    def link_fsp(self, user_id: uuid.UUID, fsp_id: str) -> Account:
        """Привязывает ФСП ID; занят другой учёткой, в том числе параллельно, — `FspIdTaken`."""
        ...

    def unlink_fsp(self, user_id: uuid.UUID) -> Account:
        """Освобождает ФСП ID учётки."""
        ...

    def credentials(self, email: str) -> Credentials | None:
        """Учётка с хэшем пароля — для проверки входа."""
        ...

    def add(self, email: str, password_hash: str, role: Role, now: datetime) -> Account:
        """Новая учётка; адрес занят, в том числе параллельным запросом, — `EmailTaken`."""
        ...

    def mark_verified(self, user_id: uuid.UUID, now: datetime) -> Account:
        """Адрес учётки подтверждён в момент `now`."""
        ...


class EmailVerificationRepository(Protocol):
    """Выданные ссылки подтверждения адреса — хэшами токенов. Сейчас — Postgres
    (`app.repository.account`)."""

    def add(self, verification: EmailVerification) -> None: ...

    def by_hash(self, token_hash: str) -> EmailVerification | None: ...

    def revoke(self, user_id: uuid.UUID) -> None:
        """Гасит все ссылки учётки."""
        ...


class PasswordHasher(Protocol):
    """Хэширование паролей — библиотека. Сейчас — argon2 (`app.adapter.password`)."""

    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str | None, password: str) -> bool:
        """Пароль подходит к хэшу; испорченный хэш — `False`. `None` — учётки нет: ответ
        `False`, но проверка идёт столько же, сколько с хэшем, — время входа не выдаёт, кто
        зарегистрирован."""
        ...


class SessionTokens(Protocol):
    """Токен входа: выпуск и проверка. Сейчас — подписанный JWT (`app.adapter.session`); срок
    реализация получает через конструктор."""

    def issue(self, user_id: uuid.UUID, now: datetime) -> str:
        """Токен со сроком от момента `now`."""
        ...

    def read(self, token: str, now: datetime) -> uuid.UUID | None:
        """Учётка по токену; подделанный, испорченный или истёкший к `now` — `None`."""
        ...


class CompanyRepository(Protocol):
    """Профили компаний. Сейчас — Postgres (`app.repository.company`)."""

    def get(self, user_id: uuid.UUID) -> Company | None: ...

    def save(self, user_id: uuid.UUID, form: CompanyForm, now: datetime) -> None:
        """Профиль работодателя — новый или поверх прежнего; сфера уже проверена."""
        ...


class FspIdProvider(Protocol):
    """ФСП ID — внешняя система входа, OpenID Connect: authorization code + PKCE. Сейчас —
    локальный Keycloak, который изображает ФСП ID (`app.adapter.fsp_id`); настоящий ФСП ID — смена
    адреса и ключей в настройках."""

    def authorization_url(self, authorization: FspAuthorization) -> str:
        """Куда отправить браузер за входом; ФСП ID не отвечает — `FspIdUnavailable`."""
        ...

    def identify(self, code: str, authorization: FspAuthorization) -> FspIdentity:
        """Кто вошёл — по коду из callback: обмен кода и проверка ID-токена. ФСП ID не отвечает —
        `FspIdUnavailable`, код или токен не принят — `FspIdRejected`."""
        ...


class FspRegistry(Protocol):
    """Реестр ФСП — достижения по ФСП ID. Сейчас — файл-заглушка на синтетике
    (`app.adapter.fsp_registry`); настоящий реестр — новый адаптер за этим портом."""

    def achievements(self, fsp_id: str) -> list[FspAchievement]:
        """Достижения участника; неизвестный ID — пусто. Реестр не отвечает —
        `FspRegistryUnavailable`."""
        ...


class FspEvidenceReader(Protocol):
    """Снимок достижений ФСП и справочник дисциплин — то, из чего профиль навыков строит
    наблюдения ФСП. Сейчас — Postgres (`app.repository.fsp`) и in-memory
    (`app.repository.memory.fsp`)."""

    def snapshot(self, user_id: uuid.UUID) -> FspSnapshot | None:
        """Последний снимок; `None` — реестр ни разу не ответил или ID не привязан."""
        ...

    def disciplines(self) -> dict[str, FspDiscipline]:
        """Дисциплины ФСП по коду."""
        ...


class FspRepository(FspEvidenceReader, Protocol):
    """Снимки достижений ФСП на запись. Пишет только внутри единицы работы и сам не фиксирует.
    Сейчас — Postgres (`app.repository.fsp`)."""

    def history(self, user_id: uuid.UUID) -> FspHistory | None:
        """Снимок для показа — с названиями дисциплин и ролей; ID привязан, а снимка нет —
        пустая история без даты; `None` — ФСП ID не привязан."""
        ...

    def save_snapshot(
        self, user_id: uuid.UUID, achievements: Sequence[FspAchievement], now: datetime
    ) -> None:
        """Заменяет снимок целиком; `now` — момент получения."""
        ...

    def delete_snapshot(self, user_id: uuid.UUID) -> None: ...


class InvitationReader(Protocol):
    """Чтение приглашений для правила раскрытия. Сейчас — Postgres (`app.repository.invitation`)."""

    def accepted(self, employer_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
        """Есть ли у компании принятое и не отозванное приглашение этому кандидату."""
        ...


class InvitationRepository(InvitationReader, Protocol):
    """Приглашения с записанным статусом: «истекло» не хранится, его выводит домен по моменту
    чтения (`Invitation.at`). Списки — новые сверху. Пишет только внутри единицы работы и сам не
    фиксирует. Сейчас — Postgres (`app.repository.invitation`)."""

    def lock_company(self, employer_id: uuid.UUID) -> None:
        """Отправки одной компании идут по очереди: двойной клик не создаст два приглашения и не
        пройдёт мимо бюджета."""
        ...

    def add(
        self,
        employer_id: uuid.UUID,
        candidate_id: uuid.UUID,
        company_name: str,
        terms: InvitationTerms,
        now: datetime,
    ) -> Invitation:
        """Новое отправленное приглашение; `now` — время отправки."""
        ...

    def get(self, invitation_id: uuid.UUID, *, for_update: bool = False) -> Invitation | None:
        """Приглашение по id; `for_update` — с блокировкой до конца единицы работы."""
        ...

    def save(self, invitation: Invitation) -> None:
        """Записывает статус, время просмотра, ответа и отзыва; истёкшее не записывается."""
        ...

    def by_candidate(self, candidate_id: uuid.UUID) -> list[Invitation]: ...

    def by_employer(self, employer_id: uuid.UUID) -> list[Invitation]: ...

    def latest(self, employer_id: uuid.UUID, candidate_id: uuid.UUID) -> Invitation | None:
        """Последнее приглашение компании кандидату: открытым может быть только оно."""
        ...

    def sent_since(self, employer_id: uuid.UUID, since: datetime) -> int:
        """Сколько приглашений компания отправила с момента `since`, в любом статусе."""
        ...


class MessageRepository(Protocol):
    """Сообщения переписки в приглашениях. Пишет только внутри единицы работы и сам не фиксирует.
    Сейчас — Postgres (`app.repository.conversation`)."""

    def add(self, invitation_id: uuid.UUID, author: Side, text: str, now: datetime) -> Message:
        """Новое непрочитанное сообщение; `now` — время отправки."""
        ...

    def by_invitation(self, invitation_id: uuid.UUID) -> list[Message]:
        """Переписка приглашения в порядке записи — старые сверху."""
        ...

    def mark_read(self, invitation_id: uuid.UUID, reader: Side, now: datetime) -> None:
        """Сообщения другой стороны в приглашении, ещё не прочитанные, — прочитаны в `now`."""
        ...

    def unread(self, reader: Side, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Непрочитанные сообщения другой стороны по приглашениям, где пользователь `user_id` —
        сторона `reader`; приглашения без непрочитанного не попадают."""
        ...


class CatalogRepository(Protocol):
    """Справочники в хранилище: чтение для форм и проверок и синхронизация. Сейчас — Postgres
    (`app.repository.catalog`)."""

    def grades(self) -> list[Grade]:
        """От младшего к старшему."""
        ...

    def grade(self, code: str) -> Grade | None: ...

    def industries(self) -> list[Industry]:
        """В порядке справочника."""
        ...

    def industry(self, code: str) -> Industry | None: ...

    def specializations(self) -> list[Specialization]:
        """В порядке справочника, темы — тоже."""
        ...

    def specialization(self, code: str) -> Specialization | None: ...

    def technologies(self, codes: Collection[str] | None = None) -> list[Technology]:
        """По названию; `codes` — только эти, неизвестные пропускаются. Темы технологии — по
        коду."""
        ...

    def codes(self) -> dict[CatalogPart, set[str]]:
        """Коды, которые сейчас в хранилище."""
        ...

    def apply(self, plan: CatalogPlan) -> None:
        """Применяет синхронизацию; снять код, на который ссылаются данные, хранилище откажет."""
        ...


class TextUnderstanding(Protocol):
    """Понимание свободного текста (docs/adr/0002-text-understanding-port.md): текст → черновик со
    значениями справочника. Сейчас — правила и словарь синонимов (`app.adapter.text_rules`).

    Порт ничего не оценивает и наружу не ходит: модель — локальные веса или сервис в compose.
    Вывод сценарий проверяет сам (`app.domain.need_draft.checked`), поэтому адаптер может
    ошибиться, но не вывести значение за справочник. Разбор резюме станет второй операцией.
    """

    def need(self, text: str, catalog: Catalog) -> NeedDraft | OutOfCatalog:
        """Потребность, которую работодатель написал как есть, — очищенный текст. `catalog` —
        справочник, в пределах которого отвечать."""
        ...


class CatalogSource(Protocol):
    """Откуда берутся справочники. Сейчас — файл `config/catalog.yaml`
    (`app.adapter.catalog_file`)."""

    def load(self) -> Catalog: ...
