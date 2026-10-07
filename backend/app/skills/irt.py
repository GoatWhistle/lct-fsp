"""Модель навыка — IRT 2PL с иерархическим априорным (docs/mechanics.md, §3–4).

Уровень по теме — общая часть плюс отклонение темы: θ_t = θ_s + δ_t. Совместное апостериорное
(θ_s, δ_1, …, δ_T) приближается нормальным N(μ, Σ); наблюдения учитываются по порядку, каждое —
шагом Ньютона к моде. Погрешность уровня — σ модели с поправкой κ. Всё здесь — чистые функции:
без БД и состояния, детерминированы.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Self


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


@dataclass(frozen=True)
class Estimate:
    """N(μ, Σ) по координатам (θ_s, δ_1, …, δ_T) в порядке `topics`.

    Уровни сообщаются с погрешностью κ σ, где σ — из Σ модели, κ — `sd_inflation`. Шаг по
    наблюдению идёт по Σ модели: поправка меняет только сообщаемую погрешность, не среднее.
    """

    topics: tuple[str, ...]
    weights: tuple[float, ...]
    mean: tuple[float, ...]
    cov: tuple[tuple[float, ...], ...]
    sd_inflation: float = 1.0

    def topic(self, topic: str) -> Normal:
        """Уровень по теме: θ_t ~ N(hᵀμ, κ² hᵀΣh), h = e_s + e_t."""
        j = self._index(topic)
        mean = self.mean[0] + self.mean[j]
        var = self.cov[0][0] + 2 * self.cov[0][j] + self.cov[j][j]
        return Normal(mean, self.sd_inflation * math.sqrt(var))

    def overall(self) -> Normal:
        """Общий уровень θ̄ = Σ w_t θ_t ~ N(gᵀμ, κ² gᵀΣg), g = e_s + Σ w_t e_t."""
        g = (1.0, *self.weights)
        mean = sum(gi * mi for gi, mi in zip(g, self.mean, strict=True))
        var = sum(g[i] * g[k] * self.cov[i][k] for i in range(len(g)) for k in range(len(g)))
        return Normal(mean, self.sd_inflation * math.sqrt(var))

    def _index(self, topic: str) -> int:
        return self.topics.index(topic) + 1


def initial(prior: Prior) -> Estimate:
    n = len(prior.topics) + 1
    variances = [prior.theta_sd**2] + [prior.deviation_sd**2] * (n - 1)
    cov = tuple(tuple(variances[i] if i == k else 0.0 for k in range(n)) for i in range(n))
    mean = (prior.mean,) + (0.0,) * (n - 1)
    return Estimate(prior.topics, prior.weights, mean, cov, prior.sd_inflation)


def update(est: Estimate, obs: Observation) -> Estimate:
    """Шаг по наблюдению (§3): Σ' = Σ − wI Σhhᵀ Σ / (1 + wI hᵀΣh), μ' = μ + w a (u − p) Σ'h."""
    j = est._index(obs.topic)
    a, w = obs.discrimination, obs.weight
    sigma_h = [row[0] + row[j] for row in est.cov]
    h_sigma_h = sigma_h[0] + sigma_h[j]
    p = sigmoid(a * (est.mean[0] + est.mean[j] - obs.difficulty))
    wi = w * a * a * p * (1 - p)
    k = wi / (1 + wi * h_sigma_h)
    cov = tuple(
        tuple(cik - k * si * sk for cik, sk in zip(row, sigma_h, strict=True))
        for row, si in zip(est.cov, sigma_h, strict=True)
    )
    step = w * a * (float(obs.correct) - p) / (1 + wi * h_sigma_h)
    mean = tuple(m + step * s for m, s in zip(est.mean, sigma_h, strict=True))
    return Estimate(est.topics, est.weights, mean, cov, est.sd_inflation)


def estimate(prior: Prior, observations: Iterable[Observation]) -> Estimate:
    """(априорное, упорядоченные наблюдения) → (μ, Σ)."""
    est = initial(prior)
    for obs in observations:
        est = update(est, obs)
    return est


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


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
