"""Автоматизация тестирования на pytest: сбор тестов, параметризация, фикстуры."""

import random

from app.assessment.bank.family import Instance

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
