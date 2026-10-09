"""Защита теста на сценариях пути (mechanics.md, §8): события с согласия, флаги времени,
подозрительный результат, проверочный блок и скомпрометированные семейства — на in-memory
хранилищах, через те же сценарии, что HTTP."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter import irt
from app.adapter.catalog_file import load_catalog
from app.adapter.clock import FrozenClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.seed import DerivedSeeds
from app.domain import bank
from app.domain.attempt import AttemptOutcome, AttemptPurpose, PathView, Stage
from app.domain.bank import Family, get_family
from app.domain.calibration import Parameters
from app.domain.catalog import Grade, Specialization, Topic
from app.domain.errors import (
    AttemptInProgress,
    VerificationPending,
    VerificationTooEarly,
    VerificationUnavailable,
)
from app.domain.skill import Normal, SignalSource
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.fsp import MemoryFspEvidence
from app.repository.memory.regular_task import MemoryRegularTasks
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from composition import drift_detector, elo_calibration, item_selector
from settings import CATALOG_FILE, Mechanics, Settings

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = load_catalog(CATALOG_FILE)
GRADES = {g.code: Grade(g.code, g.name, g.rank) for g in CATALOG.grades}
SPECIALIZATIONS = {
    s.code: Specialization(s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics))
    for s in CATALOG.specializations
}
SPECIALIZATION = "qa"
WRONG = "ответа нет"


@dataclass
class Bench:
    """Сценарии пути и калибровки на своём хранилище, часах и seed."""

    mechanics: Mechanics = MECHANICS
    seed: int = 0
    store: MemoryStore = field(default_factory=MemoryStore)
    clock: FrozenClock = field(default_factory=lambda: FrozenClock(T0))

    def __post_init__(self) -> None:
        self.attempts = MemoryAttemptRepository(
            self.store,
            SPECIALIZATIONS,
            GRADES,
            self.mechanics.grade_thresholds,
            self.mechanics.grade_confidence,
        )
        self.calibration = MemoryCalibrationRepository(self.store)
        uow = MemoryUnitOfWork(self.store)
        calibration = elo_calibration(self.calibration, self.mechanics)
        self.paths = CandidatePath(
            uow,
            self.attempts,
            MemoryRegularTasks(self.store),
            MemoryFspEvidence(self.store, CATALOG.fsp_disciplines),
            calibration,
            item_selector(self.mechanics),
            irt,
            self.clock,
            DerivedSeeds(self.seed),
            InProcessCodeRunner(),
            self.mechanics,
        )
        self.calibrations = AnswerCalibration(
            uow, calibration, drift_detector(self.calibration, self.mechanics)
        )

    def enrol(self, user: uuid.UUID | None = None) -> uuid.UUID:
        user = user or uuid.uuid4()
        self.paths.submit_survey(user, specialization=SPECIALIZATION)
        return user

    def answer(
        self,
        user: uuid.UUID,
        correct: Callable[[Family], bool],
        *,
        seconds: float = 60.0,
        focus_losses: int = 0,
        until: Callable[[PathView], bool] = lambda view: view.stage == Stage.test,
    ) -> PathView:
        """Отвечает на задания, пока `until`, как контроллер: после ответа — калибровка."""
        view = self.paths.path(user)
        while until(view):
            item = self.paths.current_item(user)
            self.clock.shift(timedelta(seconds=seconds))
            response = item.instance.answer if correct(get_family(item.family_code)) else WRONG
            answered = self.paths.answer(
                user,
                presentation_id=item.presentation_id,
                response=response,
                focus_losses=focus_losses,
            )
            if answered.answer is not None:
                self.calibrations.calibrate(answered.answer)
            view = answered.view
        return view

    def block(self, user: uuid.UUID, correct: Callable[[Family], bool]) -> PathView:
        """Проверочный блок до остановки."""
        return self.answer(
            user,
            correct,
            until=lambda v: v.verification is not None and v.verification.progress is not None,
        )

    def determine(
        self, user: uuid.UUID, grade: str = "middle", *, consent: bool = False, focus: int = 0
    ) -> PathView:
        self.paths.start_attempt(user, grade=grade, focus_consent=consent)
        return self.answer(user, lambda f: True, focus_losses=focus)

    def path_attempt(self, user: uuid.UUID):  # type: ignore[no-untyped-def]
        with self.paths._uow:
            return self.attempts.state(user).attempt


def always(_: Family) -> bool:
    return True


def never(_: Family) -> bool:
    return False


@pytest.fixture
def bench() -> Bench:
    return Bench()


# События вставки и потери фокуса.


def test_without_consent_events_are_not_written_and_test_goes_the_same() -> None:
    """Без согласия счётчики отбрасываются: те же задания, та же оценка, тот же исход, что и у
    кандидата без событий вовсе."""
    noisy, quiet = Bench(), Bench()
    user = uuid.UUID(int=1)
    for b, focus in ((noisy, 9), (quiet, 0)):
        b.enrol(user)
        b.paths.start_attempt(user, grade="middle")
        b.answer(user, always, focus_losses=focus)
    one, two = noisy.path_attempt(user), quiet.path_attempt(user)
    assert [p.family_code for p in one.presentations] == [p.family_code for p in two.presentations]
    assert one.overall == two.overall
    assert one.outcome == two.outcome == AttemptOutcome.assigned
    assert all(p.paste_events is None and p.focus_losses is None for p in one.presentations)
    assert noisy.paths.path(user).stage == Stage.category


def test_with_consent_events_are_counted(bench: Bench) -> None:
    user = bench.enrol()
    bench.determine(user, consent=True, focus=1)
    attempt = bench.path_attempt(user)
    assert attempt.focus_consent
    assert all(p.focus_losses == 1 and p.paste_events == 0 for p in attempt.presentations)


# Подозрительный результат.


def test_suspicious_first_assignment_waits_for_verification_block(bench: Bench) -> None:
    """Присвоение впервые с событиями не ниже порога — категории нет, результат ждёт блока,
    наблюдения попытки — вне профиля."""
    user = bench.enrol()
    view = bench.determine(user, consent=True, focus=MECHANICS.focus_events_for_verification)
    assert view.stage == Stage.verification
    assert view.category is None
    assert view.verification is not None and view.verification.grade == "middle"
    assert view.verification.available_at is None and view.verification.last is None
    attempt = bench.path_attempt(user)
    assert attempt.outcome == AttemptOutcome.verification and attempt.withheld
    with bench.paths._uow:
        assert bench.attempts.answered(user, SPECIALIZATION) == []


def test_attempt_that_does_not_raise_category_gets_no_block(bench: Bench) -> None:
    """Попытка вверх, которая не прошла, с теми же событиями — проверять нечего."""
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_attempt(user, grade="senior", focus_consent=True)
    view = bench.answer(user, never, focus_losses=5)
    assert bench.path_attempt(user).outcome == AttemptOutcome.not_passed
    assert view.stage == Stage.category and view.category is not None
    assert view.category.grade.code == "middle"
    assert view.verification is not None and view.verification.grade is None


def test_flag_without_block_does_not_lower_category(bench: Bench) -> None:
    """Подозрительная попытка вверх категорию не повышает и не понижает: прежняя остаётся, а
    попытка вверх ждёт блока."""
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_attempt(user, grade="senior", focus_consent=True)
    view = bench.answer(user, always, focus_losses=5)
    assert view.stage == Stage.category and view.category is not None
    assert view.category.grade.code == "middle"
    assert view.grade_up is None
    assert view.verification is not None and view.verification.grade == "senior"
    with pytest.raises(VerificationPending):
        bench.paths.start_attempt(user, grade="senior")


# Проверочный блок.


def _suspicious(bench: Bench, grade: str = "middle") -> uuid.UUID:
    user = bench.enrol()
    bench.determine(user, grade, consent=True, focus=MECHANICS.focus_events_for_verification)
    return user


def test_block_match_assigns_category_with_verified_mark(bench: Bench) -> None:
    user = _suspicious(bench)
    started = bench.paths.start_verification(user)
    assert started.verification is not None and started.verification.progress is not None
    assert started.verification.progress.deadline == T0 + timedelta(
        minutes=MECHANICS.verification_time_limit_minutes
    ) + _elapsed(bench)
    item = bench.paths.current_item(user)
    assert item.verification and item.max_items == MECHANICS.verification_items
    view = bench.block(user, always)

    assert view.stage == Stage.category and view.category is not None
    assert view.category.grade.code == "middle"
    assert view.category.verified_at is not None
    assert view.verification is None
    assert bench.path_attempt(user).outcome == AttemptOutcome.assigned
    with bench.paths._uow:
        answered = bench.attempts.answered(user, SPECIALIZATION)
    sources = {a.source for a in answered}
    assert sources == {SignalSource.test, SignalSource.verification}
    assert view.profile is not None
    assert any(SignalSource.verification in t.sources for t in view.profile.topics)


def _elapsed(bench: Bench) -> timedelta:
    return bench.clock.now() - T0


def test_block_shows_unseen_families_of_attempt_topics(bench: Bench) -> None:
    user = _suspicious(bench)
    seen = {p.family_code for p in bench.path_attempt(user).presentations}
    bench.paths.start_verification(user)
    bench.block(user, always)
    with bench.paths._uow:
        block = next(
            a for a in bench.attempts.attempts(user) if a.purpose == AttemptPurpose.verification
        )
    shown = [p.family_code for p in block.presentations]
    assert len(shown) == MECHANICS.verification_items
    assert not seen & set(shown)
    topics = {t.code for t in SPECIALIZATIONS[SPECIALIZATION].topics}
    assert {get_family(c).topic for c in shown} <= topics


def test_block_mismatch_keeps_previous_category_and_shows_reason(bench: Bench) -> None:
    """Расхождение: категории нет, как и не было; наблюдения попытки — вне профиля, блока — в
    нём; кандидат видит числа и когда повтор; провал не сжигает попытку."""
    user = _suspicious(bench)
    started_at = bench.clock.now()
    bench.paths.start_verification(user)
    view = bench.block(user, never)

    assert view.stage == Stage.verification and view.category is None
    assert view.verification is not None
    last = view.verification.last
    assert last is not None and not last.confirmed
    assert last.correct == 0 and last.items == MECHANICS.verification_items
    assert last.expected > 3
    assert view.verification.available_at == started_at + timedelta(
        days=MECHANICS.verification_retest_days
    )
    with pytest.raises(VerificationTooEarly):
        bench.paths.start_verification(user)
    with bench.paths._uow:
        answered = bench.attempts.answered(user, SPECIALIZATION)
    assert answered and {a.source for a in answered} == {SignalSource.verification}

    # Повтор на грейд ниже — сразу, с чистого листа: провал короткий интервал не включает.
    lower = bench.paths.start_attempt(user, grade="junior")
    assert lower.stage == Stage.test
    assert bench.path_attempt(user).continues_attempt_id is None


def test_block_retest_after_interval_can_confirm(bench: Bench) -> None:
    user = _suspicious(bench)
    bench.paths.start_verification(user)
    bench.block(user, never)
    bench.clock.shift(timedelta(days=MECHANICS.verification_retest_days))
    bench.paths.start_verification(user)
    view = bench.block(user, always)
    assert view.category is not None and view.category.grade.code == "middle"
    assert view.category.verified_at is not None


def test_same_grade_attempt_is_refused_while_result_waits(bench: Bench) -> None:
    user = _suspicious(bench)
    with pytest.raises(VerificationPending):
        bench.paths.start_attempt(user, grade="middle")


def test_unanswered_by_deadline_counts_wrong(bench: Bench) -> None:
    """Срок прошёл — ответ не засчитан, блок остановлен, непоказанные задания — неверные."""
    user = _suspicious(bench)
    bench.paths.start_verification(user)
    item = bench.paths.current_item(user)
    bench.clock.shift(timedelta(minutes=MECHANICS.verification_time_limit_minutes))
    late = bench.paths.answer(
        user, presentation_id=item.presentation_id, response=item.instance.answer
    )
    assert late.answer is None
    assert late.view.verification is not None
    last = late.view.verification.last
    assert last is not None and not last.confirmed
    assert last.correct == 0 and last.items == MECHANICS.verification_items


def test_voluntary_block_confirms_category(bench: Bench) -> None:
    user = bench.enrol()
    view = bench.determine(user)
    assert view.verification is not None and view.verification.grade is None
    bench.paths.start_verification(user)
    view = bench.block(user, always)
    assert view.category is not None and view.category.verified_at is not None
    assert view.verification is None
    with pytest.raises(VerificationUnavailable):
        bench.paths.start_verification(user)


def test_grade_up_without_block_removes_verified_mark(bench: Bench) -> None:
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_verification(user)
    bench.block(user, always)
    bench.paths.start_attempt(user, grade="senior")
    view = bench.answer(user, always)
    assert view.category is not None and view.category.grade.code == "senior"
    assert view.category.verified_at is None


# Флаги времени.


FAST = MECHANICS.model_copy(update={"rt_min_responses": 2, "rt_flags_for_verification": 1})


def _warm_times(bench: Bench, candidates: int, seconds: float) -> None:
    for _ in range(candidates):
        user = bench.enrol()
        bench.paths.start_attempt(user, grade="middle")
        bench.answer(user, always, seconds=seconds)


def test_time_flag_only_on_correct_hard_fast_answer_and_level_is_the_same() -> None:
    """Флаг — только верный ответ на трудное задание аномально быстро; оценка уровня от времени
    не зависит: тот же кандидат медленно и быстро получает ту же оценку."""
    fast, slow = Bench(FAST), Bench(FAST)
    for b in (fast, slow):
        _warm_times(b, 6, seconds=120)
    user = uuid.UUID(int=7)
    fast.enrol(user)
    slow.enrol(user)
    fast.paths.start_attempt(user, grade="senior")
    slow.paths.start_attempt(user, grade="senior")
    fast.answer(user, lambda f: f.grade != "intern", seconds=2)
    slow.answer(user, lambda f: f.grade != "intern", seconds=120)
    quick, careful = fast.path_attempt(user), slow.path_attempt(user)
    assert quick.overall == careful.overall
    assert not any(p.time_flag for p in careful.presentations)
    flagged = [p for p in quick.presentations if p.time_flag]
    assert flagged
    for p in quick.presentations:
        p_correct = 1 / (
            1 + pow(2.718281828459045, -p.discrimination * (p.topic_theta_before - p.difficulty))
        )
        if p.time_flag:
            assert p.correct and p_correct <= FAST.rt_hard_item_p
        elif p.correct and p_correct <= FAST.rt_hard_item_p:
            pytest.fail("трудный быстрый верный ответ без флага")
    assert quick.outcome == AttemptOutcome.verification
    assert careful.outcome == AttemptOutcome.assigned


# Скомпрометированное семейство.


def _compromise(bench: Bench, code: str) -> None:
    with bench.paths._uow:
        row = bench.calibration.locked(code, Parameters(1.2, 0.0))
        row.compromised_at = bench.clock.now()
        bench.calibration.save(row)


def test_compromised_family_leaves_rotation_and_unfinished_attempt_estimate(bench: Bench) -> None:
    """Семейство помечено посреди попытки: больше не выдаётся, ответ на него выпадает из оценки
    попытки; у остановленной попытки — помечен выпавшим. Присвоенная раньше категория не
    меняется."""
    earlier = bench.enrol()
    bench.determine(earlier)

    user = bench.enrol()
    bench.paths.start_attempt(user, grade="middle")
    first = bench.paths.current_item(user)
    bench.paths.answer(user, presentation_id=first.presentation_id, response=first.instance.answer)
    _compromise(bench, first.family_code)
    view = bench.answer(user, always)

    attempt = bench.path_attempt(user)
    assert [p.family_code for p in attempt.presentations].count(first.family_code) == 1
    assert attempt.presentations[0].dropped
    rest = [p.answered().observation() for p in attempt.presentations[1:]]
    prior = bench.paths._prior(SPECIALIZATION)
    assert attempt.overall == irt.estimate(prior, rest).overall()
    with bench.paths._uow:
        answered = bench.attempts.answered(user, SPECIALIZATION)
        assert first.family_code not in {a.family_code for a in answered}
        assert bench.attempts.state(earlier).category is not None
    assert view.stage == Stage.category

    later = bench.enrol()
    bench.paths.start_attempt(later, grade="middle")
    bench.answer(later, always)
    shown = {p.family_code for p in bench.path_attempt(later).presentations}
    assert first.family_code not in shown


def test_drift_detector_flags_leaked_family_and_not_honest_one(bench: Bench) -> None:
    """Опорные параметры известны: правильные ответы слабых кандидатов на трудное семейство —
    тревога и вывод из выдачи; ответы по модели — нет."""
    detector = drift_detector(bench.calibration, MECHANICS)
    leaked, honest = (f.code for f in bank.families_for_topics(["qa.api"])[:2])
    with bench.paths._uow:
        for code in (leaked, honest):
            row = bench.calibration.locked(code, Parameters(1.2, 1.0))
            row.reference = Parameters(1.2, 1.0)
            bench.calibration.save(row)
    flagged = []
    with bench.paths._uow:
        for i in range(200):
            flagged.append(detector.observe(SPECIALIZATION, leaked, Normal(-0.5, 0.4), True, T0))
            detector.observe(SPECIALIZATION, honest, Normal(1.0, 0.4), i % 2 == 0, T0)
    assert any(flagged)
    with bench.paths._uow:
        rows = bench.calibration.parameters([leaked, honest])
    assert rows[leaked].is_compromised and not rows[honest].is_compromised
    calibration = elo_calibration(bench.calibration, MECHANICS)
    with bench.paths._uow:
        current = calibration.current([get_family(leaked), get_family(honest)])
    assert leaked not in current and honest in current


def test_step_down_is_refused_while_grade_up_waits_for_block(bench: Bench) -> None:
    """Иначе подтверждённый блок поднял бы категорию с нового грейда сразу на грейд попытки."""
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_attempt(user, grade="senior", focus_consent=True)
    bench.answer(user, always, focus_losses=5)
    with pytest.raises(VerificationPending):
        bench.paths.step_down(user)
    bench.paths.start_verification(user)
    with pytest.raises(AttemptInProgress):
        bench.paths.step_down(user)


def test_expired_block_is_closed_by_any_step(bench: Bench) -> None:
    """Срок прошёл без обращения к пути — следующий шаг кандидата сам останавливает блок."""
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_verification(user)
    bench.clock.shift(timedelta(minutes=MECHANICS.verification_time_limit_minutes))
    view = bench.paths.step_down(user)
    assert view.verification is not None and view.verification.progress is None
    assert view.category is not None and view.category.grade.code == "junior"


def test_voluntary_block_result_is_from_current_category_only(bench: Bench) -> None:
    """Итог блока по прошлой категории в добровольный блок нынешней не переносится."""
    user = bench.enrol()
    bench.determine(user)
    bench.paths.start_verification(user)
    bench.block(user, never)
    bench.paths.start_attempt(user, grade="senior")
    view = bench.answer(user, always)
    assert view.category is not None and view.category.grade.code == "senior"
    assert view.verification is not None and view.verification.last is None
