"""Сценарии пути кандидата на in-memory репозиториях — без Postgres (mechanics.md, §4, §6).

Та же сборка, что в `backend/main.py`, только хранилище в памяти: остановка по точности,
каскад вниз и подсказка «грейд выше» проверяются на сценариях напрямую, без HTTP.
"""

import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter import irt
from app.adapter.adaptive import MaxInformationSelector
from app.adapter.calibration import EloCalibration
from app.adapter.catalog_file import load_catalog
from app.adapter.clock import FrozenClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.seed import DerivedSeeds
from app.domain import bank
from app.domain.attempt import (
    AttemptOutcome,
    AttemptPurpose,
    GradeUp,
    HistoryEvent,
    PathView,
    Stage,
)
from app.domain.bank import Family, get_family
from app.domain.calibration import ExpertGap, Parameters
from app.domain.catalog import Grade, Specialization, Topic
from app.domain.errors import (
    AttemptInProgress,
    CategoryRequired,
    GradeChangeTooEarly,
    GradeNotNext,
    NoLowerGrade,
    NoTestInProgress,
    StepUnavailable,
    TopicBlockTooEarly,
    TopicNotInCategory,
)
from app.domain.skill import Normal
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.fsp import MemoryFspEvidence
from app.repository.memory.regular_task import MemoryRegularTasks
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.skill_profile import specialization_prior
from composition import drift_detector
from settings import CATALOG_FILE, Mechanics, Settings

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = load_catalog(CATALOG_FILE)
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

    def expert_gaps(self, families: Sequence[bank.Family]) -> dict[str, ExpertGap]:
        self.calls.append("expert_gaps")
        return self.inner.expert_gaps(families)

    def compromised(self, codes: Iterable[str]) -> set[str]:
        return self.inner.compromised(codes)


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
        MemoryRegularTasks(store),
        MemoryFspEvidence(store, load_catalog(CATALOG_FILE).fsp_disciplines),
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
    return AnswerCalibration(
        MemoryUnitOfWork(store),
        calibration,
        drift_detector(MemoryCalibrationRepository(store), MECHANICS),
    )


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
            assert answered.answer is not None
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
        assert result.answer is not None
        calibrations.calibrate(result.answer)
        answered.append((result.answer, list(calibration.calls)))
        view = result.view

    *going, (last, stop_calls) = answered
    assert all(not a.stopped and calls == ["learn"] for a, calls in going)
    assert last.stopped
    assert set(last.families) == {a.family_code for a, _ in answered}
    assert stop_calls == ["lock", "learn", "relink", "refit_due"]


def _category(paths: CandidatePath, user: uuid.UUID) -> str:
    view = paths.path(user)
    assert view.stage == Stage.category and view.category is not None, view
    return view.category.grade.code


def _determine(
    paths: CandidatePath, answer_items: AnswerItems, claimed: str = "middle"
) -> uuid.UUID:
    """Кандидат сразу проходит заявленный грейд — все ответы верны."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade=claimed)
    answer_items(user, lambda family: True)
    assert _category(paths, user) == claimed
    return user


def test_grade_up_right_after_passing_claimed_grade(
    paths: CandidatePath, answer_items: AnswerItems
) -> None:
    """Первое определение часы не сдвигает: прошедший заявленный грейд сразу пробует выше, и
    прошедшая попытка меняет категорию (§4)."""
    user = _determine(paths, answer_items)
    assert paths.path(user).grade_up == GradeUp("senior", None)

    started = paths.start_attempt(user, grade="senior")
    assert started.stage == Stage.test and started.category is not None
    view = answer_items(user, lambda family: True)

    assert _category(paths, user) == "senior"
    assert view.grade_up is None
    assert view.history[-1].purpose == AttemptPurpose.grade_up
    assert view.history[-1].outcome == AttemptOutcome.assigned


def test_failed_grade_up_keeps_category_and_holds_short_interval(
    paths: CandidatePath, clock: FrozenClock, answer_items: AnswerItems
) -> None:
    """Провал попытки вверх категорию не меняет и часы смены не сдвигает: повтор на тот же
    грейд — через `grade_retry_interval_days`, не через `grade_change_interval_days`."""
    user = _determine(paths, answer_items)
    paths.start_attempt(user, grade="senior")
    view = answer_items(user, lambda family: False)

    assert _category(paths, user) == "middle"
    failed_at = clock.now()
    retry = failed_at + timedelta(days=MECHANICS.grade_retry_interval_days)
    assert view.grade_up == GradeUp("senior", retry)
    assert view.history[-1].outcome == AttemptOutcome.not_passed
    with pytest.raises(GradeChangeTooEarly) as early:
        paths.start_attempt(user, grade="senior")
    assert early.value.available_at == retry

    clock.shift(timedelta(days=MECHANICS.grade_retry_interval_days))
    assert paths.start_attempt(user, grade="senior").stage == Stage.test


def test_grade_up_starts_from_clean_prior(
    paths: CandidatePath, attempts: MemoryAttemptRepository, answer_items: AnswerItems
) -> None:
    """Попытка вверх — измерение с чистого листа: оценка до первого ответа — априорное, а не
    оценка прошлых попыток. Профиль навыков копит все попытки."""
    user = _determine(paths, answer_items)
    before = len(attempts.answered(user, "qa"))
    paths.start_attempt(user, grade="senior")
    item = paths.current_item(user)

    attempt = attempts.state(user).attempt
    assert attempt is not None and attempt.purpose == AttemptPurpose.grade_up
    assert attempt.continues_attempt_id is None
    prior = specialization_prior([t.code for t in SPECIALIZATIONS["qa"].topics], MECHANICS)
    first = attempt.presentations[0]
    assert first.topic_code == item.topic.code
    expected = irt.initial(prior).topic(first.topic_code)
    assert (first.topic_theta_before, first.topic_theta_sd_before) == (expected.mean, expected.sd)

    answer_items(user, lambda family: True)
    assert len(attempts.answered(user, "qa")) > before


def test_step_down_is_immediate_and_moves_the_clock(
    paths: CandidatePath,
    attempts: MemoryAttemptRepository,
    clock: FrozenClock,
    answer_items: AnswerItems,
) -> None:
    """Переход вниз — без теста и без ожидания: заданий не показано, грейд сменился сразу. Это
    смена: обратно вверх — через `grade_change_interval_days`."""
    user = _determine(paths, answer_items)
    shown = len(attempts.answered(user, "qa"))
    assert paths.path(user).grade_down == "junior"

    view = paths.step_down(user)

    assert view.stage == Stage.category
    assert _category(paths, user) == "junior"
    assert len(attempts.answered(user, "qa")) == shown
    state = attempts.state(user)
    assert state.attempt is not None and state.attempt.finished_at is not None
    back = clock.now() + timedelta(days=MECHANICS.grade_change_interval_days)
    assert view.grade_up == GradeUp("middle", back)
    assert view.history[-1].event == HistoryEvent.step_down
    # Подсказка «попробуйте senior» после перехода вниз устарела.
    assert view.result is not None and view.result.grade_up_hint is None

    # Вниз ждать не нужно — ещё раз сразу.
    assert _category_after(paths.step_down(user)) == "intern"
    with pytest.raises(NoLowerGrade):
        paths.step_down(user)

    with pytest.raises(GradeChangeTooEarly):
        paths.start_attempt(user, grade="junior")
    clock.shift(timedelta(days=MECHANICS.grade_change_interval_days))
    assert paths.start_attempt(user, grade="junior").stage == Stage.test


def _category_after(view: PathView) -> str:
    assert view.category is not None
    return view.category.grade.code


def test_grade_up_after_change_waits_for_change_interval(
    paths: CandidatePath, clock: FrozenClock, answer_items: AnswerItems
) -> None:
    """Попытка вверх раньше `grade_change_interval_days` после смены вверх отклоняется с датой,
    когда можно."""
    user = _determine(paths, answer_items, claimed="junior")
    paths.start_attempt(user, grade="middle")
    answer_items(user, lambda family: True)
    assert _category(paths, user) == "middle"
    allowed = clock.now() + timedelta(days=MECHANICS.grade_change_interval_days)

    clock.shift(timedelta(days=MECHANICS.grade_change_interval_days - 1))
    with pytest.raises(GradeChangeTooEarly) as early:
        paths.start_attempt(user, grade="senior")
    assert early.value.available_at == allowed

    clock.shift(timedelta(days=1))
    assert paths.start_attempt(user, grade="senior").stage == Stage.test


def test_claimed_grade_lost_in_cascade_holds_short_interval(
    paths: CandidatePath, clock: FrozenClock, answer_items: AnswerItems
) -> None:
    """Каскад увёл ниже заявленного: заявленный грейд держит короткий интервал, как
    проваленный."""
    user = uuid.uuid4()
    paths.submit_survey(user, specialization="qa")
    paths.start_attempt(user, grade="middle")
    view = answer_items(user, lambda family: family.grade in ("intern", "junior"))
    assert _category_after(view) == "junior"

    retry = clock.now() + timedelta(days=MECHANICS.grade_retry_interval_days)
    assert view.grade_up == GradeUp("middle", retry)
    with pytest.raises(GradeChangeTooEarly):
        paths.start_attempt(user, grade="middle")


def test_grade_up_only_to_next_grade(paths: CandidatePath, answer_items: AnswerItems) -> None:
    user = _determine(paths, answer_items, claimed="junior")
    with pytest.raises(GradeNotNext):
        paths.start_attempt(user, grade="senior")
    with pytest.raises(GradeNotNext):
        paths.start_attempt(user, grade="junior")


# Блок по теме (§6).

BLOCK_TOPIC = "qa.api"


def _answer_block(
    paths: CandidatePath,
    calibrations: AnswerCalibration,
    user: uuid.UUID,
    correct: Callable[[Family], bool],
) -> tuple[PathView, list[str]]:
    """Отвечает на задания блока до его конца, как контроллер; возвращает шаг пути и семейства
    заданий по порядку."""
    view, shown = paths.path(user), []
    while view.topic_block is not None:
        item = paths.current_item(user)
        assert item.topic_block and item.max_items == MECHANICS.topic_block_items
        family = get_family(item.family_code)
        shown.append(family.code)
        response = item.instance.answer if correct(family) else WRONG
        answered = paths.answer(user, presentation_id=item.presentation_id, response=response)
        assert answered.answer is not None
        calibrations.calibrate(answered.answer)
        view = answered.view
    return view, shown


def _topic_level(view: PathView, topic: str) -> tuple[float, float]:
    assert view.profile is not None
    level = next(t.level for t in view.profile.topics if t.topic.code == topic)
    return level.theta, level.theta_sd


def test_topic_block_refines_profile_and_keeps_path(
    paths: CandidatePath,
    attempts: MemoryAttemptRepository,
    store: MemoryStore,
    calibrations: AnswerCalibration,
    clock: FrozenClock,
    answer_items: AnswerItems,
) -> None:
    """Блок — ровно `topic_block_items` заданий по семействам темы: предъявления сохранены и
    сдвигают калибровку семейств, уровень и погрешность темы в профиле меняются. Категория,
    журнал смен, стадия, история и попытка вверх — как до блока."""
    user = _determine(paths, answer_items, claimed="junior")
    clock.shift(timedelta(hours=1))
    before = paths.path(user)
    changes = attempts.category_changes(user)
    responses = {code: f.responses for code, f in store.collection("families").items()}

    started = paths.start_topic_block(user, topic=BLOCK_TOPIC)
    assert started.topic_block is not None
    assert (started.topic_block.topic.code, started.topic_block.answered) == (BLOCK_TOPIC, 0)
    assert started.topic_block.items == MECHANICS.topic_block_items
    view, shown = _answer_block(paths, calibrations, user, lambda family: False)

    assert len(shown) == MECHANICS.topic_block_items == len(set(shown))
    assert all(get_family(code).topic == BLOCK_TOPIC for code in shown)
    block = attempts.attempts(user)[-1]
    assert block.purpose == AttemptPurpose.topic_block and block.finished_at is not None
    assert [p.family_code for p in block.presentations] == shown
    assert all(p.topic_theta_rest is not None for p in block.presentations)
    families = store.collection("families")
    assert all(families[code].responses == responses.get(code, 0) + 1 for code in shown)

    assert view.topic_block is None
    assert _topic_level(view, BLOCK_TOPIC) != _topic_level(before, BLOCK_TOPIC)
    assert view.profile is not None and before.profile is not None
    assert view.profile.updated_at > before.profile.updated_at
    assert (view.stage, view.category, view.result) == (
        before.stage,
        before.category,
        before.result,
    )
    assert (view.history, view.grade_up, view.grade_down) == (
        before.history,
        before.grade_up,
        before.grade_down,
    )
    assert attempts.category_changes(user) == changes


def test_topic_block_too_early_counts_from_start(
    paths: CandidatePath,
    calibrations: AnswerCalibration,
    clock: FrozenClock,
    answer_items: AnswerItems,
) -> None:
    """Интервал — от старта прошлого блока по теме, а не от его конца: блок, брошенный и
    законченный через месяц, держит тему тот же срок. По другой теме блок можно сразу."""
    user = _determine(paths, answer_items)
    started_at = clock.now()
    allowed = started_at + timedelta(days=MECHANICS.topic_block_interval_days)
    paths.start_topic_block(user, topic=BLOCK_TOPIC)
    paths.current_item(user)
    clock.shift(timedelta(days=MECHANICS.topic_block_interval_days - 1))
    _answer_block(paths, calibrations, user, lambda family: True)

    with pytest.raises(TopicBlockTooEarly) as early:
        paths.start_topic_block(user, topic=BLOCK_TOPIC)
    assert early.value.available_at == allowed

    other = paths.start_topic_block(user, topic="qa.theory")
    assert other.topic_block is not None and other.topic_block.topic.code == "qa.theory"
    _answer_block(paths, calibrations, user, lambda family: True)

    clock.shift(timedelta(days=1))
    assert paths.start_topic_block(user, topic=BLOCK_TOPIC).topic_block is not None


def test_topic_block_needs_category_and_its_topic(
    paths: CandidatePath, answer_items: AnswerItems
) -> None:
    newcomer = uuid.uuid4()
    paths.submit_survey(newcomer, specialization="qa")
    with pytest.raises(CategoryRequired):
        paths.start_topic_block(newcomer, topic=BLOCK_TOPIC)

    user = _determine(paths, answer_items)
    with pytest.raises(TopicNotInCategory):
        paths.start_topic_block(user, topic="backend.databases")
    with pytest.raises(TopicNotInCategory):
        paths.start_topic_block(user, topic="qa.unknown")


def test_one_unfinished_attempt_per_candidate(
    paths: CandidatePath,
    calibrations: AnswerCalibration,
    answer_items: AnswerItems,
) -> None:
    """Пока идёт блок, попытка вверх не начинается, и наоборот; брошенный блок продолжается с
    того же задания."""
    user = _determine(paths, answer_items, claimed="junior")
    paths.start_topic_block(user, topic=BLOCK_TOPIC)
    first = paths.current_item(user)

    with pytest.raises(AttemptInProgress):
        paths.start_attempt(user, grade="middle")
    with pytest.raises(AttemptInProgress):
        paths.start_topic_block(user, topic="qa.theory")
    assert paths.current_item(user).presentation_id == first.presentation_id

    _answer_block(paths, calibrations, user, lambda family: True)
    paths.start_attempt(user, grade="middle")
    with pytest.raises(AttemptInProgress):
        paths.start_topic_block(user, topic="qa.theory")


def test_block_stops_when_topic_families_leave_rotation(
    paths: CandidatePath,
    attempts: MemoryAttemptRepository,
    store: MemoryStore,
    calibrations: AnswerCalibration,
    answer_items: AnswerItems,
) -> None:
    """Калибровка вывела оставшиеся семейства темы из выдачи посреди блока — блок
    останавливается при запросе задания, а не висит незавершённой попыткой."""
    user = _determine(paths, answer_items)
    paths.start_topic_block(user, topic=BLOCK_TOPIC)
    item = paths.current_item(user)
    first = paths.answer(user, presentation_id=item.presentation_id, response=WRONG).answer
    assert first is not None
    calibrations.calibrate(first)
    repository = MemoryCalibrationRepository(store)
    for family in bank.families_for_topics([BLOCK_TOPIC]):
        if family.code != item.family_code:
            row = repository.locked(family.code, Parameters(1.0, 0.0))
            row.in_rotation = False
            repository.save(row)

    with pytest.raises(NoTestInProgress):
        paths.current_item(user)

    assert paths.path(user).topic_block is None
    block = attempts.attempts(user)[-1]
    assert block.purpose == AttemptPurpose.topic_block and block.finished_at is not None
