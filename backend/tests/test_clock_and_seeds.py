"""Часы и источники seed — реализации портов `Clock` и `SeedSource`."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.adapter.clock import FrozenClock, SimulatedClock, SystemClock
from app.adapter.seed import SEED_BITS, DerivedSeeds, FixedSeeds, SecureSeeds

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def test_system_clock_is_aware_utc() -> None:
    before = datetime.now(UTC)
    now = SystemClock().now()

    assert now.tzinfo is UTC
    assert before <= now <= datetime.now(UTC)


def test_frozen_clock_stands_until_moved() -> None:
    clock = FrozenClock(T0)
    assert clock.now() == clock.now() == T0

    clock.shift(timedelta(hours=25))
    assert clock.now() == T0 + timedelta(hours=25)
    # Тест двигает часы и назад — как синхронизация времени на сервере.
    clock.shift(timedelta(seconds=-5))
    assert clock.now() == T0 + timedelta(hours=25, seconds=-5)
    clock.set(T0)
    assert clock.now() == T0


def test_simulated_clock_stands_until_the_stand_moves_it() -> None:
    clock = SimulatedClock(T0)
    assert clock.now() == clock.now() == T0

    clock.advance(timedelta(days=7))
    assert clock.now() == T0 + timedelta(days=7)
    clock.advance_to(T0 + timedelta(days=30))
    assert clock.now() == T0 + timedelta(days=30)


def test_simulated_time_never_goes_back() -> None:
    clock = SimulatedClock(T0)

    with pytest.raises(ValueError):
        clock.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError):
        clock.advance_to(T0 - timedelta(seconds=1))
    assert clock.now() == T0


@pytest.mark.parametrize("make", [FrozenClock, SimulatedClock])
def test_clocks_keep_utc(make: type[FrozenClock] | type[SimulatedClock]) -> None:
    with pytest.raises(ValueError):
        make(datetime(2026, 10, 7, 12, 0))

    clock = make(datetime(2026, 10, 7, 15, 0, tzinfo=timezone(timedelta(hours=3))))

    assert clock.now() == T0
    assert clock.now().tzinfo is UTC


def test_secure_seeds_fit_the_column_and_differ() -> None:
    source = SecureSeeds()
    seeds = [source.seed() for _ in range(100)]

    assert all(0 <= s < 2**SEED_BITS for s in seeds)
    assert len(set(seeds)) == len(seeds)


def test_fixed_seeds_repeat_the_value() -> None:
    source = FixedSeeds(42)

    assert [source.seed() for _ in range(3)] == [42, 42, 42]
    for bad in (-1, 2**SEED_BITS):
        with pytest.raises(ValueError):
            FixedSeeds(bad)


def test_derived_seeds_are_a_reproducible_sequence_of_the_run_seed() -> None:
    a, b, other = DerivedSeeds(7), DerivedSeeds(7), DerivedSeeds(8)

    sequence = [a.seed() for _ in range(50)]

    assert sequence == [b.seed() for _ in range(50)]
    assert len(set(sequence)) == len(sequence)
    assert all(0 <= s < 2**SEED_BITS for s in sequence)
    assert sequence != [other.seed() for _ in range(50)]
