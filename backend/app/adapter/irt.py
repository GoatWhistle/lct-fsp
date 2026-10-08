"""Модель навыка — IRT 2PL с иерархическим априорным (docs/mechanics.md, §3–4).

Уровень по теме — общая часть плюс отклонение темы: θ_t = θ_s + δ_t. Совместное апостериорное
(θ_s, δ_1, …, δ_T) приближается нормальным N(μ, Σ); наблюдения учитываются по порядку, каждое —
шагом Ньютона к моде; в профиле навыков шаг повторяется до сходимости моды (§3, §11). Погрешность
уровня — σ модели с поправкой κ. Всё здесь — чистые функции: без БД и состояния, детерминированы.

Модуль целиком — реализация порта `app.usecase.interface.SkillModel` (`initial`, `estimate`).
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.skill import Normal, Observation, Prior, sigmoid

__all__ = ["Estimate", "estimate", "initial", "sigmoid", "update"]

# Сходимость моды по наблюдению: шаг по проекции на hᵀ меньше допуска, θ. Итераций — с запасом:
# одномерный Ньютон по выпуклой функции сходится за 3–6 шагов.
_MODE_TOLERANCE = 1e-10
_MODE_MAX_ITERATIONS = 50


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


def update(est: Estimate, obs: Observation, *, to_mode: bool = False) -> Estimate:
    """Шаг по наблюдению (§3): Σ' = Σ − wI Σhhᵀ Σ / (1 + wI hᵀΣh), μ' = μ + τ Σh.

    Мода апостериорного лежит на прямой μ + τ Σh, поэтому шаг Ньютона — одномерный по τ: мода —
    корень g(τ) = τ − w a (u − p(τ)), g'(τ) = 1 + wI(τ) hᵀΣh. Один шаг из τ = 0 — оценка теста;
    `to_mode` — шаги до сходимости моды, I — в ней.
    """
    j = est._index(obs.topic)
    a, w = obs.discrimination, obs.weight
    sigma_h = [row[0] + row[j] for row in est.cov]
    h_sigma_h = sigma_h[0] + sigma_h[j]
    projection = est.mean[0] + est.mean[j]

    def information(tau: float) -> tuple[float, float]:
        p = sigmoid(a * (projection + tau * h_sigma_h - obs.difficulty))
        return p, w * a * a * p * (1 - p)

    tau = 0.0
    p, wi = information(tau)
    for _ in range(_MODE_MAX_ITERATIONS if to_mode else 1):
        step = (w * a * (float(obs.correct) - p) - tau) / (1 + wi * h_sigma_h)
        tau += step
        p, wi = information(tau)
        if abs(step) * h_sigma_h < _MODE_TOLERANCE:
            break
    if not to_mode:
        # Один шаг: Σ' — по информации в исходной оценке, как в оценке теста.
        _, wi = information(0.0)
    k = wi / (1 + wi * h_sigma_h)
    cov = tuple(
        tuple(cik - k * si * sk for cik, sk in zip(row, sigma_h, strict=True))
        for row, si in zip(est.cov, sigma_h, strict=True)
    )
    mean = tuple(m + tau * s for m, s in zip(est.mean, sigma_h, strict=True))
    return Estimate(est.topics, est.weights, mean, cov, est.sd_inflation)


def estimate(
    prior: Prior, observations: Iterable[Observation], *, to_mode: bool = False
) -> Estimate:
    """(априорное, упорядоченные наблюдения) → (μ, Σ); `to_mode` — каждое наблюдение до
    сходимости моды, как в профиле навыков."""
    est = initial(prior)
    for obs in observations:
        est = update(est, obs, to_mode=to_mode)
    return est
