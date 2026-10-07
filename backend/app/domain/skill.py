"""Уровень навыка: наблюдения, априорное и оценка уровня с погрешностью (mechanics.md, §3–4).

Здесь то, что не зависит от выбранной модели навыка; сама модель — за портом
`app.usecase.interface.SkillModel`, сейчас IRT 2PL в `app/skills/irt.py`.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, Self


@dataclass(frozen=True)
class Observation:
    """Ответ на задание (или иное наблюдение) по теме; `weight` — вес уровня доверия."""

    topic: str
    correct: bool
    discrimination: float
    difficulty: float
    weight: float = 1.0


@dataclass(frozen=True)
class Normal:
    mean: float
    sd: float

    def prob_at_least(self, threshold: float) -> float:
        """P(θ ≥ порог); для общего уровня и порога грейда — правило уверенности (§4)."""
        return normal_cdf((self.mean - threshold) / self.sd)


@dataclass(frozen=True)
class Prior:
    """Априорное: θ_s ~ N(mean, theta_sd²), δ_t ~ N(0, deviation_sd²); веса тем w_t, Σ w_t = 1.

    `sd_inflation` — поправка погрешности κ (§3): оценка сообщает погрешность κ σ модели.
    """

    topics: tuple[str, ...]
    weights: tuple[float, ...]
    theta_sd: float
    deviation_sd: float
    mean: float = 0.0
    sd_inflation: float = 1.0

    @classmethod
    def equal_weights(
        cls,
        topics: Sequence[str],
        *,
        theta_sd: float,
        deviation_sd: float,
        mean: float = 0.0,
        sd_inflation: float = 1.0,
    ) -> Self:
        weights = tuple(1.0 / len(topics) for _ in topics)
        return cls(tuple(topics), weights, theta_sd, deviation_sd, mean, sd_inflation)


class SkillEstimate(Protocol):
    """Оценка уровня: по каждой теме и общий уровень θ̄ — с погрешностью."""

    @property
    def topics(self) -> tuple[str, ...]: ...

    def topic(self, topic: str) -> Normal: ...

    def overall(self) -> Normal: ...


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
