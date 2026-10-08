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
import string
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from app.domain.bank.runner import CodeRunner


class Kind(StrEnum):
    """Вид задания — что оно проверяет. Сценарные виды (`SCENARIO_KINDS`) мерят решения, которые
    отличают старшие грейды; трассировку решит и junior, поэтому её доля в теме ограничена."""

    # Что выведет код или запрос.
    TRACE = "trace"
    # Посчитать по данным условия.
    COMPUTE = "compute"
    # Выбор решения с компромиссами.
    SCENARIO_CHOICE = "scenario_choice"
    # Поиск ошибки.
    BUG_HUNT = "bug_hunt"
    # Порядок шагов.
    ORDERING = "ordering"
    # Разбор инцидента.
    INCIDENT = "incident"


SCENARIO_KINDS = frozenset({Kind.SCENARIO_CHOICE, Kind.BUG_HUNT, Kind.ORDERING, Kind.INCIDENT})


class AnswerFormat(StrEnum):
    # Вычисляемый ответ, кандидат вводит его сам.
    VALUE = "value"
    # Буква одного из вариантов.
    CHOICE = "choice"
    # Буквы всех вариантов в верном порядке строкой: «BDAC».
    ORDERING = "ordering"


@dataclass(frozen=True)
class Option:
    letter: str
    text: str


@dataclass(frozen=True)
class Instance:
    prompt: str
    answer: str
    params: dict[str, Any]
    code: str | None = None
    # Варианты по порядку букв; пусто — вычисляемый ответ.
    options: tuple[Option, ...] = field(default=())
    answer_format: AnswerFormat = AnswerFormat.VALUE


Generator = Callable[[random.Random, CodeRunner], Instance]


@dataclass(frozen=True)
class Family:
    code: str
    topic: str
    # Грейд по оценке эксперта: от него стартовые сложность и разделяющая сила (§2).
    grade: str
    kind: Kind
    generate: Generator = field(repr=False, compare=False)
    # Якорное семейство: параметры заморожены на экспертных, держат начало и масштаб шкалы (§7).
    anchor: bool = False

    def instance(self, seed: int, runner: CodeRunner) -> Instance:
        return self.generate(random.Random(seed), runner)

    def check(self, instance: Instance, response: str) -> bool:
        return same_answer(
            response, instance.answer, letters=instance.answer_format != AnswerFormat.VALUE
        )


_KINDS: dict[Generator, Kind] = {}


def kind(value: Kind) -> Callable[[Generator], Generator]:
    """Вид задания генератора; генератор без вида в банк не попадает (`kind_of`)."""

    def mark(generate: Generator) -> Generator:
        _KINDS[generate] = value
        return generate

    return mark


def kind_of(generate: Generator) -> Kind:
    try:
        return _KINDS[generate]
    except KeyError:
        raise ValueError(f"у генератора {generate.__name__} не указан вид задания") from None


def choice(
    rng: random.Random,
    prompt: str,
    correct: str,
    wrong: Sequence[str],
    params: dict[str, Any],
    code: str | None = None,
) -> Instance:
    """Выбор одного варианта: ответ — буква верного. Тексты перемешиваются, буквы — случайные
    из латиницы: буква верного варианта одного экземпляра совпадает с другим с вероятностью
    1/26, а не 1/k, как при буквах A, B, C по порядку."""
    texts = _shuffled(rng, [correct, *wrong])
    options = _lettered(rng, texts)
    answer = next(o.letter for o in options if o.text == correct)
    return Instance(prompt, answer, params, code, options, AnswerFormat.CHOICE)


def ordering(
    rng: random.Random,
    prompt: str,
    steps: Sequence[str],
    params: dict[str, Any],
    code: str | None = None,
) -> Instance:
    """Перестановка: `steps` — в верном порядке, ответ — буквы шагов в этом порядке строкой.
    Тексты и буквы перемешиваются, как в `choice`."""
    options = _lettered(rng, _shuffled(rng, list(steps)))
    letter = {o.text: o.letter for o in options}
    answer = "".join(letter[step] for step in steps)
    return Instance(prompt, answer, params, code, options, AnswerFormat.ORDERING)


def _shuffled(rng: random.Random, texts: list[str]) -> list[str]:
    if len(set(texts)) != len(texts):
        raise ValueError(f"варианты повторяются: {texts}")
    rng.shuffle(texts)
    return texts


def _lettered(rng: random.Random, texts: list[str]) -> tuple[Option, ...]:
    letters = sorted(rng.sample(string.ascii_uppercase, len(texts)))
    return tuple(Option(letter, text) for letter, text in zip(letters, texts, strict=True))


def rounded(value: float, digits: int) -> str:
    """Число с `digits` знаками после точки, половина — вверх по модулю, как округляют вручную.

    Округляется десятичная запись числа, а не двоичное значение: 2.675 станет 2.68, хотя
    f"{2.675:.2f}" даёт 2.67.
    """
    quantum = Decimal(1).scaleb(-digits)
    result = Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)
    return str(result.copy_abs() if result.is_zero() else result)


def same_answer(response: str, answer: str, *, letters: bool = False) -> bool:
    """Сравнение без учёта регистра и пробелов; числа — по значению («7», «7.0», «7,0»).

    `letters` — ответ буквами вариантов: регистр, пробелы и разделители между буквами не важны
    («b, d - a c» — то же, что «BDAC»), кириллические двойники латинских букв читаются латиницей.

    Эталон из нескольких значений сравнивается поштучно: значения разделяются пробелами, запятыми
    или «;», каждое — как число или как текст. Так «1 23» не засчитывается за «12 3». «|» между
    списками — само значение и с пробелами, и без: «8|9» — то же, что «8 | 9». Дробная часть в
    таких эталонах — только через точку.
    """
    if letters:
        return _letters(response) == _letters(answer)
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


def _letters(text: str) -> str:
    return _LETTER_SEPARATOR.sub("", text).upper().translate(_CYRILLIC_TWINS)


_LETTER_SEPARATOR = re.compile(r"[\s,;.:|/\\>→–—-]+")
_CYRILLIC_TWINS = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


# Значение — «|» или всё между разделителями: пробелами, запятыми, «;» и «|».
_VALUE = re.compile(r"\||[^\s,;|]+")
