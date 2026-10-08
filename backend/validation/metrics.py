"""Статистики метрик стенда — без знания механик."""

import math
from collections.abc import Sequence
from dataclasses import dataclass


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


def point_biserial(binary: Sequence[float], values: Sequence[float]) -> float:
    """Точечно-бисериальная корреляция — Пирсон с бинарной переменной; без разброса — nan."""
    if len(set(binary)) < 2 or len(set(values)) < 2:
        return math.nan
    return pearson(binary, values)


@dataclass(frozen=True)
class Line:
    """Прямая наименьших квадратов y = intercept + slope · x и sd остатка вокруг неё."""

    intercept: float
    slope: float
    residual_sd: float


def regression(xs: Sequence[float], ys: Sequence[float]) -> Line:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mx) ** 2 for x in xs
    )
    intercept = my - slope * mx
    residual = [y - intercept - slope * x for x, y in zip(xs, ys, strict=True)]
    return Line(intercept, slope, math.sqrt(sum(r**2 for r in residual) / len(xs)))


@dataclass(frozen=True)
class Bin:
    """Корзина надёжностной диаграммы: [lower, upper), средняя предсказанная вероятность и
    средняя наблюдаемая доля; пустая корзина — nan."""

    lower: float
    upper: float
    count: int
    confidence: float
    accuracy: float


def reliability(predicted: Sequence[float], observed: Sequence[float], bins: int = 10) -> list[Bin]:
    """Равные корзины по предсказанию на [0, 1]; единица — в последней."""
    members: list[list[int]] = [[] for _ in range(bins)]
    for i, p in enumerate(predicted):
        members[min(int(p * bins), bins - 1)].append(i)
    return [
        Bin(
            b / bins,
            (b + 1) / bins,
            len(ids),
            sum(predicted[i] for i in ids) / len(ids) if ids else math.nan,
            sum(observed[i] for i in ids) / len(ids) if ids else math.nan,
        )
        for b, ids in enumerate(members)
    ]


def ece(predicted: Sequence[float], observed: Sequence[float], bins: int = 10) -> float:
    """ECE = Σ_b n_b / N · |acc_b − conf_b|; наблюдаемое — метки 0/1 или доли."""
    n = len(predicted)
    return sum(
        b.count / n * abs(b.accuracy - b.confidence)
        for b in reliability(predicted, observed, bins)
        if b.count
    )


def precision_at(ranked: Sequence[int], k: int, relevant: int = 2) -> float:
    """Доля релевантных (градация не ниже `relevant`) среди k мест выдачи; пустые места
    нерелевантны."""
    return sum(1 for r in ranked[:k] if r >= relevant) / k


def _dcg(grades: Sequence[int]) -> float:
    return sum((2.0**r - 1) / math.log2(i + 2) for i, r in enumerate(grades))


def ndcg_at(ranked: Sequence[int], pool: Sequence[int], k: int) -> float:
    """nDCG@k: DCG первых k мест выдачи на DCG идеального порядка всего пула; без релевантных в
    пуле — nan."""
    ideal = _dcg(sorted(pool, reverse=True)[:k])
    return _dcg(ranked[:k]) / ideal if ideal else math.nan
