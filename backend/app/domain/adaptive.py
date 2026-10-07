"""Адаптивный тест: бланк, кандидаты на следующее задание и правило остановки
(mechanics.md, §6).

Сам выбор следующего семейства — за портом `app.usecase.interface.ItemSelector`: алгоритму
есть альтернативы. Правило остановки — инвариант механики: остановка по точности уравнивает
точность, а не длину теста.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.skill import Normal, Prior


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

    def allows(self, option: Option) -> bool:
        """Показ в текущей попытке оставит долю в окне не выше потолка."""
        return option.shown + 1 <= self.max_rate * (self.attempts + 1) + 1e-9


@dataclass(frozen=True)
class Choice:
    code: str
    # Под потолком показов в теме ничего не осталось — взято наименее показанное семейство.
    capped: bool


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


def selection_prior(prior: Prior, threshold: float) -> Prior:
    """Априорное для выбора заданий: среднее в пороге заявленного грейда, чтобы тест сразу шёл
    с заданий нужного уровня. Оценка, по которой решается грейд, считается с общим априорным."""
    return replace(prior, mean=threshold)
