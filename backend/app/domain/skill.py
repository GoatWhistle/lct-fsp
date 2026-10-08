"""Уровень навыка: наблюдения, априорное, оценка уровня с погрешностью и уровень словами
(mechanics.md, §3–4).

Здесь то, что не зависит от выбранной модели навыка; сама модель — за портом
`app.usecase.interface.SkillModel`, сейчас IRT 2PL в `app/adapter/irt.py`.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, Self

# Год свежести (§11) — юлианский: високосные годы не дают скачков.
YEAR = timedelta(days=365.25)


@dataclass(frozen=True)
class Observation:
    """Ответ на задание (или иное наблюдение) по теме; `weight` — вес уровня доверия, `at` —
    момент наблюдения. Без момента — только там, где уровень не затухает: в оценке теста."""

    topic: str
    correct: bool
    discrimination: float
    difficulty: float
    weight: float = 1.0
    at: datetime | None = None


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
    `decay_sd_per_year` — свежесть (§11): без сигналов дисперсия сообщаемого уровня каждой темы и
    общего уровня растёт на его квадрат за год, но не выше априорной; 0 — уровень не затухает.
    """

    topics: tuple[str, ...]
    weights: tuple[float, ...]
    theta_sd: float
    deviation_sd: float
    mean: float = 0.0
    sd_inflation: float = 1.0
    decay_sd_per_year: float = 0.0

    def topic_variance(self) -> float:
        """Априорная дисперсия сообщаемого уровня темы: κ² (s_θ² + s_δ²)."""
        return self.sd_inflation**2 * (self.theta_sd**2 + self.deviation_sd**2)

    def overall_variance(self) -> float:
        """Априорная дисперсия сообщаемого общего уровня: κ² (s_θ² + s_δ² Σ w_t²)."""
        spread = self.deviation_sd**2 * sum(w * w for w in self.weights)
        return self.sd_inflation**2 * (self.theta_sd**2 + spread)

    def decay_variance(self, elapsed: timedelta) -> float:
        """Прирост дисперсии сообщаемого уровня за `elapsed` без сигналов; назад время не идёт."""
        years = max(elapsed, timedelta(0)) / YEAR
        return self.decay_sd_per_year**2 * years

    @classmethod
    def equal_weights(
        cls,
        topics: Sequence[str],
        *,
        theta_sd: float,
        deviation_sd: float,
        mean: float = 0.0,
        sd_inflation: float = 1.0,
        decay_sd_per_year: float = 0.0,
    ) -> Self:
        weights = tuple(1.0 / len(topics) for _ in topics)
        return cls(
            tuple(topics), weights, theta_sd, deviation_sd, mean, sd_inflation, decay_sd_per_year
        )


class SkillEstimate(Protocol):
    """Оценка уровня: по каждой теме и общий уровень θ̄ — с погрешностью."""

    @property
    def topics(self) -> tuple[str, ...]: ...

    def topic(self, topic: str) -> Normal: ...

    def overall(self) -> Normal: ...


@dataclass(frozen=True)
class SkillProfileLevels:
    """Профиль навыков по специализации (§11): общий уровень, уровни тем, число наблюдений и
    момент последнего сигнала — `None`, пока сигналов нет. Уровни — на момент последнего
    сигнала; к «сейчас» их доводит модель навыка (`SkillModel.advance`).

    `regular_task_topics` — темы, по которым в профиль вошли ответы на регулярные задания: в
    объяснении подборки это источник уверенности «подтверждено регулярным заданием».
    """

    overall: Normal
    topics: Mapping[str, Normal]
    observations: int
    last_signal_at: datetime | None
    regular_task_topics: frozenset[str] = frozenset()


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True)
class LevelBand:
    """Уровень словами (§4): «уверенно middle» — low == high, «между junior и middle» — соседние.

    `None` — полоса ниже порога младшего грейда.
    """

    low: str | None
    high: str | None

    @property
    def confident(self) -> bool:
        return self.low == self.high


def level_band(level: Normal, thresholds: Mapping[str, float], confidence: float) -> LevelBand:
    """Полосы грейдов π_g = P(c_g ≤ θ < c_{g+1}); уверенно — при π_g ≥ γ, иначе пара соседних
    полос с наибольшей суммой."""
    ordered = sorted(thresholds.items(), key=lambda item: item[1])
    grades: list[str | None] = [None, *(grade for grade, _ in ordered)]
    tails = [1.0, *(level.prob_at_least(c) for _, c in ordered), 0.0]
    bands = [tails[i] - tails[i + 1] for i in range(len(grades))]

    best = max(range(len(bands)), key=lambda i: bands[i])
    if bands[best] >= confidence:
        return LevelBand(grades[best], grades[best])
    pair = max(range(len(bands) - 1), key=lambda i: bands[i] + bands[i + 1])
    return LevelBand(grades[pair], grades[pair + 1])
