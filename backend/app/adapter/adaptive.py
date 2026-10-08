"""Выбор следующего задания — реализация порта `ItemSelector` (mechanics.md, §6).

Максимум информации Фишера со случайным выбором из top-k и потолком доли показов. Чистые
функции без БД: состояние попытки — счётчики заданий по темам и оценка уровня, банк — семейства
с текущими параметрами, долей показов и давностью показа кандидату.
"""

import random
from collections.abc import Mapping, Sequence

from app.domain.adaptive import Blueprint, Choice, Exposure, Option
from app.domain.skill import SkillEstimate, sigmoid


def information(discrimination: float, difficulty: float, level: float) -> float:
    """Информация Фишера 2PL при уровне θ: I = a² p (1 − p)."""
    p = sigmoid(discrimination * (level - difficulty))
    return discrimination**2 * p * (1 - p)


def choose(
    blueprint: Blueprint,
    counts: Mapping[str, int],
    estimate: SkillEstimate,
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


def _topics_by_priority(
    blueprint: Blueprint, counts: Mapping[str, int], estimate: SkillEstimate
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


class MaxInformationSelector:
    """Реализация порта `ItemSelector`; `top_k` и `max_rate` — `exposure_top_k` и
    `exposure_max_rate` из конфига механик, передаёт сборка."""

    def __init__(self, *, top_k: int, max_rate: float) -> None:
        self.top_k = top_k
        self.max_rate = max_rate

    def choose(
        self,
        blueprint: Blueprint,
        counts: Mapping[str, int],
        estimate: SkillEstimate,
        options: Sequence[Option],
        attempts_in_window: int,
        rng: random.Random,
    ) -> Choice | None:
        exposure = Exposure(attempts_in_window, self.max_rate, self.top_k)
        return choose(blueprint, counts, estimate, options, exposure, rng)
