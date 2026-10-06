"""Калибровка параметров семейств (mechanics.md, §7): старт с экспертных, Эло после каждого
ответа, пакетная переоценка (a, b) при накоплении ответов, связка шкалы по якорям.

Шкала Эло здесь — сразу логиты θ, поэтому сложность Эло и есть сложность b модели 2PL. Всё —
чистые функции без БД.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.config import Mechanics
from app.skills.irt import Normal, Observation, Prior, estimate, sigmoid


@dataclass(frozen=True)
class Parameters:
    discrimination: float
    difficulty: float


@dataclass(frozen=True)
class Response:
    """Ответ на семейство: уровень кандидата по теме и верность. Калибровка получает уровень
    уже переведённым связкой шкалы (`Link.apply`)."""

    level: Normal
    correct: bool


@dataclass(frozen=True)
class Link:
    """Связка шкалы: уровень кандидата, с которым калибровка сравнивает ответ, — θ ≈ α + β μ с
    погрешностью √β σ, где (μ, σ) — оценка теста по теме.

    Оценка теста стягивается к априорному среднему; если априорное уже популяции, среднее
    пережато в β раз, и дисперсия тоже. Без связки калибровка принимает пережатые уровни за
    точные: сложности сжимаются к центру, разделяющая сила завышается, и следующий тест на таких
    параметрах пережимает уровни сильнее.
    """

    shift: float = 0.0
    scale: float = 1.0

    def apply(self, level: Normal) -> Normal:
        return Normal(self.shift + self.scale * level.mean, math.sqrt(self.scale) * level.sd)


def expert(grade: str, mechanics: Mechanics) -> Parameters:
    """Стартовые параметры семейства по грейду эксперта: середина полосы и общая a₀ (§2)."""
    return Parameters(mechanics.expert_discrimination, mechanics.expert_difficulty_by_grade[grade])


def expected_correct(params: Parameters, level: Normal) -> float:
    """P(верно) при неточной оценке уровня: σ(a(μ − b) / √(1 + π a² σ² / 8)), как в Глико."""
    a = params.discrimination
    spread = math.sqrt(1 + math.pi * a**2 * level.sd**2 / 8)
    return sigmoid(a * (level.mean - params.difficulty) / spread)


def elo_step(responses: int, mechanics: Mechanics) -> float:
    """K_n = max(K_min, K₀ · n₀ / (n₀ + n)): шаг падает вдвое за n₀ ответов."""
    half = mechanics.elo_k_half_responses
    return max(mechanics.elo_k_min, mechanics.elo_k_initial * half / (half + responses))


def elo_update(
    params: Parameters, response: Response, responses: int, mechanics: Mechanics
) -> Parameters:
    """b ← b − K_n (u − p). Разделяющая сила онлайн не обновляется: слишком шумно.

    `responses` — ответов на семейство до этого. Ответ кандидата с неточной оценкой двигает
    сложность меньше: p ближе к ½, и неожиданность ответа весит меньше.
    """
    p = expected_correct(params, response.level)
    step = elo_step(responses, mechanics) * (float(response.correct) - p)
    return Parameters(params.discrimination, params.difficulty - step)


def refit(
    responses: Sequence[Response], start: Parameters, mechanics: Mechanics, *, iterations: int = 50
) -> Parameters:
    """Пакетная переоценка (a, b): логистическая регрессия ответов на итоговые оценки кандидатов
    со штрафом к экспертным значениям `start`.

    Максимум апостериорной плотности: правдоподобие с поправкой на погрешность оценок кандидатов
    (та же, что в Эло) плюс нормальный штраф на b и на ln a. Метод — скоринг Фишера по (b, ln a).
    """
    sd_b = mechanics.calibration_refit_difficulty_prior_sd
    sd_log_a = mechanics.calibration_refit_log_discrimination_prior_sd
    b0, log_a0 = start.difficulty, math.log(start.discrimination)
    b, log_a = b0, log_a0
    for _ in range(iterations):
        a = math.exp(log_a)
        grad_b = -(b - b0) / sd_b**2
        grad_l = -(log_a - log_a0) / sd_log_a**2
        h_bb, h_bl, h_ll = 1 / sd_b**2, 0.0, 1 / sd_log_a**2
        for r in responses:
            # z = a c (μ − b), c = (1 + κ a²)^(−½), κ = π σ² / 8:
            # ∂z/∂b = −a c, ∂z/∂ln a = a c³ (μ − b).
            c = 1 / math.sqrt(1 + math.pi * a**2 * r.level.sd**2 / 8)
            gap = r.level.mean - b
            p = sigmoid(a * c * gap)
            d_b, d_l = -a * c, a * c**3 * gap
            residual = float(r.correct) - p
            grad_b += residual * d_b
            grad_l += residual * d_l
            info = p * (1 - p)
            h_bb += info * d_b * d_b
            h_bl += info * d_b * d_l
            h_ll += info * d_l * d_l
        det = h_bb * h_ll - h_bl**2
        step_b = (h_ll * grad_b - h_bl * grad_l) / det
        step_l = (h_bb * grad_l - h_bl * grad_b) / det
        # Шаг по ln a ограничен: на первых итерациях скоринг может перескочить.
        step_l = max(-0.5, min(0.5, step_l))
        b, log_a = b + step_b, log_a + step_l
        if abs(step_b) < 1e-7 and abs(step_l) < 1e-7:
            break
    return Parameters(math.exp(log_a), b)


def fit_link(
    anchors: Sequence[tuple[Parameters, Response]],
    mechanics: Mechanics,
    *,
    iterations: int = 50,
) -> Link:
    """Связка шкалы по ответам на якорные семейства: их параметры заморожены и известны, поэтому
    по ним видно, как оценки теста соотносятся со шкалой. Так якоря держат начало (α) и масштаб
    (β) шкалы.

    Максимум правдоподобия P(верно) = σ(a c (α + β μ − b)), c = (1 + π a² β σ² / 8)^(−½), по
    (α, β) скорингом Фишера. Пока ответов на якоря меньше `calibration_refit_min_responses` —
    тождественная связка: двух параметров по нескольким ответам не оценить.
    """
    if len(anchors) < mechanics.calibration_refit_min_responses:
        return Link()
    shift, scale = 0.0, 1.0
    for _ in range(iterations):
        grad_s = grad_k = h_ss = h_sk = h_kk = 0.0
        for params, r in anchors:
            # z = a c gap, gap = α + β μ − b, κ = π a² σ² / 8:
            # ∂z/∂α = a c, ∂z/∂β = a c μ − a gap κ c³ / 2.
            a = params.discrimination
            kappa = math.pi * a**2 * r.level.sd**2 / 8
            c = 1 / math.sqrt(1 + kappa * scale)
            gap = shift + scale * r.level.mean - params.difficulty
            p = sigmoid(a * c * gap)
            d_s = a * c
            d_k = a * c * r.level.mean - a * gap * kappa * c**3 / 2
            residual = float(r.correct) - p
            grad_s += residual * d_s
            grad_k += residual * d_k
            info = p * (1 - p)
            h_ss += info * d_s * d_s
            h_sk += info * d_s * d_k
            h_kk += info * d_k * d_k
        det = h_ss * h_kk - h_sk**2
        if det <= 0:
            return Link()
        step_s = (h_kk * grad_s - h_sk * grad_k) / det
        step_k = (h_ss * grad_k - h_sk * grad_s) / det
        # Шаг по β ограничен: на первых итерациях скоринг может перескочить.
        step_k = max(-0.3, min(0.3, step_k))
        shift, scale = shift + step_s, scale + step_k
        if abs(step_s) < 1e-7 and abs(step_k) < 1e-7:
            break
    # Ответы на якоря не связаны с оценками — связке не на чем стоять.
    return Link(shift, scale) if scale > 0 else Link()


def rest_levels(
    prior: Prior, observations: Sequence[Observation], indices: Iterable[int]
) -> list[Normal]:
    """Итоговая оценка темы для каждого ответа из `indices` — по всем остальным ответам.

    Сам ответ в оценку не входит: иначе верный ответ поднимает оценку, с которой его потом
    сравнивают, и переоценка завышает разделяющую силу.
    """
    return [
        estimate(prior, [o for j, o in enumerate(observations) if j != i]).topic(
            observations[i].topic
        )
        for i in indices
    ]


def needs_review(reference: Parameters, start: Parameters, mechanics: Mechanics) -> bool:
    """Опорная сложность легче экспертной больше чем на `calibration_expert_gap_review`: утечка
    во время разогрева или ошибка эксперта — семейство уходит из выдачи до ручной проверки."""
    return start.difficulty - reference.difficulty > mechanics.calibration_expert_gap_review
