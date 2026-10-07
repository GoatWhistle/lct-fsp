"""Адаптивный тест: выбор следующего семейства и остановка (mechanics.md, §6).

Чистые функции без БД: состояние попытки — счётчики заданий по темам и оценка уровня, банк —
семейства с текущими параметрами, долей показов и давностью показа кандидату. Тот же код
гоняет и сервис, и симуляция на стенде.
"""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self

from app.config import Mechanics
from app.skills.irt import Estimate, Normal, Prior, sigmoid


@dataclass(frozen=True)
class Blueprint:
    """Бланк: веса тем и ограничения покрытия. Для теста на категорию веса — w_t специализации,
    те же, что задают общий уровень."""

    topics: tuple[str, ...]
    weights: tuple[float, ...]
    min_items: int
    max_items: int
    min_per_topic: int
    max_topic_share: float
    stop_sd: float

    @classmethod
    def from_prior(cls, prior: Prior, mechanics: Mechanics) -> Self:
        return cls(
            topics=prior.topics,
            weights=prior.weights,
            min_items=mechanics.test_min_items,
            max_items=mechanics.test_max_items,
            min_per_topic=mechanics.test_min_items_per_topic,
            max_topic_share=mechanics.test_max_topic_share,
            stop_sd=mechanics.test_stop_sd,
        )


@dataclass(frozen=True)
class Option:
    """Семейство, из которого можно взять следующее задание."""

    code: str
    topic: str
    discrimination: float
    difficulty: float
    # Попыток в окне показов по специализации (без текущей), где семейство показано.
    shown: int
    # Начало попытки или блока, где кандидат видел семейство последний раз; None — не видел.
    seen_at: datetime | None = None


@dataclass(frozen=True)
class Exposure:
    """Контроль показов: случайный выбор из `top_k` самых информативных и потолок доли попыток,
    в которых показано семейство."""

    # Попыток по специализации в окне до текущей.
    attempts: int
    max_rate: float
    top_k: int

    @classmethod
    def from_mechanics(cls, attempts: int, mechanics: Mechanics) -> Self:
        return cls(attempts, mechanics.exposure_max_rate, mechanics.exposure_top_k)

    def allows(self, option: Option) -> bool:
        """Показ в текущей попытке оставит долю в окне не выше потолка."""
        return option.shown + 1 <= self.max_rate * (self.attempts + 1) + 1e-9


@dataclass(frozen=True)
class Choice:
    code: str
    # Под потолком показов в теме ничего не осталось — взято наименее показанное семейство.
    capped: bool


def information(discrimination: float, difficulty: float, level: float) -> float:
    """Информация Фишера 2PL при уровне θ: I = a² p (1 − p)."""
    p = sigmoid(discrimination * (level - difficulty))
    return discrimination**2 * p * (1 - p)


def choose(
    blueprint: Blueprint,
    counts: Mapping[str, int],
    estimate: Estimate,
    options: Sequence[Option],
    exposure: Exposure,
    rng: random.Random,
) -> Choice | None:
    """Следующее семейство: тема → кандидаты → информация → случайный выбор из top-k.

    `counts` — заданий по темам в текущей попытке, `estimate` — оценка для выбора заданий,
    `options` — семейства без скомпрометированных и уже показанных в этой попытке. Тема без
    кандидатов уступает следующей; None — спрашивать нечего.
    """
    for topic in _topics_by_priority(blueprint, counts, estimate):
        pool = [o for o in options if o.topic == topic]
        if not pool:
            continue
        unseen = [o for o in pool if o.seen_at is None]
        if unseen:
            pool = unseen
        else:
            # Невиданных не осталось — сначала семейства, виденные давнее всего.
            oldest = min(o.seen_at for o in pool if o.seen_at is not None)
            pool = [o for o in pool if o.seen_at == oldest]

        allowed = [o for o in pool if exposure.allows(o)]
        capped = not allowed
        if capped:
            least = min(o.shown for o in pool)
            allowed = [o for o in pool if o.shown == least]

        level = estimate.topic(topic).mean
        ranked = sorted(
            allowed, key=lambda o: (-information(o.discrimination, o.difficulty, level), o.code)
        )
        picked = rng.choice(ranked[: exposure.top_k])
        return Choice(picked.code, capped)
    return None


def should_stop(blueprint: Blueprint, counts: Mapping[str, int], overall: Normal) -> bool:
    """Погрешность общего уровня не выше порога при выполненных минимумах — или лимит заданий.

    Остановка по точности уравнивает точность, а не длину: сильный и слабый кандидат
    заканчивают с одинаковой погрешностью.
    """
    total = sum(counts.values())
    if total >= blueprint.max_items:
        return True
    covered = all(counts.get(t, 0) >= blueprint.min_per_topic for t in blueprint.topics)
    return covered and total >= blueprint.min_items and overall.sd <= blueprint.stop_sd


def _topics_by_priority(
    blueprint: Blueprint, counts: Mapping[str, int], estimate: Estimate
) -> list[str]:
    """Темы в порядке выбора: недобранные минимумы покрытия, затем темы с запасом до потолка
    доли, затем остальные — внутри групп по вкладу в погрешность общего уровня w_t² σ_t²."""
    total = sum(counts.values())
    weight = dict(zip(blueprint.topics, blueprint.weights, strict=True))

    def group(topic: str) -> int:
        count = counts.get(topic, 0)
        if count < blueprint.min_per_topic:
            return 0
        if count + 1 <= blueprint.max_topic_share * (total + 1) + 1e-9:
            return 1
        return 2

    def contribution(topic: str) -> float:
        return weight[topic] ** 2 * estimate.topic(topic).sd ** 2

    # Тема без запаса до потолка — по возрастанию доли: в неё идут, только если в остальных
    # спрашивать нечего.
    return sorted(
        blueprint.topics,
        key=lambda t: (group(t), counts.get(t, 0) if group(t) == 2 else 0, -contribution(t)),
    )


def selection_prior(prior: Prior, threshold: float) -> Prior:
    """Априорное для выбора заданий: среднее в пороге заявленного грейда, чтобы тест сразу шёл
    с заданий нужного уровня. Оценка, по которой решается грейд, считается с общим априорным."""
    return replace(prior, mean=threshold)
