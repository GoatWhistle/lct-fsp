"""Защита теста (mechanics.md, §8): детектор дрейфа семейства, модель времени ответа, правило
подозрительного результата и проверочный блок — сравнение и выбор заданий.

Всё — чистые функции без БД; числа конфига приходят аргументами. Детектор дрейфа ведёт порт
`DriftDetector` после фиксации ответа, флаги времени, подозрение и проверочный блок — путь
кандидата (`app.usecase.attempt`).
"""

import enum
import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.adaptive import Option
from app.domain.calibration import Parameters, expected_correct
from app.domain.skill import Normal, SkillEstimate, sigmoid

# MAD нормального распределения — 0,6745 σ: множитель приводит MAD к σ.
_MAD_TO_SD = 1.4826
# Разброс ln T, ниже которого модель времени не опускается: одинаковые времена дали бы σ = 0, и
# любой ответ на секунду быстрее стал бы аномальным.
_MIN_LOG_SPREAD = 0.05


def cusum_step(
    cusum: float, reference: Parameters, level: Normal, correct: bool, *, shift: float
) -> float:
    """Шаг risk-adjusted Bernoulli CUSUM (Steiner и др., 2000): S ← max(0, S + W).

    W — логарифм отношения правдоподобий ответа при семействе, ставшем легче на `shift`, и при
    опорных параметрах; `level` — оценка кандидата по теме до ответа. Поправка на уровень
    встроена: верный ответ сильного кандидата почти ничего не прибавляет. Вероятность — с учётом
    погрешности оценки, как в шаге Эло (§7): в начале теста оценка неточна, и без поправки верные
    ответы сильных кандидатов на трудные задания выглядели бы неожиданными.
    """
    p0 = expected_correct(reference, level)
    p1 = expected_correct(reference, Normal(level.mean + shift, level.sd))
    w = math.log(p1 / p0) if correct else math.log((1 - p1) / (1 - p0))
    return max(0.0, cusum + w)


@dataclass(frozen=True)
class ResponseTimes:
    """Логнормальная модель времени верного ответа на семейство: ln T ~ N(center, spread²),
    оценка робастная — медиана и MAD (van der Linden, 2006)."""

    center: float
    spread: float

    @classmethod
    def fit(cls, seconds: Sequence[float], min_responses: int) -> "ResponseTimes | None":
        """Модель по временам верных ответов; меньше `min_responses` — модели нет."""
        if len(seconds) < min_responses or not seconds:
            return None
        logs = [math.log(max(s, 1e-3)) for s in seconds]
        center = statistics.median(logs)
        mad = statistics.median(abs(v - center) for v in logs)
        return cls(center, max(_MAD_TO_SD * mad, _MIN_LOG_SPREAD))

    def z(self, seconds: float) -> float:
        return (math.log(max(seconds, 1e-3)) - self.center) / self.spread


def time_flag(
    p: float,
    correct: bool,
    seconds: float,
    model: ResponseTimes | None,
    *,
    hard_p: float,
    fast_z: float,
) -> bool:
    """Флаг предъявления: верный ответ на трудное для кандидата задание — P(верно) по оценке до
    ответа не выше `hard_p` — аномально быстро, z логарифма времени не выше −`fast_z`. Без модели
    времени семейства флага нет."""
    if not correct or model is None or p > hard_p:
        return False
    return model.z(seconds) <= -fast_z


class SuspicionReason(enum.StrEnum):
    """Почему результат подозрительный — сигналы правила §8."""

    # Флагов времени не меньше `rt_flags_for_verification`.
    fast_answers = "fast_answers"
    # Событий вставки и потери фокуса не меньше `focus_events_for_verification`.
    focus_events = "focus_events"


@dataclass(frozen=True)
class AttemptSignals:
    """Сигналы попытки: флаги времени и события вставки и фокуса; `focus_events` None — кандидат
    не дал согласия, событий нет."""

    time_flags: int
    focus_events: int | None


@dataclass(frozen=True)
class SuspicionRule:
    """Пороги сигналов подозрительного результата."""

    time_flags: int
    focus_events: int


def suspicion(signals: AttemptSignals, rule: SuspicionRule) -> tuple[SuspicionReason, ...]:
    """Сработавшие сигналы; пусто — результат не подозрительный. Повышает ли попытка
    категорию, решает вызывающий: попытку без повышения не проверяют."""
    reasons = []
    if signals.time_flags >= rule.time_flags:
        reasons.append(SuspicionReason.fast_answers)
    if signals.focus_events is not None and signals.focus_events >= rule.focus_events:
        reasons.append(SuspicionReason.focus_events)
    return tuple(reasons)


@dataclass(frozen=True)
class Expectation:
    """Ожидаемое по основной оценке число верных в проверочном блоке и его дисперсия."""

    expected: float
    variance: float
    items: int


def verification_expectation(
    estimate: SkillEstimate,
    items: Sequence[tuple[str, float, float]],
    *,
    unshown: int,
    target_p: float,
) -> Expectation:
    """E = Σ p_i, V = Σ p_i (1 − p_i) плюс вклад погрешности основной оценки (дельта-метод).

    `items` — показанные задания блока: тема, a, b; p_i — по основной оценке темы. ∂E/∂θ_t =
    Σ_{i ∈ t} a_i p_i (1 − p_i), вклад — gᵀ C g по ковариации уровней тем. Задания, которые не
    успели показать до срока, — неверные ответы на задания с P = `target_p`: блок подбирает
    сложность под неё.
    """
    expected = variance = 0.0
    gradient: dict[str, float] = {}
    for topic, a, b in items:
        p = sigmoid(a * (estimate.topic(topic).mean - b))
        expected += p
        variance += p * (1 - p)
        gradient[topic] = gradient.get(topic, 0.0) + a * p * (1 - p)
    variance += sum(
        gradient[t] * gradient[u] * estimate.covariance(t, u) for t in gradient for u in gradient
    )
    expected += unshown * target_p
    variance += unshown * target_p * (1 - target_p)
    return Expectation(expected, variance, len(items) + unshown)


@dataclass(frozen=True)
class Verdict:
    """Итог проверочного блока: верных из заданий, ожидалось и z."""

    correct: int
    items: int
    expected: float
    z: float
    confirmed: bool


def verification_verdict(correct: int, expectation: Expectation, *, mismatch_z: float) -> Verdict:
    """z = (X − E) / √V; совпал, если z ≥ −`mismatch_z`. Сравнение через ожидаемое число
    верных, а не через оценку короткого блока: она стянута к априорному и занижала бы сильных."""
    z = (correct - expectation.expected) / math.sqrt(max(expectation.variance, 1e-9))
    return Verdict(correct, expectation.items, expectation.expected, z, z >= -mismatch_z)


def verification_choice(
    options: Sequence[Option],
    levels: Mapping[str, float],
    counts: Mapping[str, int],
    *,
    topics: Sequence[str],
    target_p: float,
    top_k: int,
    rng: random.Random,
) -> str | None:
    """Семейство следующего задания проверочного блока; None — спрашивать нечего.

    Тема — среди тем попытки: сначала те, где есть невиданные кандидатом семейства, из них —
    с наименьшим числом заданий блока, при равенстве — по порядку тем. В теме — невиданные, а
    если их нет — виденные давнее всех; из них случайно одно из `top_k` с P(верно) по основной
    оценке ближе всего к `target_p`. `options` — семейства в выдаче без показанных в блоке.
    """
    by_topic: dict[str, list[Option]] = {}
    for o in options:
        if o.topic in topics:
            by_topic.setdefault(o.topic, []).append(o)
    if not by_topic:
        return None
    order = {t: i for i, t in enumerate(topics)}

    def fresh(topic: str) -> bool:
        return any(o.seen_at is None for o in by_topic[topic])

    topic = min(by_topic, key=lambda t: (not fresh(t), counts.get(t, 0), order[t]))
    pool = by_topic[topic]
    unseen = [o for o in pool if o.seen_at is None]
    if unseen:
        pool = unseen
    else:
        oldest = min(o.seen_at for o in pool if o.seen_at is not None)
        pool = [o for o in pool if o.seen_at == oldest]
    level = levels[topic]
    ranked = sorted(
        pool,
        key=lambda o: (abs(sigmoid(o.discrimination * (level - o.difficulty)) - target_p), o.code),
    )
    return rng.choice(ranked[: max(1, top_k)]).code
