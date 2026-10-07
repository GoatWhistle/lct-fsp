"""Часы — реализации порта `Clock`: системные, замороженные для тестов и часы стенда."""

from datetime import UTC, datetime, timedelta


def _utc(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("момент без часового пояса — неизвестно, какое это время")
    return at.astimezone(UTC)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Часы тестов: стоят на месте, сдвигаются только явно — вперёд и назад."""

    def __init__(self, at: datetime) -> None:
        self._now = _utc(at)

    def now(self) -> datetime:
        return self._now

    def set(self, at: datetime) -> None:
        self._now = _utc(at)

    def shift(self, delta: timedelta) -> None:
        self._now += delta


class SimulatedClock:
    """Часы стенда валидации: время стоит, пока стенд его не сдвинет, и назад не идёт."""

    def __init__(self, start: datetime) -> None:
        self._now = _utc(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("время стенда назад не идёт")
        self._now += delta

    def advance_to(self, at: datetime) -> None:
        self.advance(_utc(at) - self._now)
