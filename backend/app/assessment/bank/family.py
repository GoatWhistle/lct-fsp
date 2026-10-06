"""Семейство заданий — шаблон, генератор параметров и проверка ответа кодом (mechanics.md, §5).

Экземпляр полностью задан seed: генератор получает `random.Random(seed)` и возвращает условие,
параметры и эталон. Эталон вычисляется исполнением кода и живёт только на бэкенде — на фронт
уходят условие, листинг и варианты.

Генератор семейства не меняется: по seed из предъявления экземпляр восстанавливается при
проверке ответа, на тех же экземплярах стоит калибровка. Другой генератор — новое семейство со
своим кодом.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Instance:
    prompt: str
    answer: str
    params: dict[str, Any]
    code: str | None = None
    # Выбор с перемешиванием; пусто — вычисляемый ответ, который кандидат вводит сам.
    options: tuple[str, ...] = field(default=())


Generator = Callable[[random.Random], Instance]


@dataclass(frozen=True)
class Family:
    code: str
    topic: str
    # Грейд по оценке эксперта: от него стартовые сложность и разделяющая сила (§2).
    grade: str
    generate: Generator = field(repr=False, compare=False)

    def instance(self, seed: int) -> Instance:
        return self.generate(random.Random(seed))

    def check(self, instance: Instance, response: str) -> bool:
        return same_answer(response, instance.answer)


def same_answer(response: str, answer: str) -> bool:
    """Сравнение без учёта регистра и пробелов; числа — по значению («7», «7.0», «7,0»)."""
    given, expected = _normalize(response), _normalize(answer)
    try:
        return float(given.replace(",", ".")) == float(expected.replace(",", "."))
    except ValueError:
        return given == expected


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()
