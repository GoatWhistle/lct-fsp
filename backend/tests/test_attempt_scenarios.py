"""Сценарии пути кандидата на in-memory репозиториях — без Postgres (mechanics.md, §4, §6).

Та же сборка, что в `backend/main.py`, только хранилище в памяти: остановка по точности,
каскад вниз и подсказка «грейд выше» проверяются на сценариях напрямую, без HTTP.
"""

import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter.adaptive import MaxInformationSelector
from app.adapter.calibration import EloCalibration
from app.adapter.clock import FrozenClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.seed import DerivedSeeds
from app.assessment.catalog import load_catalog
from app.config import Mechanics, Settings
from app.domain import bank
from app.domain.attempt import PathView, Stage
from app.domain.bank import Family, get_family
from app.domain.calibration import Parameters
from app.domain.catalog import Grade, Specialization, Topic
from app.domain.errors import StepUnavailable
from app.domain.skill import Normal
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.skills import irt
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = load_catalog()
GRADES = {g.code: Grade(g.code, g.name, g.rank) for g in CATALOG.grades}
SPECIALIZATIONS = {
    s.code: Specialization(s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics))
    for s in CATALOG.specializations
}
WRONG = "ответа нет"
AnswerItems = Callable[[uuid.UUID, Callable[[Family], bool]], PathView]


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(T0)


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def attempts(store: MemoryStore) -> MemoryAttemptRepository:
    return MemoryAttemptRepository(
        store,
        SPECIALIZATIONS,
        GRADES,
        MECHANICS.grade_thresholds,
        MECHANICS.grade_confidence,
    )


class SpyCalibration:
    """Порт калибровки, который записывает вызовы и передаёт их настоящей реализации."""

    def __init__(self, inner: EloCalibration) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def current(self, families: Sequence[bank.Family]) -> dict[str, Parameters]:
        self.calls.append("current")
        return self.inner.current(families)

    def lock(self, codes: Iterable[str]) -> None:
        self.calls.append("lock")
        self.inner.lock(codes)

    def learn(
        self, specialization: str, family_code: str, level_before: Normal, correct: bool
    ) -> None:
        self.calls.append("learn")
        self.inner.learn(specialization, family_code, level_before, correct)

    def relink(self, specialization: str, now: datetime) -> None:
        self.calls.append("relink")
        self.inner.relink(specialization, now)

    def refit_due(self, codes: Iterable[str], specialization: str, now: datetime) -> None:
        self.calls.append("refit_due")
        self.inner.refit_due(codes, specialization, now)


@pytest.fixture
def calibration(store: MemoryStore) -> SpyCalibration:
    return SpyCalibration(
        EloCalibration(
            MemoryCalibrationRepository(store),
            expert_discrimination=MECHANICS.expert_discrimination,
            expert_difficulty_by_grade=MECHANICS.expert_difficulty_by_grade,
            elo_k_initial=MECHANICS.elo_k_initial,
            elo_k_half_responses=MECHANICS.elo_k_half_responses,
            elo_k_min=MECHANICS.elo_k_min,
            calibration_refit_min_responses=MECHANICS.calibration_refit_min_responses,
            calibration_expert_gap_review=MECHANICS.calibration_expert_gap_review,
            calibration_refit_difficulty_prior_sd=MECHANICS.calibration_refit_difficulty_prior_sd,
            calibration_refit_log_discrimination_prior_sd=(
                MECHANICS.calibration_refit_log_discrimination_prior_sd
            ),
            calibration_link_window_attempts=MECHANICS.calibration_link_window_attempts,
        )
    )


@pytest.fixture
def paths(
    store: MemoryStore,
    attempts: MemoryAttemptRepository,
    calibration: SpyCalibration,
    clock: FrozenClock,
) -> CandidatePath:
    return CandidatePath(
        MemoryUnitOfWork(store),
        attempts,
        calibration,
        MaxInformationSelector(
            top_k=MECHANICS.exposure_top_k, max_rate=MECHANICS.exposure_max_rate
        ),
        irt,
        clock,
        DerivedSeeds(0),
        InProcessCodeRunner(),
        MECHANICS,
    )


@pytest.fixture
def calibrations(store: MemoryStore, calibration: SpyCalibration) -> AnswerCalibration:
    return AnswerCalibration(MemoryUnitOfWork(store), calibration)


@pytest.fixture
def answer_items(paths: CandidatePath, calibrations: AnswerCalibration) -> AnswerItems:
    """Отвечает на задания до остановки попытки, как контроллер: после ответа — калибровка.
    `correct` решает, отвечать ли верно."""

    def answer(user: uuid.UUID, correct: Callable[[Family], bool]) -> PathView:
        view = paths.path(user)
        while view.stage == Stage.test:
            item = paths.current_item(user)
            family = get_family(item.family_code)
            response = item.instance.answer if correct(family) else WRONG
            answered = paths.answer(user, presentation_id=item.presentation_id, response=response)
            calibrations.calibrate(answered.answer)
            view = answered.view
        return view

    return answer


def test_attempt_stops_by_precision_before_item_limit(
    paths: CandidatePath, attempts: MemoryAttemptRepository, answer_items: AnswerItems
) -> None:
    """Остановка по точности: уровень определён с погрешностью не выше `test_stop_sd` — тест
    закончился раньше лимита заданий, категория присвоена."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    started = paths.start_attempt(user, grade="middle")
    assert started.stage == Stage.test

    # Кандидат уровня middle: решает всё до middle включительно — в банке хватает заданий
    # его уровня, и погрешность набирается до лимита.
    view = answer_items(user, lambda family: family.grade != "senior")

    assert view.stage == Stage.category
    assert view.category is not None and view.category.grade.code == "middle"
    assert view.result is not None
    assert view.result.overall.theta_sd <= MECHANICS.test_stop_sd
    answered = attempts.answered(user, "qa")
    assert MECHANICS.test_min_items <= len(answered) < MECHANICS.test_max_items


def test_cascade_down_to_no_category(
    paths: CandidatePath, clock: FrozenClock, answer_items: AnswerItems
) -> None:
    """Каскад вниз (§4): провал на middle предлагает дотест на junior, затем intern; провал
    стажёра оставляет без категории до даты повтора, шаги пути закрыты."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")

    offer = answer_items(user, lambda family: False)
    assert offer.stage == Stage.offer
    assert offer.offer_grade == "junior"
    assert offer.category is None

    paths.start_attempt(user, grade="junior")
    offer = answer_items(user, lambda family: False)
    assert offer.stage == Stage.offer and offer.offer_grade == "intern"

    paths.start_attempt(user, grade="intern")
    view = answer_items(user, lambda family: False)

    assert view.stage == Stage.no_category
    assert view.category is None
    assert view.retest_after == clock.now() + timedelta(days=MECHANICS.no_category_retest_days)
    with pytest.raises(StepUnavailable):
        paths.submit_survey(user, specialization="qa")
    clock.shift(timedelta(days=MECHANICS.no_category_retest_days, minutes=1))
    assert paths.path(user).stage == Stage.grade


def test_skipped_dotest_when_lower_grade_already_confident(
    paths: CandidatePath, answer_items: AnswerItems
) -> None:
    """Каскад без дотеста: уровень у порога middle, junior уже уверенно — присваивается сразу."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")

    view = answer_items(user, lambda family: family.grade in ("intern", "junior"))

    assert view.stage == Stage.category
    assert view.category is not None and view.category.grade.code == "junior"
    assert view.result is not None and view.result.grade == "middle"
    assert view.result.grade_up_hint is None


def test_grade_up_hint_after_confident_pass(
    paths: CandidatePath, answer_items: AnswerItems
) -> None:
    """Подсказка «грейд выше»: все ответы верны — P(уровень ≥ порог senior) выше порога
    подсказки, и она показывается только прошедшему заявленный грейд сразу."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")

    view = answer_items(user, lambda family: True)

    assert view.stage == Stage.category
    assert view.result is not None
    assert view.result.grade_up_hint == "senior"
    probabilities = view.result.grade_probabilities
    assert list(probabilities) == ["intern", "junior", "middle", "senior"]
    assert probabilities["senior"] >= MECHANICS.grade_up_hint_confidence


def test_answer_does_not_calibrate(paths: CandidatePath, calibration: SpyCalibration) -> None:
    """Сценарий ответа фиксирует ответ и остановку, калибровку не трогает: от порта он берёт
    только текущие параметры семейств (§7)."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")

    view = paths.path(user)
    while view.stage == Stage.test:
        item = paths.current_item(user)
        view = paths.answer(user, presentation_id=item.presentation_id, response=WRONG).view

    assert view.stage == Stage.offer
    assert set(calibration.calls) == {"current"}


def test_calibration_steps_after_each_answer_and_relinks_after_stop(
    paths: CandidatePath, calibrations: AnswerCalibration, calibration: SpyCalibration
) -> None:
    """Калибровка — по ответу из сценария ответа: шаг Эло после каждого, после остановки
    попытки — ещё блокировка семейств попытки, связка шкалы и переоценка (§7)."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")

    answered = []
    view = paths.path(user)
    while view.stage == Stage.test:
        item = paths.current_item(user)
        result = paths.answer(user, presentation_id=item.presentation_id, response=WRONG)
        calibration.calls.clear()
        calibrations.calibrate(result.answer)
        answered.append((result.answer, list(calibration.calls)))
        view = result.view

    *going, (last, stop_calls) = answered
    assert all(not a.stopped and calls == ["learn"] for a, calls in going)
    assert last.stopped
    assert set(last.families) == {a.family_code for a, _ in answered}
    assert stop_calls == ["lock", "learn", "relink", "refit_due"]
