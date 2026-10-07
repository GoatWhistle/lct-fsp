"""Путь кандидата к категории: опрос, попытка теста, предъявления и шаг пути
(mechanics.md, §4–§6, §11).

Состояние пути выводится из записей: последний опрос, последняя попытка, категория. Состояние
попытки — список предъявлений, оценка — чистая функция от него, поэтому прерванный тест
продолжается с того же места после перезапуска бэкенда. Правила здесь — инварианты механики;
хранит записи репозиторий попытки, решения принимает сценарий `app.usecase.attempt`.
"""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain import bank
from app.domain.candidate import Category, Level, SkillProfile
from app.domain.catalog import CatalogRef, Topic
from app.domain.determination import grade_probabilities, grade_up_hint
from app.domain.skill import Normal, Observation


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

    def observation(self, weight: float = 1.0) -> Observation:
        """Наблюдение модели навыка; `weight` — вес уровня доверия сигнала."""
        return Observation(
            topic=self.topic,
            correct=self.correct,
            discrimination=self.discrimination,
            difficulty=self.difficulty,
            weight=weight,
        )


class Stage(enum.StrEnum):
    survey = "survey"
    grade = "grade"
    test = "test"
    offer = "offer"
    category = "category"
    no_category = "no_category"


class AttemptOutcome(enum.StrEnum):
    """Чем закончилась попытка первичного определения категории (mechanics.md, §4)."""

    # Категория присвоена: грейд попытки или ниже, если для него уверенность уже набрана.
    assigned = "assigned"
    # Уверенности не хватило — предложен дотест на грейд ниже.
    offered = "offered"
    # Не хватило и для стажёра: кандидат без категории до даты повтора.
    no_category = "no_category"


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

    def answered(self) -> AnsweredPresentation:
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
    finished_at: datetime | None = None
    # Оценка теста на момент остановки: общий уровень θ̄ и его погрешность.
    overall: Normal | None = None
    outcome: AttemptOutcome | None = None
    # Присвоенный или предложенный для дотеста грейд — по `outcome`.
    outcome_grade_code: str | None = None
    retest_after: datetime | None = None
    presentations: list[Presentation] = field(default_factory=list)

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


@dataclass(frozen=True)
class PathState:
    """Записи пути кандидата: последний опрос, последняя попытка, категория."""

    survey: Survey | None
    attempt: Attempt | None
    category: Category | None


def stage_of(state: PathState, now: datetime) -> Stage:
    """Шаг пути из записей. Повтор после провала каскада открывается только с `retest_after` —
    правило смены грейда (§4): до этой даты путь стоит на `no_category`."""
    attempt = state.attempt
    if state.category is not None:
        return Stage.category
    if attempt is not None and attempt.finished_at is None:
        return Stage.test
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
class TestResult:
    """Оценка теста определения категории — по ней решается грейд."""

    grade: str
    overall: Level
    # P(θ̄ ≥ порог) по грейдам — от младшего к старшему.
    grade_probabilities: Mapping[str, float]
    grade_up_hint: str | None


@dataclass(frozen=True)
class PathView:
    """Шаг пути и всё, что показывает кабинет кандидата: правил у контроллера не остаётся."""

    stage: Stage
    survey: Survey | None
    progress: AttemptProgress | None
    offer_grade: str | None
    retest_after: datetime | None
    category: Category | None
    result: TestResult | None
    profile: SkillProfile | None


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
    """Итог сценария ответа: шаг пути — кандидату, ответ — сценарию калибровки."""

    view: PathView
    answer: Answer


@dataclass(frozen=True)
class Item:
    """Текущее задание попытки — экземпляр семейства; эталон из него на фронт не уходит."""

    presentation_id: uuid.UUID
    number: int
    topic: Topic
    family_code: str
    instance: bank.Instance


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
