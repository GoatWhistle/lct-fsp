"""Семейство заданий — шаблон, генератор параметров и проверка ответа кодом (mechanics.md, §5).

Экземпляр полностью задан seed: генератор получает `random.Random(seed)` и возвращает условие,
параметры и эталон. Эталон вычисляется исполнением кода — через исполнитель `CodeRunner`, он
приходит в генератор значением, как seed, — и живёт только на бэкенде: на фронт уходят условие,
листинг и варианты.

Генератор семейства не меняется: по seed из предъявления экземпляр восстанавливается при
проверке ответа, на тех же экземплярах стоит калибровка. Другой генератор — новое семейство со
своим кодом.
"""

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.domain.bank.runner import CodeRunner


@dataclass(frozen=True)
class Instance:
    prompt: str
    answer: str
    params: dict[str, Any]
    code: str | None = None
    # Выбор с перемешиванием; пусто — вычисляемый ответ, который кандидат вводит сам.
    options: tuple[str, ...] = field(default=())


Generator = Callable[[random.Random, CodeRunner], Instance]


@dataclass(frozen=True)
class Family:
    code: str
    topic: str
    # Грейд по оценке эксперта: от него стартовые сложность и разделяющая сила (§2).
    grade: str
    generate: Generator = field(repr=False, compare=False)
    # Якорное семейство: параметры заморожены на экспертных, держат начало и масштаб шкалы (§7).
    anchor: bool = False

    def instance(self, seed: int, runner: CodeRunner) -> Instance:
        return self.generate(random.Random(seed), runner)

    def check(self, instance: Instance, response: str) -> bool:
        return same_answer(response, instance.answer)


def rounded(value: float, digits: int) -> str:
    """Число с `digits` знаками после точки, половина — вверх по модулю, как округляют вручную.

    Округляется десятичная запись числа, а не двоичное значение: 2.675 станет 2.68, хотя
    f"{2.675:.2f}" даёт 2.67.
    """
    quantum = Decimal(1).scaleb(-digits)
    result = Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)
    return str(result.copy_abs() if result.is_zero() else result)


def same_answer(response: str, answer: str) -> bool:
    """Сравнение без учёта регистра и пробелов; числа — по значению («7», «7.0», «7,0»).

    Эталон из нескольких значений сравнивается поштучно: значения разделяются пробелами, запятыми
    или «;», каждое — как число или как текст. Так «1 23» не засчитывается за «12 3». «|» между
    списками — само значение и с пробелами, и без: «8|9» — то же, что «8 | 9». Дробная часть в
    таких эталонах — только через точку.
    """
    expected = values(answer)
    if len(expected) > 1:
        given = values(response)
        return len(given) == len(expected) and all(
            _same_value(g, e) for g, e in zip(given, expected, strict=True)
        )
    return _same_value(_normalize(response), _normalize(answer))


def values(text: str) -> list[str]:
    """Значения ответа по порядку."""
    return _VALUE.findall(text)


def _same_value(given: str, expected: str) -> bool:
    """Числа сравниваются как десятичная запись, а не как float: «0.30000000000000004» не
    равно «0.300000000000000041», хотя во float они совпадают."""
    given, expected = given.lower(), expected.lower()
    try:
        return Decimal(given.replace(",", ".")) == Decimal(expected.replace(",", "."))
    except InvalidOperation:
        return given == expected


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()


# Значение — «|» или всё между разделителями: пробелами, запятыми, «;» и «|».
_VALUE = re.compile(r"\||[^\s,;|]+")
