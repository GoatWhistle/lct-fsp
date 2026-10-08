"""Путь кандидата к категории: опрос, попытка теста, предъявления, шаг пути, смена грейда, блок
по теме и проверочный блок (mechanics.md, §4–§6, §8, §11).

Состояние пути выводится из записей: последний опрос, последняя попытка пути, категория. Блок по
теме и проверочный блок — тоже попытки, но не шаги пути: стадию, историю и смену грейда они не
трогают, проверочный блок только подтверждает отложенный результат попытки пути. Состояние
попытки — список предъявлений, оценка — чистая функция от него, поэтому прерванный тест
продолжается с того же места после перезапуска бэкенда. Правила здесь — инварианты механики;
хранит записи репозиторий попытки, решения принимает сценарий `app.usecase.attempt`.
"""

import enum
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.domain import bank
from app.domain.candidate import Category, Level, SkillProfile
from app.domain.catalog import CatalogRef, Topic
from app.domain.determination import grade_probabilities, grade_up_hint, grades_by_threshold
from app.domain.skill import Normal, Observation, SignalSource


@dataclass(frozen=True)
class AnsweredPresentation:
    """Отвеченное предъявление: семейство, тема, параметры экземпляра, верность ответа.

    Разделяющая сила и сложность — семейства на момент показа: калибровка их потом сдвигает, а
    оценка по ответу должна пересчитываться в то же значение.
    """

    family_code: str
    topic: str
    params: Mapping[str, Any]
    discrimination: float
    difficulty: float
    correct: bool
    answered_at: datetime
    # Уровень доверия: тест и блок по теме — `test`, проверочный блок — `verification`.
    source: SignalSource = SignalSource.test

    def observation(self, weight: float = 1.0) -> Observation:
        """Наблюдение модели навыка; `weight` — вес уровня доверия сигнала."""
        return Observation(
            topic=self.topic,
            correct=self.correct,
            discrimination=self.discrimination,
            difficulty=self.difficulty,
            weight=weight,
            at=self.answered_at,
            source=self.source,
        )


class Stage(enum.StrEnum):
    survey = "survey"
    grade = "grade"
    test = "test"
    offer = "offer"
    category = "category"
    no_category = "no_category"
    # Результат определения подозрительный и ждёт проверочного блока (§8): категории пока нет.
    verification = "verification"


class AttemptPurpose(enum.StrEnum):
    """Зачем попытка (mechanics.md, §4)."""

    # Первичное определение категории, вместе с дотестами каскада.
    determination = "determination"
    # Попытка на грейд выше — отдельное измерение с чистого листа.
    grade_up = "grade_up"
    # Блок по одной теме категории: уточняет профиль навыков, категорию и грейд не меняет.
    topic_block = "topic_block"
    # Проверочный блок на время (§8): подтверждает подозрительный результат попытки пути или,
    # добровольно, уровень категории.
    verification = "verification"


class AttemptOutcome(enum.StrEnum):
    """Чем закончилась попытка (mechanics.md, §4)."""

    # Категория присвоена: грейд попытки или ниже, если для него уверенность уже набрана.
    assigned = "assigned"
    # Уверенности не хватило — предложен дотест на грейд ниже.
    offered = "offered"
    # Не хватило и для стажёра: кандидат без категории до даты повтора.
    no_category = "no_category"
    # Попытка вверх: уверенности не хватило, категория прежняя.
    not_passed = "not_passed"
    # Результат повышает категорию или присваивает её впервые, но подозрительный (§8): категория
    # ждёт проверочного блока, наблюдения попытки — вне оценки и профиля. Провалом не считается.
    verification = "verification"
    # Итоги проверочного блока: совпал с основным тестом или разошёлся с ним.
    confirmed = "confirmed"
    mismatch = "mismatch"


class ChangeKind(enum.StrEnum):
    """Запись журнала категории. Часы ожидания сдвигают только `up` и `down`."""

    # Первичное определение, включая каскад, — сменой не считается.
    determined = "determined"
    up = "up"
    down = "down"


@dataclass(frozen=True)
class CategoryChange:
    """Запись журнала категории: грейд после записи и когда."""

    grade_code: str
    kind: ChangeKind
    at: datetime


@dataclass(frozen=True)
class Survey:
    """Опрос — первый шаг пути: направление, то есть специализация («отрасль» в ТЗ). Последний
    опрос кандидата — текущий."""

    id: uuid.UUID
    specialization: CatalogRef
    created_at: datetime

    @property
    def specialization_code(self) -> str:
        return self.specialization.code


@dataclass
class Presentation:
    """Предъявление экземпляра семейства: всё, на чём стоят калибровка, защита и валидация.

    Параметры семейства (a, b) записаны на момент показа. Эталон не хранится — он вычисляется
    из семейства и seed.
    """

    id: uuid.UUID
    attempt_id: uuid.UUID
    position: int
    family_code: str
    topic_code: str
    seed: int
    params: Mapping[str, Any]
    discrimination: float
    difficulty: float
    # Оценка теста по теме до ответа (μ_t, σ_t).
    topic_theta_before: float
    topic_theta_sd_before: float
    # Время — по часам сервера: клиентские подделываются.
    shown_at: datetime
    answered_at: datetime | None = None
    response: str | None = None
    correct: bool | None = None
    response_time_ms: int | None = None
    # Итоговая оценка теста по теме без этого ответа — пишется при остановке попытки. По ней
    # переоценивают параметры семейства: ответ не сравнивается с оценкой, в которую вошёл сам.
    topic_theta_rest: float | None = None
    topic_theta_rest_sd: float | None = None
    # События за время задания — только с согласия кандидата, только счётчики (§8); без
    # согласия — None.
    paste_events: int | None = None
    focus_losses: int | None = None
    # Флаг времени (§8) — пишется при остановке попытки; None — не проверялось.
    time_flag: bool | None = None
    # Семейство скомпрометировано, пока попытка шла: ответ выпал из оценки и профиля (§8).
    dropped: bool = False

    @property
    def focus_events(self) -> int | None:
        if self.paste_events is None and self.focus_losses is None:
            return None
        return (self.paste_events or 0) + (self.focus_losses or 0)

    def answered(self, source: SignalSource = SignalSource.test) -> AnsweredPresentation:
        if self.correct is None or self.answered_at is None:
            raise ValueError("наблюдение — только отвеченное предъявление")
        return AnsweredPresentation(
            family_code=self.family_code,
            topic=self.topic_code,
            params=dict(self.params),
            discrimination=self.discrimination,
            difficulty=self.difficulty,
            correct=self.correct,
            answered_at=self.answered_at,
            source=source,
        )


@dataclass
class Attempt:
    """Попытка — прохождение теста на один грейд. Дотест каскада продолжает оценку попытки,
    на которую ссылается `continues_attempt_id`: вместе они — одно определение категории."""

    id: uuid.UUID
    user_id: uuid.UUID
    number: int
    survey_id: uuid.UUID
    specialization_code: str
    grade_code: str
    continues_attempt_id: uuid.UUID | None
    started_at: datetime
    purpose: AttemptPurpose = AttemptPurpose.determination
    # Тема блока — только у `topic_block`.
    topic_code: str | None = None
    finished_at: datetime | None = None
    # Оценка теста на момент остановки: общий уровень θ̄ и его погрешность.
    overall: Normal | None = None
    outcome: AttemptOutcome | None = None
    # Присвоенный или предложенный для дотеста грейд — по `outcome`.
    outcome_grade_code: str | None = None
    retest_after: datetime | None = None
    presentations: list[Presentation] = field(default_factory=list)
    # Кандидат согласился на счётчики вставки и потери фокуса (§8).
    focus_consent: bool = False
    # Наблюдения попытки не входят ни в оценку, ни в профиль: результат ждёт проверочного блока
    # или разошёлся с ним (§8). У определения — у всех звеньев цепочки.
    withheld: bool = False
    # Проверочный блок: какую попытку пути он проверяет; None — добровольный блок по категории.
    verifies_attempt_id: uuid.UUID | None = None
    # Срок проверочного блока по часам сервера: неотвеченное к нему — неверно.
    deadline: datetime | None = None
    # Итог проверочного блока: ожидаемое по основной оценке число верных, верных, заданий.
    expected_correct: float | None = None
    correct_count: int | None = None
    planned_items: int | None = None

    def pending(self) -> Presentation | None:
        """Показанное, но не отвеченное задание — всегда последнее."""
        last = self.presentations[-1] if self.presentations else None
        return last if last is not None and last.answered_at is None else None

    def counts(self) -> dict[str, int]:
        """Заданий по темам в этой попытке: минимумы покрытия и потолок доли — у каждой свои."""
        counts: dict[str, int] = {}
        for p in self.presentations:
            counts[p.topic_code] = counts.get(p.topic_code, 0) + 1
        return counts

    def shown(self) -> set[str]:
        return {p.family_code for p in self.presentations}

    @property
    def on_path(self) -> bool:
        """Попытка — шаг пути к категории: определение или попытка вверх, но не блок по теме и
        не проверочный блок."""
        return self.purpose not in (AttemptPurpose.topic_block, AttemptPurpose.verification)

    @property
    def source(self) -> SignalSource:
        """Уровень доверия наблюдений попытки (§11)."""
        if self.purpose == AttemptPurpose.verification:
            return SignalSource.verification
        return SignalSource.test

    @property
    def pending_verification(self) -> bool:
        """Результат попытки пути ждёт проверочного блока."""
        return self.outcome == AttemptOutcome.verification


@dataclass(frozen=True)
class PathState:
    """Записи пути кандидата: последний опрос, последняя попытка пути, категория. Блок по теме
    состоянием пути не бывает."""

    survey: Survey | None
    attempt: Attempt | None
    category: Category | None


def stage_of(state: PathState, now: datetime) -> Stage:
    """Шаг пути из записей. Повтор после провала каскада открывается только с `retest_after`:
    до этой даты путь стоит на `no_category`. Попытка вверх идёт при категории — шаг `test`;
    её отложенный до проверочного блока результат шаг `category` не меняет."""
    attempt = state.attempt
    if attempt is not None and attempt.finished_at is None:
        return Stage.test
    if state.category is not None:
        return Stage.category
    if attempt is not None and attempt.pending_verification:
        return Stage.verification
    if attempt is not None and attempt.outcome == AttemptOutcome.offered:
        return Stage.offer
    if (
        attempt is not None
        and attempt.outcome == AttemptOutcome.no_category
        and attempt.retest_after is not None
        and now < attempt.retest_after
    ):
        return Stage.no_category
    if state.survey is None:
        return Stage.survey
    return Stage.grade


@dataclass(frozen=True)
class AttemptProgress:
    grade: str
    answered: int


@dataclass(frozen=True)
class TopicBlockProgress:
    """Идущий блок по теме: длина фиксированная — `items` заданий."""

    topic: CatalogRef
    answered: int
    items: int


@dataclass(frozen=True)
class VerificationProgress:
    """Идущий проверочный блок: срок — по часам сервера."""

    answered: int
    items: int
    deadline: datetime


@dataclass(frozen=True)
class VerificationResult:
    """Итог последнего проверочного блока — кандидату причиной числами: «ожидалось около 7
    верных из 10, получено 2»."""

    confirmed: bool
    expected: float
    correct: int
    items: int
    at: datetime


@dataclass(frozen=True)
class VerificationView:
    """Проверочный блок в кабинете (§8). `grade` — грейд результата, который ждёт блока; None —
    добровольный блок по категории. `available_at` None — блок можно начать сейчас."""

    grade: str | None
    available_at: datetime | None
    progress: VerificationProgress | None = None
    last: VerificationResult | None = None


@dataclass(frozen=True)
class TestResult:
    """Оценка теста определения категории — по ней решается грейд."""

    grade: str
    overall: Level
    # P(θ̄ ≥ порог) по грейдам — от младшего к старшему.
    grade_probabilities: Mapping[str, float]
    grade_up_hint: str | None


class HistoryEvent(enum.StrEnum):
    attempt = "attempt"
    step_down = "step_down"


@dataclass(frozen=True)
class HistoryEntry:
    """Строка истории в кабинете: остановленная попытка или переход вниз.

    У попытки `grade` — грейд попытки, у перехода — грейд после него. Уровень, назначение и итог —
    только у попытки.
    """

    at: datetime
    event: HistoryEvent
    grade: str
    purpose: AttemptPurpose | None = None
    overall: Level | None = None
    outcome: AttemptOutcome | None = None
    outcome_grade: str | None = None


@dataclass(frozen=True)
class GradeUp:
    """Попытка вверх: на какой грейд и с какого момента; `available_at` None — доступна сейчас."""

    grade: str
    available_at: datetime | None


@dataclass(frozen=True)
class PathView:
    """Шаг пути и всё, что показывает кабинет кандидата: правил у контроллера не остаётся.

    Смена грейда и история — только на шаге `category`.
    """

    stage: Stage
    survey: Survey | None
    progress: AttemptProgress | None
    offer_grade: str | None
    retest_after: datetime | None
    category: Category | None
    result: TestResult | None
    profile: SkillProfile | None
    grade_up: GradeUp | None = None
    grade_down: str | None = None
    history: tuple[HistoryEntry, ...] = ()
    # Незавершённый блок по теме: пока он идёт, кабинет показывает его задания.
    topic_block: TopicBlockProgress | None = None
    # Проверочный блок: результат ждёт его, он идёт или его можно пройти добровольно.
    verification: VerificationView | None = None


@dataclass(frozen=True)
class Answer:
    """Зафиксированный ответ на задание — вход калибровки (mechanics.md, §7): она идёт по нему
    после фиксации ответа, без повторного чтения попытки."""

    specialization_code: str
    family_code: str
    # Оценка теста по теме до ответа (μ_t, σ_t) — с ней шаг Эло сравнивает ответ.
    level_before: Normal
    correct: bool
    answered_at: datetime
    # Ответ остановил попытку: после шага Эло — связка шкалы и переоценка семейств попытки.
    stopped: bool
    # Семейства, показанные в попытке, — в порядке показа.
    families: tuple[str, ...]


@dataclass(frozen=True)
class Answered:
    """Итог сценария ответа: шаг пути — кандидату, ответ — сценарию калибровки. Ответа нет,
    если срок проверочного блока прошёл до него: ответ не засчитан."""

    view: PathView
    answer: Answer | None


@dataclass(frozen=True)
class Item:
    """Текущее задание попытки — экземпляр семейства; эталон из него на фронт не уходит."""

    presentation_id: uuid.UUID
    number: int
    topic: Topic
    family_code: str
    instance: bank.Instance
    # Заданий не больше — у теста; ровно столько — у блока по теме и проверочного блока.
    max_items: int
    topic_block: bool = False
    verification: bool = False
    # Срок проверочного блока.
    deadline: datetime | None = None


def test_result(
    attempt: Attempt,
    *,
    thresholds: Mapping[str, float],
    grade_confidence: float,
    hint_confidence: float,
) -> TestResult:
    """Итог остановленной попытки. Подсказка «грейд выше» — только тому, кто сразу прошёл
    заявленный грейд: после каскада грейд выше уже не дался."""
    assert attempt.overall is not None
    passed_claimed = (
        attempt.outcome == AttemptOutcome.assigned
        and attempt.continues_attempt_id is None
        and attempt.outcome_grade_code == attempt.grade_code
    )
    hint = None
    if passed_claimed:
        hint = grade_up_hint(
            attempt.overall,
            attempt.grade_code,
            thresholds=thresholds,
            confidence=hint_confidence,
        )
    return TestResult(
        grade=attempt.grade_code,
        overall=Level.of(attempt.overall, thresholds, grade_confidence),
        grade_probabilities=grade_probabilities(attempt.overall, thresholds),
        grade_up_hint=hint,
    )


def failed_grade(attempt: Attempt) -> str | None:
    """Грейд, который в остановленной попытке не дался: провал попытки вверх, дотест каскада или
    грейд, с которого каскад увёл ниже."""
    if attempt.finished_at is None or attempt.outcome is None:
        return None
    if attempt.outcome == AttemptOutcome.verification:
        # Отложенный до проверочного блока результат — не провал: попытку он не сжигает (§4, §8).
        return None
    if attempt.outcome == AttemptOutcome.assigned:
        return None if attempt.outcome_grade_code == attempt.grade_code else attempt.grade_code
    return attempt.grade_code


def grade_up_available_at(
    target: str,
    attempts: Sequence[Attempt],
    changes: Sequence[CategoryChange],
    *,
    thresholds: Mapping[str, float],
    change_interval: timedelta,
    retry_interval: timedelta,
) -> datetime | None:
    """Правило ожидания (§4): с какого момента можно начать попытку на `target`; None — ничто
    не держит.

    Часы сдвигает только смена категории — вверх или вниз, первичное определение не считается.
    Проваленный грейд держит короткий интервал для себя и грейдов выше, грейд ниже — не держит.
    """
    order = grades_by_threshold(thresholds)
    moments = [c.at + change_interval for c in changes if c.kind != ChangeKind.determined]
    for attempt in attempts:
        failed = failed_grade(attempt)
        if failed is not None and order.index(target) >= order.index(failed):
            assert attempt.finished_at is not None
            moments.append(attempt.finished_at + retry_interval)
    return max(moments, default=None)


def path_history(
    attempts: Sequence[Attempt],
    changes: Sequence[CategoryChange],
    *,
    thresholds: Mapping[str, float],
    confidence: float,
) -> tuple[HistoryEntry, ...]:
    """История пути по времени: остановленные попытки и переходы вниз. Присвоение и повышение
    видны по своим попыткам — отдельной строкой не повторяются."""
    entries = [
        HistoryEntry(
            at=a.finished_at,
            event=HistoryEvent.attempt,
            grade=a.grade_code,
            purpose=a.purpose,
            overall=Level.of(a.overall, thresholds, confidence),
            outcome=a.outcome,
            outcome_grade=a.outcome_grade_code,
        )
        for a in sorted(attempts, key=lambda a: a.number)
        if a.finished_at is not None and a.overall is not None
    ]
    entries += [
        HistoryEntry(at=c.at, event=HistoryEvent.step_down, grade=c.grade_code)
        for c in changes
        if c.kind == ChangeKind.down
    ]
    # Сортировка устойчивая: при равном времени попытки идут по номеру.
    return tuple(sorted(entries, key=lambda e: e.at))


def topic_block_starts(attempts: Sequence[Attempt]) -> dict[str, datetime]:
    """Старт последнего блока по каждой теме — и брошенного тоже: иначе блок можно бросать до
    удобных заданий."""
    starts: dict[str, datetime] = {}
    for a in attempts:
        if a.purpose != AttemptPurpose.topic_block or a.topic_code is None:
            continue
        if a.topic_code not in starts or a.started_at > starts[a.topic_code]:
            starts[a.topic_code] = a.started_at
    return starts


def topic_blocks_held(
    attempts: Sequence[Attempt], topics: Iterable[str], now: datetime, interval: timedelta
) -> dict[str, datetime]:
    """Темы из `topics`, блок по которым ещё держит интервал, — с датой, когда можно. Одно
    правило для запуска блока и для подсказок обратной связи."""
    starts = topic_block_starts(attempts)
    return {
        topic: at
        for topic in topics
        if (at := topic_block_available_at(starts, topic, now, interval)) is not None
    }


def topic_block_available_at(
    starts: Mapping[str, datetime], topic: str, now: datetime, interval: timedelta
) -> datetime | None:
    """Интервал блока по теме (§6): с какого момента можно начать блок по `topic`; None — можно
    сейчас. Считается от старта последнего блока по этой теме, другие темы его не держат."""
    start = starts.get(topic)
    if start is None or start + interval <= now:
        return None
    return start + interval
