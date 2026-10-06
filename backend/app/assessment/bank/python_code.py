"""Язык программирования: «что выведет код». Эталон — вывод самого листинга."""

import random
from typing import Any

from app.assessment.bank.family import Instance

PROMPT = "Что выведет программа на Python? Ответ — то, что появится в консоли."


def run_python(code: str) -> str:
    """Исполняет сгенерированный листинг и возвращает его вывод без хвостовых пробелов."""
    out: list[str] = []

    def capture(*args: Any, sep: str = " ", end: str = "\n") -> None:
        out.append(sep.join(str(a) for a in args) + end)

    exec(code, {"print": capture})
    return "".join(out).strip()


def arithmetic(rng: random.Random) -> Instance:
    x, y, z = rng.randint(40, 199), rng.randint(3, 9), rng.randint(2, 7)
    code = f"x = {x}\ny = {y}\nx = x // y\ny = x % {z} + y\nprint(x + y)\n"
    return Instance(PROMPT, run_python(code), {"x": x, "y": y, "z": z}, code=code)


def slicing(rng: random.Random) -> Instance:
    nums = [rng.randint(1, 60) for _ in range(9)]
    start, stop = rng.randint(0, 3), rng.randint(5, 9)
    factor = rng.randint(2, 5)
    code = (
        f"nums = {nums}\n"
        f"picked = [n * {factor} for n in nums[{start}:{stop}] if n % 2 == 0]\n"
        "print(sum(picked[::2]))\n"
    )
    params = {"nums": nums, "start": start, "stop": stop, "factor": factor}
    return Instance(PROMPT, run_python(code), params, code=code)


def mutable_default(rng: random.Random) -> Instance:
    values = rng.sample(range(2, 40), 5)
    fresh = rng.sample(range(4), rng.randint(1, 2))
    calls = [f"add({v}, [])" if i in fresh else f"add({v})" for i, v in enumerate(values[:4])]
    code = (
        "def add(item, bucket=[]):\n"
        "    bucket.append(item)\n"
        "    return bucket\n\n" + "\n".join(calls) + f"\nprint(sum(add({values[4]})))\n"
    )
    return Instance(PROMPT, run_python(code), {"values": values, "fresh": fresh}, code=code)


def late_binding(rng: random.Random) -> Instance:
    n, k, x = rng.randint(3, 6), rng.randint(1, 9), rng.randint(2, 9)
    if rng.random() < 0.5:
        build = f"funcs = []\nfor i in range({n}):\n    funcs.append(lambda x: x * i + {k})\n"
    else:
        build = f"funcs = [lambda x: x * i + {k} for i in range({n})]\n"
    code = build + f"print(sum(f({x}) for f in funcs))\n"
    return Instance(PROMPT, run_python(code), {"n": n, "k": k, "x": x}, code=code)
