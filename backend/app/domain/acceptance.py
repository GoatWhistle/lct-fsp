"""Признаки модели принятия числами (mechanics.md, §13): одна строка на пару «потребность —
кандидат», столбцы `COLUMNS`. Тот же перевод — при обучении на стенде и в проде: модель видит
одни и те же числа там и там.

Нет данных — `nan`: модель сама решает, куда идёт пропуск. Вилки нет — строки нет вовсе:
P(принятия) без вилки не считается (`encode` отдаёт None).
"""

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.domain.selection import AcceptanceExplanation, AcceptanceFeatures
from app.domain.work import SalaryRange, WorkFormat

# Порядок столбцов модели. Вилка — в логарифме отношения: «на 20 % выше ожидания» значит одно и
# то же у стажёра и у старшего.
COLUMNS = (
    # ln(середина вилки / ожидание кандидата).
    "salary_to_expected",
    # ln(середина вилки / медиана рынка грейда категории кандидата).
    "salary_to_market",
    "grade",
    # 1 — формат потребности среди готовых кандидату, 0 — нет.
    "format_match",
    # 1 — город не важен или совпал, 0,5 — не совпал, но готов к переезду, 0 — не совпал.
    "city_match",
    "open_invitations",
    "match_score",
    # 1 — сфера компании среди интересных кандидату, иначе 0.
    "industry_match",
)
# Категориальные столбцы — значения строками.
CATEGORICAL = ("grade",)
# Монотонные ограничения: +1 — P не убывает по столбцу, −1 — не возрастает. Выше вилка — P не
# ниже; больше открытых приглашений — не выше.
MONOTONE: Mapping[str, int] = {
    "salary_to_expected": 1,
    "salary_to_market": 1,
    "open_invitations": -1,
}

type Row = tuple[float | str, ...]


def salary_middle(features: AcceptanceFeatures) -> float | None:
    salary = features.salary
    return None if salary is None else (salary.low + salary.high) / 2


def format_match(features: AcceptanceFeatures) -> float:
    if not features.work_formats:
        return math.nan
    return 1.0 if features.need_work_format in features.work_formats else 0.0


def city_match(features: AcceptanceFeatures) -> float:
    """Удалённой потребности и потребности без города город не важен."""
    if features.need_work_format == WorkFormat.remote or features.need_city is None:
        return 1.0
    if features.relocation is None:
        return math.nan
    if features.city == features.need_city:
        return 1.0
    return 0.5 if features.relocation else 0.0


def industry_match(features: AcceptanceFeatures) -> float:
    return float(features.company_industry in features.industries)


def encode(features: AcceptanceFeatures) -> Row | None:
    """Строка модели по `COLUMNS`; без вилки — None."""
    middle = salary_middle(features)
    if middle is None:
        return None
    expected = features.expected_salary
    return (
        math.log(middle / expected) if expected else math.nan,
        math.log(middle / features.market_salary),
        features.grade,
        format_match(features),
        city_match(features),
        float(features.open_invitations),
        features.match_score,
        industry_match(features),
    )


# Факторы объяснения: столбцы модели, сложенные по смыслу. Два вилочных столбца — один фактор
# «вилка»: делить вклад вилки между ними нечем, а работодателю нужен один ответ.
FACTORS: Mapping[str, str] = {
    "salary_to_expected": "salary",
    "salary_to_market": "salary",
    "grade": "grade",
    "format_match": "format",
    "city_match": "city",
    "open_invitations": "load",
    "match_score": "match",
    "industry_match": "industry",
}


def explanation(base: float, shap: Sequence[float]) -> AcceptanceExplanation:
    """Объяснение по SHAP-вкладам столбцов `COLUMNS` в логите. Складывание столбцов в факторы
    сумму не меняет: `base` плюс вклады по-прежнему равны логиту."""
    if len(shap) != len(COLUMNS):
        raise ValueError(f"вкладов должно быть {len(COLUMNS)}, получено {len(shap)}")
    folded: dict[str, float] = dict.fromkeys(dict.fromkeys(FACTORS.values()), 0.0)
    for column, value in zip(COLUMNS, shap, strict=True):
        folded[FACTORS[column]] += value
    return AcceptanceExplanation(base, folded)


@dataclass(frozen=True)
class SalaryHint:
    """Подсказка по вилке (§13): P при вилке работодателя и вилка, при которой P достигает цели.

    `probability` считается при вилке, округлённой до шага: точная P при любой вилке позволяла
    бы перебором вилок найти ожидание кандидата точнее шага. `range` — самая низкая вилка сетки,
    где P не ниже цели; `None` — цель недостижима в пределах сетки, вилку не выдумываем."""

    probability: float
    # Вилка, по которой посчитана `probability`: вилка работодателя, округлённая до шага.
    evaluated: SalaryRange
    target: float
    range: SalaryRange | None
    # Шаг округления вилки, ₽.
    step: int


def snap(value: float, step: int) -> int:
    """Ближайшее кратное шагу, не ниже самого шага; половина шага округляется вверх."""
    return max(step, math.floor(value / step + 0.5) * step)


def quantize_expectation(features: AcceptanceFeatures, step: int) -> AcceptanceFeatures:
    """Публичные прогнозы зависят только от ячейки ожидания шириной `step`, а не от точной суммы.
    Округление входящей вилки само по себе от перебора публичной модели не защищает."""
    expected = features.expected_salary
    return dataclasses.replace(
        features, expected_salary=None if expected is None else snap(expected, step)
    )


def salary_hint(
    features: AcceptanceFeatures,
    salary: SalaryRange,
    predict: Callable[[Sequence[AcceptanceFeatures]], Sequence[float | None]],
    *,
    target: float,
    step: int,
    market_ratio: float,
) -> SalaryHint | None:
    """Подсказка для пары по её признакам и вилке `salary`; `None` — модель P не знает.

    Сетка — вилки той же ширины, что у `salary` (до шага), с «от» кратным шагу от `step` до
    `market_ratio` рыночных медиан грейда. P не убывает по вилке, поэтому порог один: берётся
    первая вилка сетки с P не ниже цели. Все границы подсказки — кратные шагу, а P считается
    именно по ней, так что округление не уводит её ниже цели."""
    width = math.floor((salary.high - salary.low) / step + 0.5) * step
    low = snap(salary.low, step)
    shown = SalaryRange(low, low + width)
    top = max(step, math.ceil(market_ratio * features.market_salary / step) * step)
    grid = [SalaryRange(start, start + width) for start in range(step, top + 1, step)]
    coarse = quantize_expectation(features, step)
    rows = [dataclasses.replace(coarse, salary=r) for r in (shown, *grid)]
    found = predict(rows)
    if any(p is None for p in found):
        return None
    probabilities = [p for p in found if p is not None]
    reached = next((r for r, p in zip(grid, probabilities[1:], strict=True) if p >= target), None)
    return SalaryHint(probabilities[0], shown, target, reached, step)
