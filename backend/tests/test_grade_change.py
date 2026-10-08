"""Правило ожидания смены грейда и история пути — чистые функции домена (mechanics.md, §4)."""

import uuid
from datetime import UTC, datetime, timedelta

from app.domain.attempt import (
    Attempt,
    AttemptOutcome,
    AttemptPurpose,
    CategoryChange,
    ChangeKind,
    HistoryEvent,
    grade_up_available_at,
    path_history,
)
from app.domain.skill import Normal

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
THRESHOLDS = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}
CHANGE = timedelta(days=90)
RETRY = timedelta(days=30)


def attempt(
    grade: str,
    outcome: AttemptOutcome,
    outcome_grade: str | None,
    finished_at: datetime,
    *,
    purpose: AttemptPurpose = AttemptPurpose.determination,
    number: int = 1,
) -> Attempt:
    return Attempt(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        number=number,
        survey_id=uuid.uuid4(),
        specialization_code="qa",
        grade_code=grade,
        continues_attempt_id=None,
        started_at=finished_at - timedelta(minutes=30),
        purpose=purpose,
        finished_at=finished_at,
        overall=Normal(0.0, 0.3),
        outcome=outcome,
        outcome_grade_code=outcome_grade,
    )


def available(
    target: str, attempts: list[Attempt], changes: list[CategoryChange]
) -> datetime | None:
    return grade_up_available_at(
        target,
        attempts,
        changes,
        thresholds=THRESHOLDS,
        change_interval=CHANGE,
        retry_interval=RETRY,
    )


def test_first_determination_does_not_move_the_clock() -> None:
    """Сразу прошёл заявленный грейд — попытка вверх доступна сразу."""
    attempts = [attempt("middle", AttemptOutcome.assigned, "middle", T0)]
    changes = [CategoryChange("middle", ChangeKind.determined, T0)]

    assert available("senior", attempts, changes) is None


def test_change_up_or_down_holds_the_long_interval() -> None:
    up = [CategoryChange("junior", ChangeKind.determined, T0)]
    up.append(CategoryChange("middle", ChangeKind.up, T0 + timedelta(days=5)))
    assert available("senior", [], up) == T0 + timedelta(days=5) + CHANGE

    down = [CategoryChange("middle", ChangeKind.determined, T0)]
    down.append(CategoryChange("junior", ChangeKind.down, T0 + timedelta(days=7)))
    assert available("middle", [], down) == T0 + timedelta(days=7) + CHANGE


def test_failed_attempt_holds_the_short_interval_for_its_grade_and_above() -> None:
    """Провал не сдвигает часы смены: держит только повтор на тот же грейд или выше."""
    failed_at = T0 + timedelta(days=100)
    attempts = [
        attempt("junior", AttemptOutcome.assigned, "junior", T0),
        attempt(
            "middle",
            AttemptOutcome.not_passed,
            None,
            failed_at,
            purpose=AttemptPurpose.grade_up,
            number=2,
        ),
    ]
    changes = [CategoryChange("junior", ChangeKind.determined, T0)]

    assert available("middle", attempts, changes) == failed_at + RETRY
    assert available("senior", attempts, changes) == failed_at + RETRY
    assert available("junior", attempts, changes) is None


def test_claimed_grade_lost_in_cascade_counts_as_failed() -> None:
    """Каскад увёл ниже заявленного — заявленный грейд держит короткий интервал, грейд ниже
    него — нет."""
    claimed = attempt("senior", AttemptOutcome.offered, "middle", T0)
    dotest = attempt("middle", AttemptOutcome.assigned, "junior", T0 + timedelta(minutes=20))
    changes = [CategoryChange("junior", ChangeKind.determined, dotest.finished_at or T0)]

    # Дотест на middle тоже не дался: каскад присвоил junior без дотеста.
    assert available("middle", [claimed, dotest], changes) == T0 + timedelta(minutes=20) + RETRY
    assert available("senior", [claimed, dotest], changes) == T0 + timedelta(minutes=20) + RETRY

    only_claimed = attempt("senior", AttemptOutcome.assigned, "middle", T0)
    changes = [CategoryChange("middle", ChangeKind.determined, T0)]
    assert available("senior", [only_claimed], changes) == T0 + RETRY


def test_latest_constraint_wins() -> None:
    attempts = [
        attempt(
            "middle",
            AttemptOutcome.not_passed,
            None,
            T0 + timedelta(days=95),
            purpose=AttemptPurpose.grade_up,
        )
    ]
    changes = [CategoryChange("junior", ChangeKind.down, T0)]

    assert available("middle", attempts, changes) == T0 + timedelta(days=125)


def test_history_lists_finished_attempts_and_steps_down_by_date() -> None:
    first = attempt("middle", AttemptOutcome.assigned, "middle", T0)
    up = attempt(
        "senior",
        AttemptOutcome.not_passed,
        None,
        T0 + timedelta(days=10),
        purpose=AttemptPurpose.grade_up,
        number=2,
    )
    running = attempt("senior", AttemptOutcome.assigned, "senior", T0, number=3)
    running.finished_at, running.outcome = None, None
    changes = [
        CategoryChange("middle", ChangeKind.determined, T0),
        CategoryChange("junior", ChangeKind.down, T0 + timedelta(days=5)),
    ]

    history = path_history([first, up, running], changes, thresholds=THRESHOLDS, confidence=0.8)

    assert [(h.event, h.grade, h.at) for h in history] == [
        (HistoryEvent.attempt, "middle", T0),
        (HistoryEvent.step_down, "junior", T0 + timedelta(days=5)),
        (HistoryEvent.attempt, "senior", T0 + timedelta(days=10)),
    ]
    assert history[0].overall is not None and history[0].overall.theta_sd == 0.3
    assert history[2].outcome == AttemptOutcome.not_passed
    assert history[2].purpose == AttemptPurpose.grade_up
    assert history[1].overall is None
