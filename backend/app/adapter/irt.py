"""Модель навыка — IRT 2PL с иерархическим априорным (docs/mechanics.md, §3–4).

Уровень по теме — общая часть плюс отклонение темы: θ_t = θ_s + δ_t. Совместное апостериорное
(θ_s, δ_1, …, δ_T) приближается нормальным N(μ, Σ); наблюдения учитываются по порядку, каждое —
шагом Ньютона к моде; в профиле навыков шаг повторяется до сходимости моды (§3, §11). Погрешность
уровня — σ модели с поправкой κ. Между наблюдениями к Σ добавляется шум свежести по общей части
уровня (§11). Всё здесь — чистые функции: без БД и состояния, детерминированы.

Модуль целиком — реализация порта `app.usecase.interface.SkillModel` (`initial`, `estimate`,
`advance`); `begin` / `step` / `result` — та же оценка по одному наблюдению, для кэша префиксов
`app.adapter.skill_cache`.
"""

import dataclasses
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.skill import Normal, Observation, Prior, SkillProfileLevels, sigmoid

__all__ = [
    "Estimate",
    "Progress",
    "advance",
    "begin",
    "diffuse",
    "estimate",
    "initial",
    "result",
    "sigmoid",
    "step",
    "update",
]

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

    def covariance(self, topic: str, other: str) -> float:
        """Ковариация уровней двух тем с поправкой погрешности: κ² h_tᵀ Σ h_u."""
        j, k = self._index(topic), self._index(other)
        c = self.cov
        return self.sd_inflation**2 * (c[0][0] + c[0][k] + c[j][0] + c[j][k])

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


def decay_step(prior: Prior, elapsed: timedelta, variances: Iterable[float]) -> float:
    """Прирост дисперсии сообщаемых уровней за `elapsed` (§11, «Свежесть»).

    Шум Q Δt идёт в общую часть θ_s: дисперсия уровня каждой темы и общего уровня растёт на одно
    и то же q. Чтобы ни одна из них не стала выше априорной, q не больше наименьшего зазора до
    априорной; `variances` — текущие сообщаемые дисперсии: темы, затем общий уровень.
    """
    q = prior.decay_variance(elapsed)
    if q <= 0.0:
        return 0.0
    *topics, overall = variances
    gaps = [prior.topic_variance() - v for v in topics] + [prior.overall_variance() - overall]
    return max(0.0, min(q, *gaps))


def diffuse(est: Estimate, prior: Prior, elapsed: timedelta) -> Estimate:
    """Σ + Q Δt: время без сигналов расширяет оценку по общей части уровня, среднее не меняется."""
    reported = [est.topic(t).sd ** 2 for t in est.topics] + [est.overall().sd ** 2]
    q = decay_step(prior, elapsed, reported) / est.sd_inflation**2
    if q == 0.0:
        return est
    cov = [list(row) for row in est.cov]
    cov[0][0] += q
    return dataclasses.replace(est, cov=tuple(tuple(row) for row in cov))


@dataclass(frozen=True)
class Progress:
    """Оценка по префиксу наблюдений и момент последнего из них: от него до следующего наблюдения
    считается затухание. Без затухания в априорном момент не нужен и остаётся `None`."""

    estimate: Estimate
    last: datetime | None = None


def begin(prior: Prior) -> Progress:
    return Progress(initial(prior))


def step(prior: Prior, progress: Progress, obs: Observation, *, to_mode: bool = False) -> Progress:
    """Следующее наблюдение префикса: затухание с прошлого наблюдения, затем шаг `update`."""
    est, last = progress.estimate, progress.last
    if prior.decay_sd_per_year > 0.0:
        if obs.at is None:
            raise ValueError("уровень затухает — у наблюдения нужен момент")
        if last is not None:
            est = diffuse(est, prior, obs.at - last)
        last = obs.at
    return Progress(update(est, obs, to_mode=to_mode), last)


def result(progress: Progress) -> Estimate:
    return progress.estimate


def estimate(
    prior: Prior, observations: Iterable[Observation], *, to_mode: bool = False
) -> Estimate:
    """(априорное, упорядоченные наблюдения) → (μ, Σ) на момент последнего наблюдения; `to_mode` —
    каждое наблюдение до сходимости моды, как в профиле навыков. С затуханием в априорном каждому
    наблюдению нужен момент `at`."""
    progress = begin(prior)
    for obs in observations:
        progress = step(prior, progress, obs, to_mode=to_mode)
    return progress.estimate


def advance(prior: Prior, levels: SkillProfileLevels, now: datetime) -> SkillProfileLevels:
    """Сохранённый профиль — на момент последнего сигнала — доводится до `now`: тот же шум, что
    в `diffuse`, по сохранённым уровням. Темы, которых нет в априорном, не затухают."""
    if levels.last_signal_at is None:
        return levels
    topics = {t: n for t, n in levels.topics.items() if t in prior.topics}
    reported = [n.sd**2 for n in topics.values()] + [levels.overall.sd**2]
    q = decay_step(prior, now - levels.last_signal_at, reported)
    if q == 0.0:
        return levels

    def widened(level: Normal) -> Normal:
        return Normal(level.mean, math.sqrt(level.sd**2 + q))

    return dataclasses.replace(
        levels,
        overall=widened(levels.overall),
        topics={t: widened(n) if t in topics else n for t, n in levels.topics.items()},
    )
