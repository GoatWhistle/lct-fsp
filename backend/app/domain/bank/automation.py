"""Автоматизация тестирования на pytest: сбор тестов, параметризация, фикстуры."""

import random

from app.domain.bank.family import Instance, rounded

PROMPT = "Сколько тестов соберёт pytest из этого файла? Ответ — целое число."


def _plain_tests(rng: random.Random, count: int, start: int = 1) -> list[str]:
    return [
        f"def test_case_{start + i}():\n    assert check({rng.randint(1, 99)})\n"
        for i in range(count)
    ]


def parametrize_count(rng: random.Random) -> Instance:
    plain, values = rng.randint(2, 5), rng.sample(range(1, 50), rng.randint(3, 7))
    code = "import pytest\n\n" + "\n".join(_plain_tests(rng, plain))
    code += f'\n@pytest.mark.parametrize("x", {values})\ndef test_values(x):\n    assert check(x)\n'
    return Instance(PROMPT, str(plain + len(values)), {"plain": plain, "values": values}, code=code)


def stacked_parametrize(rng: random.Random) -> Instance:
    xs, ys = (
        rng.sample(range(1, 20), rng.randint(2, 4)),
        rng.sample(range(20, 40), rng.randint(2, 4)),
    )
    marked = rng.randint(1, 3)
    params = [
        f"pytest.param({v}, marks=pytest.mark.skip)" if i < marked else str(v)
        for i, v in enumerate(rng.sample(range(40, 60), marked + rng.randint(1, 3)))
    ]
    code = (
        "import pytest\n\n"
        f'@pytest.mark.parametrize("x", {xs})\n'
        f'@pytest.mark.parametrize("y", {ys})\n'
        "def test_pair(x, y):\n    assert check(x, y)\n\n"
        f'@pytest.mark.parametrize("z", [{", ".join(params)}])\n'
        "def test_single(z):\n    assert check(z)\n"
    )
    prompt = "Сколько тестов pytest выполнит, не считая пропущенных? Ответ — целое число."
    answer = len(xs) * len(ys) + len(params) - marked
    return Instance(prompt, str(answer), {"xs": xs, "ys": ys, "params": params}, code=code)


SCOPES = ["function", "module", "session"]


def fixture_scope(rng: random.Random) -> Instance:
    scope = rng.choice(SCOPES)
    modules = [rng.randint(0, 4) for _ in range(3)]
    if not any(modules):
        modules[0] = 2
    users = sum(modules)
    setups = {
        "function": users,
        "module": sum(1 for m in modules if m),
        "session": 1,
    }[scope]
    code = (
        f'@pytest.fixture(scope="{scope}")\n'
        "def database():\n    db = connect()   # подготовка\n    yield db\n    db.close()\n"
    )
    files = ", ".join(
        f"test_{name}.py — {m}" for name, m in zip(("a", "b", "c"), modules, strict=True)
    )
    prompt = (
        f"Фикстура лежит в conftest.py. Тестов, которые её запрашивают: {files}; в каждом файле "
        "есть и тесты без неё. Сколько раз выполнится connect() за прогон всех тестов?"
    )
    return Instance(prompt, str(setups), {"scope": scope, "modules": modules}, code=code)


def parametrized_fixture(rng: random.Random) -> Instance:
    scope = rng.choice(["function", "module"])
    params = rng.sample(["sqlite", "postgres", "mysql", "oracle"], rng.randint(2, 4))
    modules = [rng.randint(1, 4), rng.randint(0, 4)]
    tests = sum(modules)
    setups = len(params) * (tests if scope == "function" else sum(1 for m in modules if m))
    code = (
        f'@pytest.fixture(scope="{scope}", params={params})\n'
        "def database(request):\n    db = connect(request.param)   # подготовка\n"
        "    yield db\n    db.close()\n"
    )
    prompt = (
        f"Фикстура лежит в conftest.py. Тестов, которые её запрашивают: test_a.py — {modules[0]}, "
        f"test_b.py — {modules[1]}. Сколько раз выполнится connect() за прогон всех тестов?"
    )
    data = {"scope": scope, "params": params, "modules": modules}
    return Instance(prompt, str(setups), data, code=code)


def collect_count(rng: random.Random) -> Instance:
    plain = rng.randint(1, 5)
    values = rng.sample(range(1, 50), rng.randint(2, 8))
    in_class = rng.randint(1, 4)
    skipped = rng.randint(0, 2)
    code = "import pytest\n\n" + "\n".join(_plain_tests(rng, plain))
    code += "\ndef helper_case():\n    return check(0)\n"
    code += f'\n@pytest.mark.parametrize("x", {values})\ndef test_values(x):\n    assert check(x)\n'
    code += "\nclass TestCart:\n" + "".join(
        f"    def test_item_{i}(self):\n        assert check({i})\n\n" for i in range(in_class)
    )
    code += "\nclass Helpers:\n    def test_unused(self):\n        assert check(-1)\n"
    code += "".join(
        f'\n@pytest.mark.skip(reason="позже")\ndef test_later_{i}():\n    assert check({i})\n'
        for i in range(skipped)
    )
    collected = plain + len(values) + in_class + skipped
    prompt = (
        "Файл называется test_cart.py, настройки pytest по умолчанию. Сколько тестов pytest "
        "соберёт и сколько из них выполнит (не пропустит)? Ответ — два числа через пробел."
    )
    params = {"plain": plain, "values": values, "in_class": in_class, "skipped": skipped}
    return Instance(prompt, f"{collected} {collected - skipped}", params, code=code)


def stacked_count(rng: random.Random) -> Instance:
    xs = rng.sample(range(1, 20), rng.randint(2, 4))
    ys = rng.sample(range(20, 40), rng.randint(2, 4))
    marked = rng.randint(0, 3)
    params = [
        f"pytest.param({v}, marks=pytest.mark.skip)" if i < marked else str(v)
        for i, v in enumerate(rng.sample(range(40, 60), marked + rng.randint(1, 3)))
    ]
    code = (
        "import pytest\n\n"
        f'@pytest.mark.parametrize("x", {xs})\n'
        f'@pytest.mark.parametrize("y", {ys})\n'
        "def test_pair(x, y):\n    assert check(x, y)\n\n"
        f'@pytest.mark.parametrize("z", [{", ".join(params)}])\n'
        "def test_single(z):\n    assert check(z)\n"
    )
    collected = len(xs) * len(ys) + len(params)
    prompt = (
        "Сколько тестов pytest соберёт и сколько из них пропустит? Ответ — два числа через пробел."
    )
    return Instance(
        prompt, f"{collected} {marked}", {"xs": xs, "ys": ys, "params": params}, code=code
    )


TEST_MARKS = ["smoke", "slow", "api", "ui", "regress"]


def _marked_tests(rng: random.Random) -> list[tuple[str, set[str]]]:
    names = rng.sample(["login", "cart", "pay", "search", "profile", "export", "order", "admin"], 6)
    return [(name, set(rng.sample(TEST_MARKS, rng.randint(0, 2)))) for name in names]


def marker_selection(rng: random.Random) -> Instance:
    tests = _marked_tests(rng)
    a, b = rng.sample(TEST_MARKS, 2)
    kind = rng.randrange(3)
    expression = [f"{a} and not {b}", f"{a} or {b}", f"not {a}"][kind]

    def check(marks: set[str]) -> bool:
        if kind == 0:
            return a in marks and b not in marks
        if kind == 1:
            return a in marks or b in marks
        return a not in marks

    selected = [name for name, marks in tests if check(marks)]
    code = "import pytest\n\n" + "\n".join(
        "".join(f"@pytest.mark.{m}\n" for m in sorted(marks)) + f"def test_{name}():\n    ...\n"
        for name, marks in tests
    )
    prompt = (
        f'Какие тесты выполнит pytest -m "{expression}"? Ответ — имена без test_ через пробел '
        "в порядке файла; если ни один — 0."
    )
    params = {"tests": [[n, sorted(m)] for n, m in tests], "expression": expression}
    return Instance(prompt, " ".join(selected) or "0", params, code=code)


def keyword_selection(rng: random.Random) -> Instance:
    words = ["login", "logout", "cart", "card", "pay", "payment", "order", "orders"]
    names = [
        f"test_{rng.choice(words)}_{rng.choice(['ok', 'fail', 'empty', 'big'])}" for _ in range(6)
    ]
    names = list(dict.fromkeys(names))
    # Слова выражения берём из имён и перебираем, пока выражение что-то выбирает: пустой ответ
    # слишком частый и угадывается.
    used = sorted({w for n in names for w in words if w in n})
    selected: list[str] = []
    expression = ""
    while not selected:
        a = rng.choice(used)
        b = rng.choice([w for w in words if w != a])
        kind = rng.randrange(3)
        expression = [f"{a} and not {b}", f"{a} or {b}", f"{a} and ok"][kind]
        selected = [
            n.removeprefix("test_")
            for n in names
            if (kind == 0 and a in n and b not in n)
            or (kind == 1 and (a in n or b in n))
            or (kind == 2 and a in n and "ok" in n)
        ]
    code = "\n".join(f"def {n}():\n    ...\n" for n in names)
    prompt = (
        f'Файл называется test_shop.py. Какие тесты выполнит pytest -k "{expression}"? -k ищет '
        "подстроки в именах. Ответ — имена без test_ через пробел в порядке файла."
    )
    return Instance(
        prompt, " ".join(selected), {"names": names, "expression": expression}, code=code
    )


def xfail_outcomes(rng: random.Random) -> Instance:
    tests = []
    counts = {"passed": 0, "failed": 0, "xfailed": 0, "xpassed": 0}
    for i in range(1, rng.randint(6, 9)):
        passes = rng.random() < 0.5
        mark = rng.choice(["", "", "xfail", "xfail_strict"])
        if mark == "":
            counts["passed" if passes else "failed"] += 1
            deco = ""
        elif mark == "xfail":
            counts["xpassed" if passes else "xfailed"] += 1
            deco = '@pytest.mark.xfail(reason="баг 42")\n'
        else:
            counts["failed" if passes else "xfailed"] += 1
            deco = '@pytest.mark.xfail(strict=True, reason="баг 42")\n'
        tests.append(f"{deco}def test_{i}():\n    assert {'True' if passes else 'False'}\n")
    code = "import pytest\n\n" + "\n".join(tests)
    prompt = (
        "Каким будет итог pytest? Ответ — четыре числа через пробел: passed, failed, xfailed, "
        "xpassed."
    )
    answer = " ".join(str(counts[k]) for k in ("passed", "failed", "xfailed", "xpassed"))
    return Instance(prompt, answer, {"tests": tests}, code=code)


def fixture_setups(rng: random.Random) -> Instance:
    modules = [rng.randint(0, 6) for _ in range(4)]
    if not any(modules):
        modules[0] = 3
    files = ", ".join(f"test_{name}.py — {m}" for name, m in zip("abcd", modules, strict=True))
    code = (
        "@pytest.fixture(scope=SCOPE)\n"
        "def database():\n    db = connect()   # подготовка\n    yield db\n    db.close()\n"
    )
    prompt = (
        f"Фикстура лежит в conftest.py. Тестов, которые её запрашивают: {files}; в каждом файле "
        "есть и тесты без неё. Сколько раз выполнится connect() за прогон всех тестов при SCOPE "
        '= "function", "module" и "session"? Ответ — три числа через пробел.'
    )
    answer = f"{sum(modules)} {sum(1 for m in modules if m)} 1"
    return Instance(prompt, answer, {"modules": modules}, code=code)


def conftest_override(rng: random.Random) -> Instance:
    values = rng.sample(range(10, 99), 3)
    defined = {
        "conftest.py (корень)": values[0],
        "tests/api/conftest.py": values[1],
        "tests/api/test_orders.py": values[2],
    }
    present = [k for k in defined if k == "conftest.py (корень)" or rng.random() < 0.6]
    files = ["tests/test_home.py", "tests/api/test_orders.py", "tests/api/test_users.py"]
    seen = []
    for f in files:
        if f == "tests/api/test_orders.py" and "tests/api/test_orders.py" in present:
            seen.append(defined["tests/api/test_orders.py"])
        elif f.startswith("tests/api/") and "tests/api/conftest.py" in present:
            seen.append(defined["tests/api/conftest.py"])
        else:
            seen.append(defined["conftest.py (корень)"])
    code = "\n".join(
        f"# {where}\n@pytest.fixture\ndef limit():\n    return {defined[where]}\n"
        for where in present
    )
    prompt = (
        "Фикстура limit определена в файлах ниже. Тест test_limit(limit) есть в "
        f"{', '.join(files)}. Какое значение limit получит тест в каждом файле? Ответ — три "
        "числа через пробел в порядке файлов."
    )
    return Instance(
        prompt, " ".join(map(str, seen)), {"present": present, "values": values}, code=code
    )


def explicit_wait(rng: random.Random) -> Instance:
    timeout = rng.randint(3, 20)
    poll = rng.choice([0.25, 0.5, 1.0])
    appears = rng.randint(1, 100) / 4
    steps = [i * poll for i in range(int(timeout / poll) + 1)]
    found = next((t for t in steps if t >= appears), None)
    answer = f"{found:g}" if found is not None else f"{timeout:g}"
    status = "найден" if found is not None else "TimeoutException"
    code = (
        "from selenium.webdriver.support.ui import WebDriverWait\n"
        "from selenium.webdriver.support import expected_conditions as EC\n\n"
        f"wait = WebDriverWait(driver, timeout={timeout}, poll_frequency={poll})\n"
        "button = wait.until(EC.element_to_be_clickable(PAY_BUTTON))\n"
    )
    prompt = (
        f"Кнопка становится кликабельной через {appears:g} с после начала ожидания. Условие "
        "проверяется сразу и затем через каждые poll_frequency секунд; поиск мгновенный. Через "
        "сколько секунд закончится ожидание и чем — «найден» или TimeoutException? Ответ — "
        "число и слово через пробел."
    )
    params = {"timeout": timeout, "poll": poll, "appears": appears}
    return Instance(prompt, f"{answer} {status}", params, code=code)


def parametrized_setups(rng: random.Random) -> Instance:
    params = rng.sample(["sqlite", "postgres", "mysql", "oracle"], rng.randint(2, 4))
    modules = [rng.randint(1, 5), rng.randint(0, 5), rng.randint(0, 3)]
    tests = sum(modules)
    code = (
        "@pytest.fixture(scope=SCOPE, params=" + repr(params) + ")\n"
        "def database(request):\n    db = connect(request.param)   # подготовка\n"
        "    yield db\n    db.close()\n"
    )
    prompt = (
        "Фикстура лежит в conftest.py. Тестов, которые её запрашивают: test_a.py — "
        f"{modules[0]}, test_b.py — {modules[1]}, test_c.py — {modules[2]}. Сколько тестов "
        'соберёт pytest с этой фикстурой и сколько раз выполнится connect() при SCOPE = "function" '
        'и при SCOPE = "module"? Ответ — три числа через пробел.'
    )
    answer = (
        f"{tests * len(params)} {tests * len(params)} {len(params) * sum(1 for m in modules if m)}"
    )
    return Instance(prompt, answer, {"params": params, "modules": modules}, code=code)


def xdist_duration(rng: random.Random) -> Instance:
    import heapq

    workers = rng.randint(2, 4)
    durations = [rng.randint(1, 20) for _ in range(rng.randint(6, 9))]
    free = [0] * workers
    for d in durations:
        start = heapq.heappop(free)
        heapq.heappush(free, start + d)
    prompt = (
        f"Тесты длятся {', '.join(map(str, durations))} с (в порядке сбора). Их запускают "
        f"pytest -n {workers} --dist load: освободившийся воркер сразу берёт следующий тест по "
        "порядку. Сколько секунд займёт прогон и во сколько раз он быстрее последовательного? "
        "Ответ — два числа через пробел, второе округлите до сотых."
    )
    total = max(free)
    answer = f"{total} {rounded(sum(durations) / total, 2)}"
    return Instance(prompt, answer, {"workers": workers, "durations": durations})
