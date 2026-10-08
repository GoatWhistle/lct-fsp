"""Признаки модели принятия числами (mechanics.md, §13): одна строка на пару «потребность —
кандидат», столбцы `COLUMNS`. Тот же перевод — при обучении на стенде и в проде: модель видит
одни и те же числа там и там.

Нет данных — `nan`: модель сама решает, куда идёт пропуск. Вилки нет — строки нет вовсе:
P(принятия) без вилки не считается (`encode` отдаёт None).
"""

import math
from collections.abc import Mapping

from app.domain.selection import AcceptanceFeatures
from app.domain.work import WorkFormat

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
