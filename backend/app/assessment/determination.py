"""Определение категории по оценке теста — правило уверенности и каскад вниз (mechanics.md, §4).

Чистые функции: решение зависит только от общего уровня θ̄ по оценке теста, грейда попытки и
того, есть ли что спросить в дотесте.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.skills.irt import Normal


@dataclass(frozen=True)
class Assign:
    """Категория присвоена с этим грейдом."""

    grade: str


@dataclass(frozen=True)
class Offer:
    """Уверенности не хватило — предлагается дотест на этот грейд."""

    grade: str


@dataclass(frozen=True)
class NoCategory:
    """Не хватило уверенности и для младшего грейда."""


Decision = Assign | Offer | NoCategory


def grades_by_threshold(thresholds: Mapping[str, float]) -> list[str]:
    """Грейды от младшего к старшему — по порогам c_g."""
    return sorted(thresholds, key=lambda grade: thresholds[grade])


def grade_probabilities(overall: Normal, thresholds: Mapping[str, float]) -> dict[str, float]:
    """P(θ̄ ≥ c_g) для каждого грейда — от младшего к старшему."""
    return {g: overall.prob_at_least(thresholds[g]) for g in grades_by_threshold(thresholds)}


def decide(
    overall: Normal,
    grade: str,
    *,
    thresholds: Mapping[str, float],
    confidence: float,
    has_items: Callable[[str], bool],
) -> Decision:
    """Итог попытки на `grade`.

    Правило выполнено — грейд присвоен. Иначе вниз по грейдам: если уверенность для грейда ниже
    уже набрана, он присваивается без дотеста; если для него есть что спросить — предлагается
    дотест. Дотест, в котором спрашивать нечего, оценку не меняет — его провал известен сразу,
    и каскад идёт дальше. Ниже младшего грейда — без категории.
    """
    probabilities = grade_probabilities(overall, thresholds)
    if probabilities[grade] >= confidence:
        return Assign(grade)
    order = grades_by_threshold(thresholds)
    for lower in reversed(order[: order.index(grade)]):
        if probabilities[lower] >= confidence:
            return Assign(lower)
        if has_items(lower):
            return Offer(lower)
    return NoCategory()


def grade_up_hint(
    overall: Normal, grade: str, *, thresholds: Mapping[str, float], confidence: float
) -> str | None:
    """Грейд выше присвоенного, если P(θ̄ ≥ c_{g+1}) не ниже порога подсказки."""
    order = grades_by_threshold(thresholds)
    level = order.index(grade)
    if level + 1 == len(order):
        return None
    higher = order[level + 1]
    return higher if overall.prob_at_least(thresholds[higher]) >= confidence else None
