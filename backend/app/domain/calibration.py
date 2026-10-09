"""Калибровка параметров семейств (mechanics.md, §7): старт с экспертных, Эло после каждого
ответа до пакетной переоценки (a, b) при накоплении ответов, связка шкалы по якорям.

Шкала Эло здесь — сразу логиты θ, поэтому сложность Эло и есть сложность b модели 2PL. Всё —
чистые функции без БД; числа конфига приходят аргументами, их передаёт реализация порта
`Calibration` (`app.adapter.calibration`).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.skill import Normal, sigmoid


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


@dataclass
class CalibratedFamily:
    """Состояние калибровки семейства — то, что лежит в репозитории калибровки.

    До первого ответа записи нет: параметры — экспертные из банка. `in_rotation` — семейство не
    снято на ручную проверку: снимает переоценка, когда опорная сложность легче экспертной больше
    допустимого. `drift` — статистика CUSUM детектора дрейфа (§8); превысила порог — семейство
    скомпрометировано с `compromised_at` и тоже выходит из выдачи.
    """

    family_code: str
    discrimination: float
    difficulty: float
    responses: int = 0
    reference: Parameters | None = None
    refitted_at: datetime | None = None
    in_rotation: bool = True
    drift: float = 0.0
    compromised_at: datetime | None = None

    @property
    def parameters(self) -> Parameters:
        return Parameters(self.discrimination, self.difficulty)

    @property
    def is_compromised(self) -> bool:
        return self.compromised_at is not None

    @property
    def issued(self) -> bool:
        """Семейство в выдаче: не снято на проверку и не скомпрометировано."""
        return self.in_rotation and not self.is_compromised


@dataclass(frozen=True)
class AnchorAnswer:
    """Ответ на якорное семейство для связки шкалы: код и параметры якоря, оценка темы до ответа
    и итоговая без ответа — её нет, пока попытка ответа не остановлена."""

    family_code: str
    params: Parameters
    before: Response
    rest: Response | None


def expected_correct(params: Parameters, level: Normal) -> float:
    """P(верно) при неточной оценке уровня: σ(a(μ − b) / √(1 + π a² σ² / 8)), как в Глико."""
    a = params.discrimination
    spread = math.sqrt(1 + math.pi * a**2 * level.sd**2 / 8)
    return sigmoid(a * (level.mean - params.difficulty) / spread)


def elo_step(responses: int, *, k_initial: float, k_half_responses: int, k_min: float) -> float:
    """K_n = max(K_min, K₀ · n₀ / (n₀ + n)): шаг падает вдвое за n₀ ответов."""
    return max(k_min, k_initial * k_half_responses / (k_half_responses + responses))


def elo_update(
    params: Parameters,
    response: Response,
    responses: int,
    *,
    k_initial: float,
    k_half_responses: int,
    k_min: float,
) -> Parameters:
    """b ← b − K_n (u − p). Разделяющая сила онлайн не обновляется: слишком шумно.

    `responses` — ответов на семейство до этого. Ответ кандидата с неточной оценкой двигает
    сложность меньше: p ближе к ½, и неожиданность ответа весит меньше.
    """
    p = expected_correct(params, response.level)
    step = elo_step(
        responses, k_initial=k_initial, k_half_responses=k_half_responses, k_min=k_min
    ) * (float(response.correct) - p)
    return Parameters(params.discrimination, params.difficulty - step)


def refit(
    responses: Sequence[Response],
    start: Parameters,
    *,
    difficulty_prior_sd: float,
    log_discrimination_prior_sd: float,
    ceiling: float = 1.0,
    iterations: int = 50,
) -> Parameters:
    """Пакетная переоценка (a, b): логистическая регрессия ответов на итоговые оценки кандидатов
    со штрафом к экспертным значениям `start`.

    Максимум апостериорной плотности: правдоподобие с поправкой на погрешность оценок кандидатов
    (та же, что в Эло) плюс нормальный штраф на b и на ln a. Метод — скоринг Фишера по (b, ln a).
    `ceiling` — потолок d модели P = d · p(a, b) для проверки согласия (`ceiling_gain`); у
    переоценки он единица.
    """
    sd_b = difficulty_prior_sd
    sd_log_a = log_discrimination_prior_sd
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
            s = sigmoid(a * c * gap)
            p = ceiling * s
            d_b, d_l = -a * c, a * c**3 * gap
            # ∂P/∂z = d s (1 − s); вес ответа — ∂P/∂z / P(1 − P). При d = 1 он ровно единица и
            # не теряет ответ, где сигмоида насытилась до 0 или 1.
            slope = ceiling * s * (1 - s)
            weight = 1.0 if ceiling == 1 else slope / (p * (1 - p)) if 0 < p < 1 else 0.0
            residual = (float(r.correct) - p) * weight
            grad_b += residual * d_b
            grad_l += residual * d_l
            info = slope * weight
            h_bb += info * d_b * d_b
            h_bl += info * d_b * d_l
            h_ll += info * d_l * d_l
        det = h_bb * h_ll - h_bl**2
        step_b = (h_ll * grad_b - h_bl * grad_l) / det
        step_l = (h_bb * grad_l - h_bl * grad_b) / det
        # Шаг по ln a ограничен: на первых итерациях скоринг может перескочить. У модели с
        # потолком — и по b: плоские ответы она объясняет при b → −∞, и шаг туда неограничен.
        step_l = max(-0.5, min(0.5, step_l))
        if ceiling < 1:
            step_b = max(-1.0, min(1.0, step_b))
        b, log_a = b + step_b, log_a + step_l
        if abs(step_b) < 1e-7 and abs(step_l) < 1e-7:
            break
    return Parameters(math.exp(log_a), b)


def log_posterior(
    responses: Sequence[Response],
    start: Parameters,
    params: Parameters,
    *,
    difficulty_prior_sd: float,
    log_discrimination_prior_sd: float,
    ceiling: float = 1.0,
) -> float:
    """Логарифм апостериорной плотности (a, b) модели P = d · p(a, b) с штрафами переоценки, без
    постоянных слагаемых."""
    log_a, log_a0 = math.log(params.discrimination), math.log(start.discrimination)
    total = -((params.difficulty - start.difficulty) ** 2) / (2 * difficulty_prior_sd**2) - (
        log_a - log_a0
    ) ** 2 / (2 * log_discrimination_prior_sd**2)
    for r in responses:
        p = min(max(ceiling * expected_correct(params, r.level), 1e-12), 1 - 1e-12)
        total += math.log(p if r.correct else 1 - p)
    return total


def ceilings(minimum: float, step: float) -> list[float]:
    """Потолки модели, с которой проверка согласия сравнивает 2PL: от `minimum` с шагом `step`,
    ниже единицы — единица и есть сама 2PL."""
    return [round(minimum + i * step, 6) for i in range(round((1 - minimum) / step))]


def ceiling_gain(
    responses: Sequence[Response],
    start: Parameters,
    fitted: Parameters,
    *,
    ceilings: Sequence[float],
    difficulty_prior_sd: float,
    log_discrimination_prior_sd: float,
) -> float:
    """Согласие семейства с 2PL против модели с потолком: насколько лучше ответы объясняет
    P = d · p(a, b) с лучшим d из `ceilings`, чем переоценённая 2PL `fitted`, — разность
    логарифмов апостериорной плотности при тех же штрафах на b и ln a, в натах.

    У модели с потолком та же свобода, что у переоценки, плюс d, поэтому переоценка не может
    спрятать порчу другими (a, b): ответ, не зависящий от уровня, — потолок около ½ при b → −∞
    без штрафа на a, неверный эталон у части экземпляров — потолок ниже единицы. Перевес не
    меньше нуля: d = 1 — сама `fitted`.
    """
    sd_b, sd_log_a = difficulty_prior_sd, log_discrimination_prior_sd

    def posterior(params: Parameters, ceiling: float) -> float:
        return log_posterior(
            responses,
            start,
            params,
            difficulty_prior_sd=sd_b,
            log_discrimination_prior_sd=sd_log_a,
            ceiling=ceiling,
        )

    base = posterior(fitted, 1.0)
    best = max(
        base,
        *(
            posterior(
                refit(
                    responses,
                    start,
                    difficulty_prior_sd=sd_b,
                    log_discrimination_prior_sd=sd_log_a,
                    ceiling=d,
                ),
                d,
            )
            for d in ceilings
        ),
    )
    return best - base


def item_fit_rmsd(responses: Sequence[Response], params: Parameters, *, groups: int) -> float:
    """Согласие семейства с 2PL: RMSD наблюдённой и ожидаемой доли верных по группам равного
    размера по уровню отвечавших, взвешенный числом ответов в группе, за вычетом шума выборки.

    Ответы сортируются по `level.mean` и делятся на `groups` групп, остаток — по одному в первые
    группы. Ожидаемая доля — с поправкой на погрешность уровня, как в шаге Эло. Доля верных в
    группе гуляет и у семейства, которое ведёт себя ровно по модели, — с дисперсией
    Σ p(1 − p) / nₖ²; она вычитается из квадрата расхождения. Без ответов расхождения нет — 0.
    """
    ordered = sorted(responses, key=lambda r: r.level.mean)
    if not ordered:
        return 0.0
    size, extra = divmod(len(ordered), min(groups, len(ordered)))
    total, start = 0.0, 0
    while start < len(ordered):
        end = start + size + (1 if extra > 0 else 0)
        extra -= 1
        group = ordered[start:end]
        expected = [expected_correct(params, r.level) for r in group]
        observed = sum(r.correct for r in group) / len(group)
        gap = observed - sum(expected) / len(group)
        noise = sum(p * (1 - p) for p in expected) / len(group) ** 2
        total += len(group) * (gap**2 - noise)
        start = end
    return math.sqrt(max(0.0, total) / len(ordered))


def fit_link(
    anchors: Sequence[tuple[Parameters, Response]],
    *,
    min_responses: int,
    iterations: int = 50,
) -> Link:
    """Связка шкалы по ответам на якорные семейства: их параметры заморожены и известны, поэтому
    по ним видно, как оценки теста соотносятся со шкалой. Так якоря держат начало (α) и масштаб
    (β) шкалы.

    Максимум правдоподобия P(верно) = σ(a c (α + β μ − b)), c = (1 + π a² β σ² / 8)^(−½), по
    (α, β) скорингом Фишера. Пока ответов на якоря меньше `min_responses` — тождественная связка:
    двух параметров по нескольким ответам не оценить. Тождественная она и тогда, когда скоринг
    уводит β в β ≤ 0, где модели нет.
    """
    if len(anchors) < min_responses:
        return Link()
    shift, scale = 0.0, 1.0
    # Всё, что не зависит от (α, β), считается один раз: a, b, μ, κ и ответ.
    rows = [
        (
            params.discrimination,
            params.difficulty,
            r.level.mean,
            math.pi * params.discrimination**2 * r.level.sd**2 / 8,
            float(r.correct),
        )
        for params, r in anchors
    ]
    for _ in range(iterations):
        grad_s = grad_k = h_ss = h_sk = h_kk = 0.0
        for a, difficulty, mean, kappa, correct in rows:
            # z = a c gap, gap = α + β μ − b, κ = π a² σ² / 8:
            # ∂z/∂α = a c, ∂z/∂β = a c μ − a gap κ c³ / 2.
            c = 1 / math.sqrt(1 + kappa * scale)
            gap = shift + scale * mean - difficulty
            p = sigmoid(a * c * gap)
            d_s = a * c
            d_k = a * c * mean - a * gap * kappa * c**3 / 2
            residual = correct - p
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
        if scale <= 0:
            # Модель есть только при β > 0 (погрешность √β σ). Ответы на якоря не связаны с
            # оценками или противоречат им — связке не на чем стоять.
            return Link()
        if abs(step_s) < 1e-7 and abs(step_k) < 1e-7:
            break
    return Link(shift, scale)


class ExpertGap(StrEnum):
    """Расхождение опорной сложности с экспертной больше `calibration_expert_gap_review`."""

    # Легче экспертной: утечка во время разогрева или ошибка эксперта — семейство уходит из
    # выдачи до ручной проверки.
    EASIER = "easier"
    # Тяжелее экспертной: эксперт недооценил задание или формулировка сбивает. Подыгрыша нет —
    # семейство остаётся в выдаче, пометка идёт в отчёт покрытия банка.
    HARDER = "harder"


def expert_gap(reference: Parameters, start: Parameters, *, gap: float) -> ExpertGap | None:
    """Сверка опорной сложности с экспертной в обе стороны."""
    if start.difficulty - reference.difficulty > gap:
        return ExpertGap.EASIER
    if reference.difficulty - start.difficulty > gap:
        return ExpertGap.HARDER
    return None
