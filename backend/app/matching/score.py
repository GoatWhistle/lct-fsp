"""Скор соответствия и порядок подборки (mechanics.md, §12) — чистые функции.

Скор — ожидаемая взвешенная доля выполненных требований по темам плюс ограниченный вклад
самоописанного стека:

    S = (1 − λ) Σ_t v_t P(θ_t ≥ req_t) + λ o

Объяснение — вклады слагаемых этой же формулы: сумма вкладов равна скору, обнуление фактора
уменьшает скор ровно на его вклад. Самоописание поднимает скор не больше чем на λ.
"""

import enum
import hashlib
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from app.domain.skill import Normal
from app.matching.importance import TopicImportance


@dataclass(frozen=True)
class Requirement:
    """Требование потребности по теме: вес темы v_t (Σ v_t = 1) и требуемый уровень req_t."""

    topic: str
    weight: float
    level: float


def requirements(
    topics: Sequence[tuple[str, TopicImportance]],
    *,
    requirement: float,
    importance_weights: Mapping[str, float],
) -> list[Requirement]:
    """Темы потребности с важностью → требования. Вес — вес важности, нормированный на сумму;
    требуемый уровень у всех тем один — порог грейда потребности."""
    raw = [importance_weights[importance] for _, importance in topics]
    total = sum(raw)
    return [
        Requirement(topic, weight / total, requirement)
        for (topic, _), weight in zip(topics, raw, strict=True)
    ]


@dataclass(frozen=True)
class TopicFit:
    topic: str
    weight: float
    requirement: float
    level: Normal
    # P(θ_t ≥ req_t) по профилю навыков.
    probability: float
    contribution: float


@dataclass(frozen=True)
class StackFit:
    # Технологии потребности, которые кандидат указал в самоописании.
    matched: tuple[str, ...]
    total: int
    # o — доля технологий потребности в самоописанном стеке; без стека в потребности — 0.
    overlap: float
    contribution: float


@dataclass(frozen=True)
class Match:
    score: float
    topics: tuple[TopicFit, ...]
    stack: StackFit


def match_score(
    need: Sequence[Requirement],
    levels: Mapping[str, Normal],
    need_stack: Collection[str],
    candidate_stack: Collection[str],
    *,
    stack_cap: float,
) -> Match:
    """Скор соответствия кандидата потребности; `levels` — уровни по темам из профиля навыков,
    `stack_cap` — λ, потолок вклада самоописания."""
    probabilities = [levels[r.topic].prob_at_least(r.level) for r in need]
    matched = tuple(sorted(set(need_stack) & set(candidate_stack)))
    overlap = len(matched) / len(set(need_stack)) if need_stack else 0.0

    # Скор — по формуле, вклады — отдельно: их совпадение проверяет тест, а не построение.
    skills = sum(r.weight * p for r, p in zip(need, probabilities, strict=True))
    score = (1 - stack_cap) * skills + stack_cap * overlap

    topics = tuple(
        TopicFit(r.topic, r.weight, r.level, levels[r.topic], p, (1 - stack_cap) * r.weight * p)
        for r, p in zip(need, probabilities, strict=True)
    )
    stack = StackFit(matched, len(set(need_stack)), overlap, stack_cap * overlap)
    return Match(score, topics, stack)


def ranking(scores: Mapping[uuid.UUID, float], selection_id: uuid.UUID) -> list[uuid.UUID]:
    """Кандидаты по убыванию скора. Ничьи — по хэшу пары «подборка — кандидат»: порядок
    детерминирован, но ни один кандидат не стоит выше всегда — ни по дате регистрации, ни по
    защищённым признакам."""
    return sorted(scores, key=lambda c: (-scores[c], _tie_breaker(selection_id, c)))


def _tie_breaker(selection_id: uuid.UUID, candidate_id: uuid.UUID) -> bytes:
    return hashlib.sha256(f"{selection_id}:{candidate_id}".encode()).digest()


class Verdict(enum.StrEnum):
    """Вероятность выполнить требование словами (`confidence_language_bands`)."""

    confidently_above = "confidently_above"
    likely_above = "likely_above"
    likely_below = "likely_below"
    below = "below"


def verdict(probability: float, bands: Sequence[float]) -> Verdict:
    """Границы — по возрастанию: ниже первой — «ниже требования», от последней — «уверенно
    выше»."""
    words = (Verdict.below, Verdict.likely_below, Verdict.likely_above, Verdict.confidently_above)
    return words[sum(probability >= edge for edge in bands)]
