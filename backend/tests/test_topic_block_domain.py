"""Правило интервала блока по теме — чистая функция домена (mechanics.md, §6)."""

import uuid
from datetime import UTC, datetime, timedelta

from app.domain.attempt import (
    Attempt,
    AttemptPurpose,
    topic_block_available_at,
    topic_block_starts,
)

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
INTERVAL = timedelta(days=30)


def attempt(
    started_at: datetime,
    *,
    purpose: AttemptPurpose = AttemptPurpose.topic_block,
    topic: str | None = "qa.api",
    finished: bool = True,
) -> Attempt:
    return Attempt(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        number=1,
        survey_id=uuid.uuid4(),
        specialization_code="qa",
        grade_code="middle",
        continues_attempt_id=None,
        started_at=started_at,
        purpose=purpose,
        topic_code=topic if purpose == AttemptPurpose.topic_block else None,
        finished_at=started_at + timedelta(minutes=10) if finished else None,
    )


def test_without_blocks_topic_is_available() -> None:
    assert topic_block_available_at({}, "qa.api", T0, INTERVAL) is None


def test_block_holds_its_topic_until_interval_from_start() -> None:
    starts = {"qa.api": T0}

    assert topic_block_available_at(starts, "qa.api", T0 + timedelta(days=29), INTERVAL) == (
        T0 + INTERVAL
    )
    assert topic_block_available_at(starts, "qa.api", T0 + INTERVAL, INTERVAL) is None
    assert topic_block_available_at(starts, "qa.theory", T0, INTERVAL) is None


def test_starts_are_latest_per_topic_and_count_abandoned_blocks() -> None:
    """Брошенный блок тоже держит тему: интервал — от старта, а не от завершения."""
    attempts = [
        attempt(T0),
        attempt(T0 + timedelta(days=40), finished=False),
        attempt(T0 + timedelta(days=5), topic="qa.theory"),
        attempt(T0 + timedelta(days=50), purpose=AttemptPurpose.grade_up),
    ]

    assert topic_block_starts(attempts) == {
        "qa.api": T0 + timedelta(days=40),
        "qa.theory": T0 + timedelta(days=5),
    }
