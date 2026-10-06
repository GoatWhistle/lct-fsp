"""Тестирование и тест-дизайн: классы эквивалентности, граничные значения, покрытие, мутанты,
таблицы решений, переходы состояний."""

import itertools
import random
from collections.abc import Callable

from app.assessment.bank.family import Instance

OUTCOMES = ["passed", "failed", "skipped"]


def fail_fast(rng: random.Random) -> Instance:
    statuses = [rng.choices(OUTCOMES, weights=[6, 2, 1])[0] for _ in range(rng.randint(7, 10))]
    if "failed" not in statuses:
        statuses[rng.randrange(2, len(statuses))] = "failed"
    first_fail = statuses.index("failed")
    passed = statuses[:first_fail].count("passed")
    code = "\n".join(f"test_{i + 1:02d} … {s}" for i, s in enumerate(statuses))
    prompt = (
        "Так прошли бы тесты при полном прогоне. Их запускают командой pytest -x. Сколько тестов "
        "завершится со статусом passed?"
    )
    return Instance(prompt, str(passed), {"statuses": statuses}, code=code)


def boundary_values(rng: random.Random) -> Instance:
    low = rng.randint(1, 50)
    high = low + rng.randint(2, 60)
    boundary = {low - 1, low, low + 1, high - 1, high, high + 1}
    picks = set(rng.sample(sorted(boundary), rng.randint(2, 4)))
    while len(picks) < 8:
        picks.add(rng.randint(low - 5, high + 5))
    values = sorted(picks)
    answer = len(boundary & picks)
    prompt = (
        f"Поле принимает целые числа от {low} до {high} включительно. Анализ граничных значений "
        "берёт по три точки у каждой границы: саму границу и соседей с обеих сторон. Сколько "
        f"значений из набора {', '.join(map(str, values))} — граничные?"
    )
    return Instance(prompt, str(answer), {"low": low, "high": high, "values": values})


def branch_coverage(rng: random.Random) -> Instance:
    a, b = sorted(rng.sample(range(0, 100), 2))
    c = rng.randint(b + 1, 150)
    branches: list[Callable[[int], bool]] = [
        lambda x: x < a,
        lambda x: x < b,
        lambda x: x == c,
        lambda x: True,
    ]
    code = (
        "def tariff(x):\n"
        f"    if x < {a}:\n        return 'low'\n"
        f"    elif x < {b}:\n        return 'mid'\n"
        f"    elif x == {c}:\n        return 'special'\n"
        "    else:\n        return 'high'\n"
    )
    inputs = sorted(rng.sample(range(-10, 170), rng.randint(5, 8)))
    covered = {next(i for i, hit in enumerate(branches) if hit(x)) for x in inputs}
    prompt = (
        f"Тесты вызывают tariff с аргументами {', '.join(map(str, inputs))}. Сколько тестов можно "
        "удалить, не потеряв покрытия ветвей? Ответ — наибольшее такое число."
    )
    params = {"a": a, "b": b, "c": c, "inputs": inputs}
    return Instance(prompt, str(len(inputs) - len(covered)), params, code=code)


MUTANTS = [
    ("ge-to-gt", "граница: >= заменено на >"),
    ("divisor", "делитель увеличен на 1"),
    ("fallback", "return 0 заменено на return 1"),
]


def mutant_killers(rng: random.Random) -> Instance:
    limit, divisor = rng.randrange(100, 1000, 50), rng.randint(5, 20)
    kind, description = rng.choice(MUTANTS)
    inputs = sorted(
        {rng.choice([limit, limit - 1, limit + 1]), *rng.sample(range(limit - 300, limit + 600), 5)}
    )

    def original(total: int) -> int:
        return total // divisor if total >= limit else 0

    def mutant(total: int) -> int:
        if kind == "ge-to-gt":
            return total // divisor if total > limit else 0
        if kind == "divisor":
            return total // (divisor + 1) if total >= limit else 0
        return total // divisor if total >= limit else 1

    killers = sum(1 for x in inputs if original(x) != mutant(x))
    code = (
        "def bonus(total):\n"
        f"    if total >= {limit}:\n"
        f"        return total // {divisor}\n"
        "    return 0\n"
    )
    prompt = (
        f"Мутационное тестирование. Мутант bonus: {description}. Тесты проверяют bonus на "
        f"аргументах {', '.join(map(str, inputs))} с ожиданиями, посчитанными по исходной "
        "функции. Сколько тестов упадут на мутанте?"
    )
    params = {"limit": limit, "divisor": divisor, "mutant": kind, "inputs": inputs}
    return Instance(prompt, str(killers), params, code=code)


def equivalence_class(rng: random.Random) -> Instance:
    low = rng.randint(14, 25)
    high = low + rng.randint(30, 50)
    values = sorted(rng.sample(range(low - 15, high + 15), 9))
    probe = rng.choice(values)

    def klass(x: int) -> int:
        return 0 if x < low else 1 if x <= high else 2

    same = sum(1 for v in values if v != probe and klass(v) == klass(probe))
    prompt = (
        f"Поле «возраст» принимает целые от {low} до {high} включительно. Сколько значений из "
        f"набора {', '.join(map(str, values))}, кроме самого {probe}, попадают в один класс "
        f"эквивалентности с {probe}?"
    )
    return Instance(prompt, str(same), {"low": low, "high": high, "values": values, "probe": probe})


CONDITIONS = [
    "есть скидка",
    "доставка курьером",
    "оплата картой",
    "клиент новый",
    "заказ срочный",
    "товар крупный",
]

CONSTRAINTS = {
    "exclusive": "«{a}» и «{b}» не бывают одновременно",
    "implies": "если «{a}», то обязательно «{b}»",
    "one_of": "хотя бы одно из «{a}» и «{b}» есть всегда",
}


def _holds(kind: str, a: bool, b: bool) -> bool:
    if kind == "exclusive":
        return not (a and b)
    if kind == "implies":
        return b or not a
    return a or b


def decision_table(rng: random.Random) -> Instance:
    names = rng.sample(CONDITIONS, rng.randint(3, 5))
    constraints: list[tuple[str, int, int]] = []
    for _ in range(rng.randint(1, 3)):
        a, b = rng.sample(range(len(names)), 2)
        constraints.append((rng.choice(list(CONSTRAINTS)), a, b))
    rules = sum(
        1
        for row in itertools.product([False, True], repeat=len(names))
        if all(_holds(kind, row[a], row[b]) for kind, a, b in constraints)
    )
    texts = [CONSTRAINTS[kind].format(a=names[a], b=names[b]) for kind, a, b in constraints]
    prompt = (
        f"Таблица решений по условиям: {', '.join(f'«{c}»' for c in names)}. Ограничения: "
        f"{'; '.join(texts)}. Сколько правил (допустимых комбинаций условий) в полной таблице?"
    )
    return Instance(prompt, str(rules), {"conditions": names, "constraints": constraints})


STATES = ["Новый", "Оплачен", "Собран", "Отправлен", "Доставлен", "Отменён"]


def transition_pairs(rng: random.Random) -> Instance:
    states = STATES[: rng.randint(4, 6)]
    transitions = {(states[i], states[i + 1]) for i in range(len(states) - 1)}
    while len(transitions) < len(states) + 2:
        a, b = rng.sample(states, 2)
        transitions.add((a, b))
    ordered = sorted(transitions, key=lambda t: (states.index(t[0]), states.index(t[1])))
    pairs = sum(1 for t1 in ordered for t2 in ordered if t1[1] == t2[0])
    code = "\n".join(f"{a} → {b}" for a, b in ordered)
    prompt = (
        "Переходы конечного автомата заказа перечислены ниже. Сколько тестов нужно для покрытия "
        "всех пар последовательных переходов (1-switch): по одному тесту на каждую пару "
        "«переход, за которым сразу идёт следующий»?"
    )
    return Instance(prompt, str(pairs), {"transitions": [list(t) for t in ordered]}, code=code)
