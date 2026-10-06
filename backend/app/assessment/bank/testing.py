"""Тестирование и тест-дизайн: классы эквивалентности, граничные значения, покрытие, мутанты,
таблицы решений, переходы состояний."""

import itertools
import random
from collections.abc import Callable

from app.assessment.bank.family import Instance, rounded

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


def run_summary(rng: random.Random) -> Instance:
    statuses = [rng.choices(OUTCOMES, weights=[6, 2, 1])[0] for _ in range(rng.randint(8, 12))]
    if "failed" not in statuses:
        statuses[rng.randrange(2, len(statuses))] = "failed"
    maxfail = rng.randint(1, 2)
    failed = passed = skipped = ran = 0
    for s in statuses:
        ran += 1
        passed += s == "passed"
        skipped += s == "skipped"
        failed += s == "failed"
        if failed >= maxfail:
            break
    code = "\n".join(f"test_{i + 1:02d} … {s}" for i, s in enumerate(statuses))
    prompt = (
        "Так прошли бы тесты при полном прогоне, по порядку. Их запускают командой "
        f"pytest --maxfail={maxfail}. Сколько тестов завершится со статусами passed, failed и "
        "skipped и сколько не запустится? Ответ — четыре числа через пробел в этом порядке."
    )
    answer = f"{passed} {failed} {skipped} {len(statuses) - ran}"
    return Instance(prompt, answer, {"statuses": statuses, "maxfail": maxfail}, code=code)


def assert_failures(rng: random.Random) -> Instance:
    checks: list[tuple[str, bool]] = []
    for _ in range(6):
        kind = rng.randrange(5)
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        if kind == 0:
            checks.append((f"assert {a} + {b} == {a + b + rng.choice([0, 0, 1])}", True))
        elif kind == 1:
            items = rng.sample(range(1, 10), 3)
            probe = rng.choice([*items, rng.randint(1, 9)])
            checks.append((f"assert {probe} in {items}", probe in items))
        elif kind == 2:
            checks.append((f"assert [{a}, {b}] == [{b}, {a}]", a == b))
        elif kind == 3:
            checks.append((f"assert 0.1 * {a} == {a / 10}", 0.1 * a == a / 10))
        else:
            checks.append((f"assert '{a}' * 2 == '{a}{a}'", True))
    code = "\n".join(f"def test_{i}():\n    {text}\n" for i, (text, _) in enumerate(checks, 1))
    # Первая строка — сам assert: проверяем его исполнением, а не по заготовленному флагу.
    failing = []
    for i, (text, _) in enumerate(checks, 1):
        try:
            exec(text, {})
        except AssertionError:
            failing.append(i)
    prompt = (
        "Какие тесты упадут? Ответ — номера тестов через пробел по возрастанию; если все "
        "пройдут — 0."
    )
    return Instance(
        prompt, " ".join(map(str, failing)) or "0", {"checks": [c for c, _ in checks]}, code=code
    )


def boundary_points(rng: random.Random) -> Instance:
    low = rng.randint(1, 50)
    high = low + rng.randint(3, 60)
    boundary = {low - 1, low, low + 1, high - 1, high, high + 1}
    picks = set(rng.sample(sorted(boundary), rng.randint(2, 4)))
    while len(picks) < 8:
        picks.add(rng.randint(low - 5, high + 5))
    values = sorted(picks)
    answer = sorted(boundary & picks)
    prompt = (
        f"Поле принимает целые числа от {low} до {high} включительно. Анализ граничных значений "
        "берёт по три точки у каждой границы: саму границу и соседей с обеих сторон. Какие "
        f"значения из набора {', '.join(map(str, values))} — граничные? Ответ — числа через "
        "пробел по возрастанию."
    )
    return Instance(
        prompt, " ".join(map(str, answer)), {"low": low, "high": high, "values": values}
    )


def mock_calls(rng: random.Random) -> Instance:
    items = [rng.randint(1, 60) for _ in range(rng.randint(5, 8))]
    limit = rng.randint(15, 45)
    batch = rng.randint(2, 3)
    code = (
        "from unittest.mock import Mock\n\n"
        "def sync(items, client):\n"
        "    batch = []\n"
        "    for x in items:\n"
        f"        if x > {limit}:\n"
        "            continue\n"
        "        batch.append(x)\n"
        f"        if len(batch) == {batch}:\n"
        "            client.send(sum(batch))\n"
        "            batch = []\n"
        "    if batch:\n"
        "        client.send(sum(batch))\n\n"
        "client = Mock()\n"
        f"sync({items}, client)\n"
        "print(client.send.call_count, client.send.call_args.args[0])\n"
    )
    from unittest.mock import Mock

    sent: list[int] = []
    client = Mock()
    client.send.side_effect = sent.append
    chunk: list[int] = []
    for x in items:
        if x > limit:
            continue
        chunk.append(x)
        if len(chunk) == batch:
            client.send(sum(chunk))
            chunk = []
    if chunk:
        client.send(sum(chunk))
    if not sent:
        items.append(1)
        return mock_calls(rng)
    prompt = (
        "Что выведет программа? Ответ — два числа через пробел: сколько раз вызван send и с "
        "каким аргументом в последний раз."
    )
    params = {"items": items, "limit": limit, "batch": batch}
    return Instance(prompt, f"{len(sent)} {sent[-1]}", params, code=code)


def flaky_retries(rng: random.Random) -> Instance:
    tests = rng.randint(5, 60)
    fail = rng.choice([2, 3, 4, 5, 8, 10, 15, 20])
    reruns = rng.randint(0, 1)
    p_test_fails = (fail / 100) ** (reruns + 1)
    p_green = (1 - p_test_fails) ** tests
    prompt = (
        f"В наборе {tests} независимых тестов, каждый нестабильный: падает с вероятностью "
        f"{fail} % при каждом запуске независимо от прошлых. Упавший тест перезапускается до "
        f"{reruns} раз. Какова вероятность, что весь прогон окажется зелёным? Ответ — число, "
        "округлите до тысячных."
    )
    return Instance(
        prompt, f"{rounded(p_green, 3)}", {"tests": tests, "fail": fail, "reruns": reruns}
    )


def fixture_teardown(rng: random.Random) -> Instance:
    names = rng.sample(["db", "cache", "client", "user", "tmpdir", "broker", "token"], 4)
    # Зависимости: каждая фикстура может зависеть от одной из предыдущих.
    deps = {
        names[0]: None,
        **{n: rng.choice([None, *names[:i]]) for i, n in enumerate(names[1:], 1)},
    }
    used = rng.sample(names, rng.randint(1, 2))
    setup: list[str] = []

    def need(name: str) -> None:
        dep = deps[name]
        if dep is not None:
            need(dep)
        if name not in setup:
            setup.append(name)

    for name in used:
        need(name)
    lines = [
        "@pytest.fixture\n"
        f"def {n}({deps[n] or ''}):\n"
        f"    print('+{n}')\n"
        "    yield\n"
        f"    print('-{n}')\n"
        for n in names
    ]
    code = "\n".join(lines) + f"\ndef test_flow({', '.join(used)}):\n    print('test')\n"
    output = [f"+{n}" for n in setup] + ["test"] + [f"-{n}" for n in reversed(setup)]
    prompt = "Какие строки напечатает запуск test_flow? Ответ — строки через пробел по порядку."
    return Instance(prompt, " ".join(output), {"deps": deps, "used": used}, code=code)


def branch_cover_set(rng: random.Random) -> Instance:
    bulk, member_bulk, cap = rng.randint(5, 15), rng.randint(3, 10), rng.randint(40, 80)
    code = (
        "def price(qty, member):\n"
        "    if qty <= 0:\n        return 'error'\n"
        f"    if qty > {cap}:\n        return 'too-many'\n"
        "    if member:\n"
        f"        if qty >= {member_bulk}:\n            return 'member-bulk'\n"
        "        return 'member'\n"
        f"    if qty >= {bulk}:\n        return 'bulk'\n"
        "    return 'regular'\n"
    )
    # Аргументы тестов: по случайной ветви на вызов, значение — внутри её диапазона.
    ranges = {
        "error": ((-3, 0), None),
        "too-many": ((cap + 1, cap + 20), None),
        "member-bulk": ((member_bulk, cap), True),
        "member": ((1, member_bulk - 1), True),
        "bulk": ((bulk, cap), False),
        "regular": ((1, bulk - 1), False),
    }
    calls = []
    for branch in rng.choices(list(ranges), k=4):
        (low, high), member = ranges[branch]
        calls.append(
            (rng.randint(low, high), rng.choice([True, False]) if member is None else member)
        )

    def price(qty: int, member: bool) -> str:
        if qty <= 0:
            return "error"
        if qty > cap:
            return "too-many"
        if member:
            return "member-bulk" if qty >= member_bulk else "member"
        return "bulk" if qty >= bulk else "regular"

    covered = {price(q, m) for q, m in calls}
    missed = [b for b in ranges if b not in covered]
    prompt = (
        f"Тесты вызывают {', '.join(f'price({q}, {m})' for q, m in calls)}. Какие ветви "
        "останутся непокрытыми? Ответ — значения, которые эти ветви возвращают, через пробел в "
        "порядке ветвей в коде; если покрыто всё — 0."
    )
    params = {"bulk": bulk, "member_bulk": member_bulk, "cap": cap, "calls": calls}
    return Instance(prompt, " ".join(missed) or "0", params, code=code)


def line_hits(rng: random.Random) -> Instance:
    limit, step = rng.randint(3, 9), rng.randint(2, 4)
    code = (
        "def score(points):\n"
        "    total = 0\n"
        "    for p in points:\n"
        f"        if p > {limit}:\n"
        f"            total += {step}      # A\n"
        "        elif p % 2 == 0:\n"
        "            total -= 1      # B\n"
        "        else:\n"
        "            continue        # C\n"
        "    return total\n"
    )
    calls = [[rng.randint(0, 12) for _ in range(rng.randint(2, 5))] for _ in range(2)]
    hits = [0, 0, 0]
    for points in calls:
        for p in points:
            hits[0 if p > limit else 1 if p % 2 == 0 else 2] += 1
    prompt = (
        f"Тесты вызывают {', '.join(f'score({c})' for c in calls)}. Отчёт покрытия с "
        "подсчётом (как в lcov) показывает, сколько раз выполнилась каждая строка. Сколько "
        "раз выполнятся строки A, B и C? Ответ — три числа через пробел."
    )
    return Instance(
        prompt, " ".join(map(str, hits)), {"limit": limit, "step": step, "calls": calls}, code=code
    )


def shared_state(rng: random.Random) -> Instance:
    cart: list[int] = []
    bodies, failed = [], []
    for i in range(1, 9):
        kind = rng.choice(["add", "add", "extend", "clear", "check"])
        n = rng.randint(1, 9)
        if kind == "add":
            body = f"CART.append({n})\n    assert CART == [{n}]"
            cart.append(n)
            ok = cart == [n]
        elif kind == "extend":
            body = f"CART.extend([{n}, {n}])\n    assert len(CART) == 2"
            cart.extend([n, n])
            ok = len(cart) == 2
        elif kind == "clear":
            body = "CART.clear()\n    assert CART == []"
            cart.clear()
            ok = True
        else:
            body = "assert sum(CART) == 0"
            ok = sum(cart) == 0
        bodies.append(f"def test_{i}():\n    {body}\n")
        if not ok:
            failed.append(i)
    code = "CART = []\n\n" + "\n".join(bodies)
    prompt = (
        "Тесты используют общий список CART и запускаются в порядке объявления. Каждый писали в "
        "расчёте на пустой CART. Какие тесты упадут? Ответ — номера через пробел по порядку; "
        "если ни один — 0."
    )
    return Instance(prompt, " ".join(map(str, failed)) or "0", {"bodies": bodies}, code=code)


def side_effects(rng: random.Random) -> Instance:
    retries = rng.randint(1, 3)
    rendered = [
        "TimeoutError()" if rng.random() < 0.4 else str(rng.randint(1, 99))
        for _ in range(2 * (retries + 1))
    ]
    code = (
        "from unittest.mock import Mock\n\n"
        f"fetch = Mock(side_effect=[{', '.join(rendered)}])\n\n"
        "def load():\n"
        f"    for attempt in range({retries + 1}):\n"
        "        try:\n"
        "            return fetch()\n"
        "        except TimeoutError:\n"
        "            pass\n"
        "    return -1\n\n"
        "results = [load(), load()]\n"
        "print(results[0], results[1], fetch.call_count)\n"
    )
    out: list[str] = []
    exec(code, {"print": lambda *a: out.append(" ".join(map(str, a)))})
    prompt = "Что выведет программа? Ответ — то, что появится в консоли."
    return Instance(prompt, out[0], {"effects": rendered, "retries": retries}, code=code)


def kill_matrix(rng: random.Random) -> Instance:
    limit, divisor = rng.randrange(100, 1000, 50), rng.randint(5, 20)
    shift = rng.randrange(50, 250, 10)
    inputs = sorted(rng.sample(range(limit - 300, limit + 400), 7))
    mutants: dict[str, tuple[str, Callable[[int], int]]] = {
        "М1": (
            f"граница сдвинута: total >= {limit + shift}",
            lambda t: t // divisor if t >= limit + shift else 0,
        ),
        "М2": (
            f"вместо return 0 — return total // {2 * divisor}",
            lambda t: t // divisor if t >= limit else t // (2 * divisor),
        ),
        "М3": (
            "вместо total // divisor — round(total / divisor)",
            lambda t: round(t / divisor) if t >= limit else 0,
        ),
    }

    def original(total: int) -> int:
        return total // divisor if total >= limit else 0

    kills = [sum(1 for x in inputs if f(x) != original(x)) for _, f in mutants.values()]
    code = (
        "def bonus(total):\n"
        f"    if total >= {limit}:\n"
        f"        return total // {divisor}\n"
        "    return 0\n"
    )
    listing = "; ".join(f"{name} — {text}" for name, (text, _) in mutants.items())
    prompt = (
        f"Мутационное тестирование функции bonus. Мутанты: {listing}. Тесты проверяют bonus на "
        f"аргументах {', '.join(map(str, inputs))} с ожиданиями по исходной функции. Сколько "
        "тестов упадёт на каждом мутанте? Ответ — три числа через пробел: М1, М2, М3."
    )
    params = {"limit": limit, "divisor": divisor, "shift": shift, "inputs": inputs}
    return Instance(prompt, " ".join(map(str, kills)), params, code=code)


def mutation_score(rng: random.Random) -> Instance:
    total = rng.randint(20, 120)
    equivalent = rng.randint(0, 8)
    killed = rng.randint((total - equivalent) // 3, total - equivalent)
    score = 100 * killed / (total - equivalent)
    prompt = (
        f"Инструмент сгенерировал {total} мутантов, тесты убили {killed}. Ручной разбор показал, "
        f"что {equivalent} из выживших эквивалентны исходному коду: никакой тест их не убьёт. "
        "Какова оценка мутационного тестирования без эквивалентных мутантов? Ответ — процент, "
        "округлите до десятых."
    )
    return Instance(
        prompt, f"{rounded(score, 1)}", {"total": total, "killed": killed, "equivalent": equivalent}
    )


def equivalence_members(rng: random.Random) -> Instance:
    low = rng.randint(14, 25)
    high = low + rng.randint(30, 50)
    values = sorted(rng.sample(range(low - 15, high + 15), 9))
    probe = rng.choice(values)

    def klass(x: int) -> int:
        return 0 if x < low else 1 if x <= high else 2

    same = [v for v in values if v != probe and klass(v) == klass(probe)]
    prompt = (
        f"Поле «возраст» принимает целые от {low} до {high} включительно. Какие значения из "
        f"набора {', '.join(map(str, values))}, кроме самого {probe}, попадают в один класс "
        f"эквивалентности с {probe}? Ответ — числа через пробел по возрастанию; если таких "
        "нет — 0."
    )
    params = {"low": low, "high": high, "values": values, "probe": probe}
    return Instance(prompt, " ".join(map(str, same)) or "0", params)


def decision_rules(rng: random.Random) -> Instance:
    names = rng.sample(CONDITIONS, rng.randint(3, 5))
    constraints: list[tuple[str, int, int]] = []
    for _ in range(rng.randint(1, 3)):
        a, b = rng.sample(range(len(names)), 2)
        constraints.append((rng.choice(list(CONSTRAINTS)), a, b))
    rows = [
        row
        for row in itertools.product([False, True], repeat=len(names))
        if all(_holds(kind, row[a], row[b]) for kind, a, b in constraints)
    ]
    with_first = sum(1 for row in rows if row[0])
    with_last = sum(1 for row in rows if row[-1])
    texts = [CONSTRAINTS[kind].format(a=names[a], b=names[b]) for kind, a, b in constraints]
    prompt = (
        f"Таблица решений по условиям: {', '.join(f'«{c}»' for c in names)}. Ограничения: "
        f"{'; '.join(texts)}. Сколько правил (допустимых комбинаций условий) в полной таблице, "
        f"в скольких из них выполнено «{names[0]}» и в скольких — «{names[-1]}»? Ответ — три "
        "числа через пробел."
    )
    params = {"conditions": names, "constraints": constraints}
    return Instance(prompt, f"{len(rows)} {with_first} {with_last}", params)


def risk_order(rng: random.Random) -> Instance:
    ids = rng.sample(range(10, 99), 6)
    scores = [(rng.randint(1, 5), rng.randint(1, 5)) for _ in ids]
    order = sorted(
        zip(ids, scores, strict=True), key=lambda t: (-t[1][0] * t[1][1], -t[1][1], t[0])
    )
    lines = [
        f"TC-{i}: вероятность отказа {p}, ущерб {d}" for i, (p, d) in zip(ids, scores, strict=True)
    ]
    prompt = (
        "Регрессию запускают по убыванию риска: риск = вероятность отказа × ущерб. При равном "
        "риске раньше идёт тест с большим ущербом, при равенстве и его — с меньшим номером. В "
        "каком порядке пойдут тесты? Ответ — номера без TC- через пробел."
    )
    return Instance(
        prompt,
        " ".join(str(i) for i, _ in order),
        {"ids": ids, "scores": scores},
        code="\n".join(lines),
    )


BUG_FLOW = {
    ("Новый", "назначить"): "Назначен",
    ("Новый", "отклонить"): "Отклонён",
    ("Назначен", "исправить"): "Исправлен",
    ("Назначен", "отклонить"): "Отклонён",
    ("Исправлен", "проверить: ок"): "Закрыт",
    ("Исправлен", "проверить: воспроизводится"): "Переоткрыт",
    ("Переоткрыт", "назначить"): "Назначен",
    ("Закрыт", "воспроизвёлся снова"): "Переоткрыт",
}
BUG_ACTIONS = sorted({action for _, action in BUG_FLOW})


def defect_lifecycle(rng: random.Random) -> Instance:
    bugs = {f"BUG-{n}": "Новый" for n in rng.sample(range(100, 999), 4)}
    events = []
    for _ in range(rng.randint(9, 12)):
        bug = rng.choice(list(bugs))
        allowed = [a for (state, a) in BUG_FLOW if state == bugs[bug]]
        action = rng.choice(allowed + BUG_ACTIONS[:1]) if allowed else rng.choice(BUG_ACTIONS)
        events.append(f"{bug}: {action}")
        bugs[bug] = BUG_FLOW.get((bugs[bug], action), bugs[bug])
    flow = "\n".join(f"{s} —[{a}]→ {t}" for (s, a), t in BUG_FLOW.items())
    prompt = (
        "Жизненный цикл дефекта задан переходами ниже; действие, для которого перехода нет, "
        "трекер отклоняет, статус не меняется. Все дефекты начинают в статусе «Новый». Какими "
        "будут статусы дефектов после событий? Ответ — статусы через пробел в порядке номеров "
        "дефектов по возрастанию."
    )
    answer = " ".join(bugs[b] for b in sorted(bugs))
    return Instance(
        prompt, answer, {"events": events}, code=flow + "\n\nСобытия:\n" + "\n".join(events)
    )


def transition_switch(rng: random.Random) -> Instance:
    states = STATES[: rng.randint(4, 6)]
    transitions = {(states[i], states[i + 1]) for i in range(len(states) - 1)}
    while len(transitions) < len(states) + rng.randint(2, 5):
        a, b = rng.sample(states, 2)
        transitions.add((a, b))
    ordered = sorted(transitions, key=lambda t: (states.index(t[0]), states.index(t[1])))
    start = rng.choice(states[:-1])
    pairs = [(t1, t2) for t1 in ordered for t2 in ordered if t1[1] == t2[0]]
    from_start = sum(1 for t1, _ in pairs if t1[0] == start)
    code = "\n".join(f"{a} → {b}" for a, b in ordered)
    prompt = (
        "Переходы конечного автомата заказа перечислены ниже. Покрытие пар последовательных "
        "переходов (1-switch) требует по тесту на каждую пару «переход, за которым сразу идёт "
        "следующий». Сколько всего таких пар и сколько из них начинается переходом из состояния "
        f"«{start}»? Ответ — два числа через пробел."
    )
    params = {"transitions": [list(t) for t in ordered], "start": start}
    return Instance(prompt, f"{len(pairs)} {from_start}", params, code=code)


def traceability(rng: random.Random) -> Instance:
    reqs = [f"R{i}" for i in range(1, 6)]
    tests = {f"T{i}": sorted(rng.sample(reqs, rng.randint(1, 2))) for i in range(1, 6)}
    results = {t: rng.random() < 0.7 for t in tests}
    statuses = []
    for r in reqs:
        covering = [t for t, rs in tests.items() if r in rs]
        if not covering:
            statuses.append("Н")
        elif all(results[t] for t in covering):
            statuses.append("П")
        else:
            statuses.append("У")
    lines = [
        f"{t}: проверяет {', '.join(rs)} — {'прошёл' if results[t] else 'упал'}"
        for t, rs in tests.items()
    ]
    prompt = (
        "Матрица трассировки: какие требования проверяет каждый тест и чем закончился прогон. "
        "Каков статус требований R1–R5? Ответ — по букве на требование подряд: П — все его "
        "тесты прошли, У — хотя бы один упал, Н — не покрыто тестами."
    )
    params = {"tests": tests, "results": results}
    return Instance(prompt, "".join(statuses), params, code="\n".join(lines))


def pairwise_coverage(rng: random.Random) -> Instance:
    params_values = {
        "браузер": ["Chrome", "Firefox", "Safari"][: rng.randint(2, 3)],
        "ОС": ["Windows", "macOS", "Linux"][: rng.randint(2, 3)],
        "язык": ["ru", "en"],
        "сеть": ["Wi-Fi", "LTE", "3G"][: rng.randint(2, 3)],
    }
    names = list(params_values)
    tests = [tuple(rng.choice(params_values[n]) for n in names) for _ in range(rng.randint(3, 7))]
    needed = sum(
        len(params_values[a]) * len(params_values[b]) for a, b in itertools.combinations(names, 2)
    )
    covered = {
        (i, j, t[i], t[j]) for t in tests for i, j in itertools.combinations(range(len(names)), 2)
    }
    lines = [f"{k}. " + ", ".join(t) for k, t in enumerate(tests, 1)]
    values = "; ".join(f"{n}: {', '.join(v)}" for n, v in params_values.items())
    prompt = (
        f"Параметры конфигурации: {values}. Попарное тестирование требует, чтобы каждая пара "
        "значений любых двух параметров встретилась хотя бы в одном тесте. Сколько всего таких "
        "пар и сколько из них покрывает набор тестов ниже? Ответ — два числа через пробел."
    )
    params = {"values": params_values, "tests": tests}
    return Instance(prompt, f"{needed} {len(covered)}", params, code="\n".join(lines))


def defect_removal(rng: random.Random) -> Instance:
    found = rng.randint(40, 300)
    escaped = rng.randint(2, 60)
    kloc = rng.randint(10, 120)
    dre = 100 * found / (found + escaped)
    density = escaped / kloc
    prompt = (
        f"До релиза команда нашла {found} дефектов, после релиза пользователи нашли ещё "
        f"{escaped}. В релизе {kloc} тысяч строк кода. Какова эффективность устранения "
        "дефектов (DRE, % найденных до релиза от всех) и плотность пропущенных дефектов на "
        "тысячу строк? Ответ — два числа через пробел, оба округлите до десятых."
    )
    return Instance(
        prompt,
        f"{rounded(dre, 1)} {rounded(density, 1)}",
        {"found": found, "escaped": escaped, "kloc": kloc},
    )
