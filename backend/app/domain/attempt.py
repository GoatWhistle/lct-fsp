"""Попытка теста глазами сигналов профиля: отвеченное предъявление (mechanics.md, §5, §11)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.skill import Observation


@dataclass(frozen=True)
class AnsweredPresentation:
    """Отвеченное предъявление: семейство, тема, параметры экземпляра, верность ответа.

    Разделяющая сила и сложность — семейства на момент показа: калибровка их потом сдвигает, а
    оценка по ответу должна пересчитываться в то же значение.
    """

    family_code: str
    topic: str
    params: Mapping[str, Any]
    discrimination: float
    difficulty: float
    correct: bool
    answered_at: datetime

    def observation(self, weight: float = 1.0) -> Observation:
        """Наблюдение модели навыка; `weight` — вес уровня доверия сигнала."""
        return Observation(
            topic=self.topic,
            correct=self.correct,
            discrimination=self.discrimination,
            difficulty=self.difficulty,
            weight=weight,
        )
