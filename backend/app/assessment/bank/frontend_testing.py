"""Тестирование интерфейсов: матчеры и моки Jest, фейковые таймеры, запросы Testing Library,
асинхронные тесты, визуальное сравнение, шардирование e2e, пороги покрытия, повторы Playwright."""

import random

from app.assessment.bank.family import Instance, rounded


def jest_matchers(rng: random.Random) -> Instance:
    rows = []
    for _ in range(6):
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        rows.append(
            rng.choice(
                [
                    (f"expect({a} + {b}).toBe({a + b})", True),
                    (f"expect({{ id: {a} }}).toBe({{ id: {a} }})", False),
                    (f"expect({{ id: {a} }}).toEqual({{ id: {a} }})", True),
                    (f"expect([{a}, {b}]).toEqual([{b}, {a}])", a == b),
                    (f"expect({{ id: {a}, tag: undefined }}).toEqual({{ id: {a} }})", True),
                    (f"expect({{ id: {a}, tag: undefined }}).toStrictEqual({{ id: {a} }})", False),
                    (f"expect('{a}{b}').toBe({a}{b})", False),
                    (f"expect([{a}, {b}]).toContain({b})", True),
                    ("expect(0.1 + 0.2).toBeCloseTo(0.3)", True),
                    ("expect(0.1 + 0.2).toBe(0.3)", False),
                ]
            )
        )
    code = "\n".join(f"test('{i}', () => {{ {text}; }});" for i, (text, _) in enumerate(rows, 1))
    failing = [i for i, (_, ok) in enumerate(rows, 1) if not ok]
    prompt = "Какие тесты упадут? Ответ — номера через пробел; если ни один — 0."
    return Instance(
        prompt, " ".join(map(str, failing)) or "0", {"rows": [t for t, _ in rows]}, code=code
    )


def jest_focus(rng: random.Random) -> Instance:
    tests = []
    for i in range(1, rng.randint(7, 10)):
        kind = rng.choice(["test", "test", "test.skip", "test.only", "test.todo"])
        tests.append((i, kind))
    has_only = any(kind == "test.only" for _, kind in tests)
    ran = sum(1 for _, kind in tests if kind == "test.only" or (kind == "test" and not has_only))
    todo = sum(1 for _, kind in tests if kind == "test.todo")
    skipped = len(tests) - ran - todo
    code = "\n".join(
        f"{kind}('case {i}');"
        if kind == "test.todo"
        else f"{kind}('case {i}', () => {{ expect(sum({i}, 1)).toBe({i + 1}); }});"
        for i, kind in tests
    )
    prompt = (
        "Jest запускает этот файл. Сколько тестов выполнится, сколько будет пропущено (skipped) "
        "и сколько отмечено todo? Ответ — три числа через пробел."
    )
    return Instance(prompt, f"{ran} {skipped} {todo}", {"tests": tests}, code=code)


def mock_returns(rng: random.Random) -> Instance:
    once = [rng.randint(1, 99) for _ in range(rng.randint(1, 3))]
    default = rng.choice([None, rng.randint(1, 99)])
    calls = rng.randint(len(once) + 1, len(once) + 3)
    chain = (
        "jest.fn()"
        + ("" if default is None else f".mockReturnValue({default})")
        + "".join(f".mockReturnValueOnce({v})" for v in once)
    )
    results = [
        str(once[i]) if i < len(once) else ("undefined" if default is None else str(default))
        for i in range(calls)
    ]
    code = (
        f"const price = {chain};\n"
        f"const seen = [{', '.join('price()' for _ in range(calls))}];\n"
        "console.log(seen.join(' '), price.mock.calls.length);\n"
    )
    prompt = (
        "Что выведет console.log? Пустые значения join выводит как пустую строку. Ответ — то, "
        "что в консоли."
    )
    # join превращает undefined в пустую строку: значения склеиваются через пробелы.
    printed = " ".join("" if r == "undefined" else r for r in results)
    answer = " ".join([*printed.split(), str(calls)])
    return Instance(prompt, answer, {"once": once, "default": default, "calls": calls}, code=code)


def fake_timers(rng: random.Random) -> Instance:
    timeout = rng.randrange(100, 2000, 100)
    interval = rng.randrange(100, 1000, 50)
    advances = [rng.randrange(100, 1500, 50) for _ in range(rng.randint(2, 3))]
    total = 0
    timeout_calls, interval_calls = [], []
    for step in advances:
        total += step
        timeout_calls.append(1 if total >= timeout else 0)
        interval_calls.append(total // interval)
    code = (
        "jest.useFakeTimers();\n"
        "const onTimeout = jest.fn();\n"
        "const onTick = jest.fn();\n"
        f"setTimeout(onTimeout, {timeout});\n"
        f"setInterval(onTick, {interval});\n"
        + "".join(
            f"jest.advanceTimersByTime({step});\n"
            "console.log(onTimeout.mock.calls.length, onTick.mock.calls.length);\n"
            for step in advances
        )
    )
    answer = " ".join(f"{a} {b}" for a, b in zip(timeout_calls, interval_calls, strict=True))
    prompt = "Что выведут console.log? Ответ — все числа через пробел по порядку."
    return Instance(
        prompt, answer, {"timeout": timeout, "interval": interval, "advances": advances}, code=code
    )


def rtl_queries(rng: random.Random) -> Instance:
    rows = []
    for _ in range(5):
        variant = rng.choice(["getBy", "queryBy", "getAllBy", "queryAllBy"])
        matches = rng.choice([0, 1, 2, 3])
        if variant == "getBy":
            outcome = "элемент" if matches == 1 else "ошибка"
        elif variant == "queryBy":
            outcome = "элемент" if matches == 1 else "null" if matches == 0 else "ошибка"
        elif variant == "getAllBy":
            outcome = str(matches) if matches else "ошибка"
        else:
            outcome = str(matches)
        rows.append((variant, matches, outcome))
    lines = [
        f"{i}. screen.{v}Role('button') — на странице кнопок: {m}"
        for i, (v, m, _) in enumerate(rows, 1)
    ]
    prompt = (
        "Что вернёт каждый запрос Testing Library? Ответ — по значению на запрос через пробел: "
        "«элемент», «null», «ошибка» (бросит исключение) или длина массива."
    )
    return Instance(prompt, " ".join(o for _, _, o in rows), {"rows": rows}, code="\n".join(lines))


def async_pitfalls(rng: random.Random) -> Instance:
    cases = []
    for i in range(1, 7):
        resolves = rng.random() < 0.5
        style = rng.choice(["await", "return", "forget", "done"])
        # Тест ловит отклонение промиса, только если Jest его дождался.
        waits = style in ("await", "return", "done")
        failed = waits and not resolves
        if style == "await":
            body = "await expect(load()).resolves.toBe(7);"
            head = "async () =>"
        elif style == "return":
            body = "return expect(load()).resolves.toBe(7);"
            head = "() =>"
        elif style == "forget":
            body = "expect(load()).resolves.toBe(7);"
            head = "() =>"
        else:
            body = "load().then(v => { expect(v).toBe(7); done(); }, done);"
            head = "(done) =>"
        cases.append((i, resolves, head, body, failed))
    code = "\n".join(
        f"// load() в тесте {i} {'выполняется с 7' if ok else 'отклоняется с ошибкой'}\n"
        f"test('{i}', {head} {{ {body} }});"
        for i, ok, head, body, _ in cases
    )
    failing = [i for i, _, _, _, failed in cases if failed]
    prompt = (
        "Какие тесты Jest покажет упавшими? Отклонённый промис, которого тест не дождался, "
        "на результат этого теста не влияет. Ответ — номера через пробел; если ни один — 0."
    )
    return Instance(
        prompt,
        " ".join(map(str, failing)) or "0",
        {"cases": [[c[0], c[1], c[3]] for c in cases]},
        code=code,
    )


def visual_diff(rng: random.Random) -> Instance:
    width, height = rng.choice([(1280, 720), (800, 600), (375, 812)])
    threshold = rng.choice([0.1, 0.2, 0.5, 1.0])
    shots = []
    for _ in range(4):
        diff = rng.randint(0, width * height // 100)
        shots.append(diff)
    ratios = [100 * diff / (width * height) for diff in shots]
    passed = [i for i, r in enumerate(ratios, 1) if r <= threshold]
    lines = [f"{i}. отличается пикселей: {d}" for i, d in enumerate(shots, 1)]
    prompt = (
        f"Скриншоты {width}×{height} сравниваются с эталоном; снимок проходит, если доля "
        f"отличающихся пикселей не больше {threshold} %. Какая доля отличий у каждого снимка и "
        "какие пройдут? Ответ — четыре доли в процентах, округлённые до сотых, затем номера "
        "прошедших снимков (или 0, если ни один); всё через пробел."
    )
    answer = (
        " ".join(f"{rounded(r, 2)}" for r in ratios) + " " + (" ".join(map(str, passed)) or "0")
    )
    params = {"size": [width, height], "threshold": threshold, "shots": shots}
    return Instance(prompt, answer, params, code="\n".join(lines))


def test_shards(rng: random.Random) -> Instance:
    shards = rng.randint(2, 4)
    durations = [rng.randint(5, 90) for _ in range(rng.randint(7, 10))]
    # Как Playwright --shard: тесты делятся по порядку на равные по числу части, первые части
    # получают на тест больше, если не делится нацело.
    size, extra = divmod(len(durations), shards)
    totals, start = [], 0
    for k in range(shards):
        count = size + (1 if k < extra else 0)
        totals.append(sum(durations[start : start + count]))
        start += count
    prompt = (
        f"Тесты длятся {', '.join(map(str, durations))} с в порядке файла. CI запускает "
        f"{shards} шарда параллельно; тесты делятся по порядку на части равного размера, первые "
        "части получают по лишнему тесту, если не делится нацело. Сколько секунд идёт каждый "
        "шард? Ответ — числа через пробел по порядку шардов."
    )
    return Instance(prompt, " ".join(map(str, totals)), {"shards": shards, "durations": durations})


def coverage_thresholds(rng: random.Random) -> Instance:
    files = rng.sample(["Cart.tsx", "api.ts", "useAuth.ts", "format.ts", "Checkout.tsx"], 3)
    rows = []
    for name in files:
        lines_total = rng.randint(20, 200)
        branches_total = rng.randint(4, 40)
        rows.append(
            (
                name,
                rng.randint(lines_total // 2, lines_total),
                lines_total,
                rng.randint(branches_total // 3, branches_total),
                branches_total,
            )
        )
    lines_pct = 100 * sum(r[1] for r in rows) / sum(r[2] for r in rows)
    branches_pct = 100 * sum(r[3] for r in rows) / sum(r[4] for r in rows)
    need_lines, need_branches = rng.choice([70, 80, 85]), rng.choice([60, 70, 80])
    # Глобальный порог Jest сравнивает суммарное покрытие по всем файлам, а не среднее файлов.
    fails = lines_pct < need_lines or branches_pct < need_branches
    lines = [
        f"{name}: строки {covered}/{total}, ветви {b_covered}/{b_total}"
        for name, covered, total, b_covered, b_total in rows
    ]
    prompt = (
        f"В jest.config: coverageThreshold: {{ global: {{ lines: {need_lines}, branches: "
        f"{need_branches} }} }}. Отчёт покрытия по файлам ниже, других файлов нет. Каково "
        "суммарное покрытие строк и ветвей и упадёт ли прогон из-за порога? Ответ — два "
        "процента, округлённые до десятых, и «да» или «нет» через пробел."
    )
    return Instance(
        prompt,
        f"{rounded(lines_pct, 1)} {rounded(branches_pct, 1)} {'да' if fails else 'нет'}",
        {"rows": rows, "lines": need_lines, "branches": need_branches},
        code="\n".join(lines),
    )


def playwright_retries(rng: random.Random) -> Instance:
    retries = rng.randint(1, 3)
    tests = []
    for i in range(1, rng.randint(5, 7) + 1):
        attempts = []
        for _ in range(retries + 1):
            ok = rng.random() < 0.55
            attempts.append(ok)
            if ok:
                break
        tests.append((f"test-{i}", attempts))
    passed = sum(1 for _, a in tests if a == [True])
    flaky = sum(1 for _, a in tests if a[-1] and len(a) > 1)
    failed = sum(1 for _, a in tests if not a[-1])
    runs = sum(len(a) for _, a in tests)
    lines = [
        f"{name}: " + ", ".join("прошёл" if ok else "упал" for ok in attempts)
        for name, attempts in tests
    ]
    prompt = (
        f"В playwright.config retries: {retries}. Ниже — исходы попыток каждого теста по порядку "
        "(после успешной попытки повторов нет). Что покажет отчёт: сколько тестов passed, "
        "flaky и failed и сколько всего было запусков? Ответ — четыре числа через пробел."
    )
    return Instance(
        prompt,
        f"{passed} {flaky} {failed} {runs}",
        {"retries": retries, "tests": tests},
        code="\n".join(lines),
    )
