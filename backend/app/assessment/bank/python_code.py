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


WORDS = [
    "backend",
    "service",
    "request",
    "payload",
    "cluster",
    "gateway",
    "handler",
    "session",
    "context",
    "storage",
    "replica",
    "monitor",
    "adapter",
    "channel",
    "message",
    "profile",
    "routine",
    "account",
    "reports",
    "invoice",
    "catalog",
    "pipeline",
    "scanner",
    "builder",
]


def string_methods(rng: random.Random) -> Instance:
    word = rng.choice(WORDS)
    pad, start = rng.randint(1, 3), rng.randint(0, 3)
    stop = rng.randint(start + 2, len(word))
    code = (
        f"word = {' ' * pad + word + ' ' * pad!r}\n"
        f"word = word.strip()[::-1].upper()\n"
        f"print(word[{start}:{stop}] + str(len(word)))\n"
    )
    params = {"word": word, "pad": pad, "start": start, "stop": stop}
    return Instance(PROMPT, run_python(code), params, code=code)


def dict_counting(rng: random.Random) -> Instance:
    letters = "".join(rng.choice("abcde") for _ in range(rng.randint(11, 15)))
    code = (
        f"text = {letters!r}\n"
        "counts = {}\n"
        "for ch in text:\n"
        "    counts[ch] = counts.get(ch, 0) + 1\n"
        "order = sorted(counts, key=lambda ch: (-counts[ch], ch))\n"
        "print(''.join(order) + str(counts[order[0]]))\n"
    )
    return Instance(PROMPT, run_python(code), {"text": letters}, code=code)


def collatz_steps(rng: random.Random) -> Instance:
    n = rng.randint(12, 260)
    code = (
        f"n = {n}\n"
        "steps = 0\n"
        "while n != 1:\n"
        "    n = n // 2 if n % 2 == 0 else 3 * n + 1\n"
        "    steps += 1\n"
        "print(steps)\n"
    )
    return Instance(PROMPT, run_python(code), {"n": n}, code=code)


def comprehension_filter(rng: random.Random) -> Instance:
    nums = [rng.randint(-9, 25) for _ in range(8)]
    k, r = rng.randint(2, 4), 0
    r = rng.randrange(k)
    code = (
        f"nums = {nums}\n"
        f"squares = [x * x for x in nums if x % {k} == {r}]\n"
        "print(sum(squares) - len(squares))\n"
    )
    return Instance(PROMPT, run_python(code), {"nums": nums, "k": k, "r": r}, code=code)


def closure_counter(rng: random.Random) -> Instance:
    start, a1, b1, a2, b2 = (rng.randint(1, 30) for _ in range(5))
    code = (
        "def make_counter(start):\n"
        "    count = start\n"
        "    def step(delta):\n"
        "        nonlocal count\n"
        "        count += delta\n"
        "        return count\n"
        "    return step\n\n"
        f"first = make_counter({start})\n"
        f"second = make_counter({start})\n"
        f"first({a1})\n"
        f"second({b1})\n"
        f"print(first({a2}) * 2 + second({b2}))\n"
    )
    params = {"start": start, "deltas": [a1, b1, a2, b2]}
    return Instance(PROMPT, run_python(code), params, code=code)


def generator_exhaustion(rng: random.Random) -> Instance:
    n, k, skip = rng.randint(6, 14), rng.randint(2, 9), rng.randint(1, 3)
    code = (
        f"gen = (x * {k} for x in range({n}))\n"
        + "".join("next(gen)\n" for _ in range(skip))
        + "total = sum(gen)\n"
        "print(total + sum(gen))\n"
    )
    return Instance(PROMPT, run_python(code), {"n": n, "k": k, "skip": skip}, code=code)


def exception_finally(rng: random.Random) -> Instance:
    limit, a, b, c, d = rng.randint(3, 9), *(rng.randint(2, 20) for _ in range(4))
    xs = [rng.randint(0, 12) for _ in range(3)]
    code = (
        "log = []\n\n"
        "def f(x):\n"
        "    try:\n"
        f"        if x > {limit}:\n"
        "            raise ValueError(x)\n"
        f"        result = x + {a}\n"
        "    except ValueError:\n"
        f"        result = {b}\n"
        "        return result\n"
        "    else:\n"
        f"        result += {c}\n"
        "    finally:\n"
        f"        log.append(x)\n"
        f"        result = {d}\n"
        "    return result\n\n"
        f"print(sum(f(x) for x in {xs}) + len(log))\n"
    )
    params = {"limit": limit, "a": a, "b": b, "c": c, "d": d, "xs": xs}
    return Instance(PROMPT, run_python(code), params, code=code)


def mro_super(rng: random.Random) -> Instance:
    names = rng.sample("KLMNPRST", 4)
    base, left, right, child = names
    digits = rng.sample(range(1, 10), 4)
    bases = [left, right] if rng.random() < 0.5 else [right, left]

    def cls(name: str, parents: str, digit: int, call_super: bool) -> str:
        body = f"super().tag() + '{digit}'" if call_super else f"'{digit}'"
        return f"class {name}{parents}:\n    def tag(self):\n        return {body}\n"

    code = "\n".join(
        [
            cls(base, "", digits[0], False),
            cls(left, f"({base})", digits[1], True),
            cls(right, f"({base})", digits[2], True),
            cls(child, f"({', '.join(bases)})", digits[3], True),
            f"print({child}().tag())\n",
        ]
    )
    params = {"names": names, "digits": digits, "bases": bases}
    return Instance(PROMPT, run_python(code), params, code=code)
