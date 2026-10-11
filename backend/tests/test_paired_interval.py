import uuid

from validation.report import paired_interval


def test_interval_covers_constant_difference_and_is_reproducible() -> None:
    needs = [uuid.UUID(int=i) for i in range(30)]
    ours = {n: 0.9 for n in needs}
    other = {n: 0.7 for n in needs}

    mean, low, high = paired_interval(ours, other)

    assert round(mean, 6) == 0.2
    assert low == high == mean or low <= mean <= high
    assert paired_interval(ours, other) == (mean, low, high)


def test_interval_widens_with_noisy_differences() -> None:
    needs = [uuid.UUID(int=i) for i in range(40)]
    ours = {n: float(i % 2) for i, n in enumerate(needs)}
    other = {n: 0.5 for n in needs}

    mean, low, high = paired_interval(ours, other)

    assert abs(mean) < 1e-9
    assert low < 0 < high
