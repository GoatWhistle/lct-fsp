"""Статистики метрик стенда — без знания механик."""

import math
from collections.abc import Sequence


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / math.sqrt(vx * vy)


def rmse(xs: Sequence[float], ys: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys, strict=True)) / len(xs))


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def cohen_kappa(pairs: Sequence[tuple[object, object]], categories: Sequence[object]) -> float:
    """Каппа Коэна; не определена, когда все определения в одной категории, — тогда nan."""
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    expected = sum(
        sum(a == c for a, _ in pairs) / n * sum(b == c for _, b in pairs) / n for c in categories
    )
    return (observed - expected) / (1 - expected) if expected < 1 else math.nan
