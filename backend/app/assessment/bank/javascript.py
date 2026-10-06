"""JavaScript и TypeScript: приведение типов, методы массивов, замыкания, цикл событий, промисы.

Движка JS на бэкенде нет, поэтому эталон считает модель семантики на Python — узкая, ровно под
конструкции шаблона. Шаблоны собраны так, чтобы модель была точной: без this, без NaN в выводе,
без чисел с экспонентой.
"""

import random

from app.assessment.bank.family import Instance

PROMPT = "Что выведет код в консоль? Ответ — выведенные значения через пробел по порядку."


def _js_number(value: float) -> str:
    """Число так, как его печатает console.log: целые без «.0»."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def type_coercion(rng: random.Random) -> Instance:
    lines, out = [], []
    for _ in range(4):
        a, b, c = rng.randint(1, 9), rng.randint(1, 9), rng.randint(1, 9)
        kind = rng.randrange(6)
        if kind == 0:
            lines.append(f"console.log('{a}' + {b});")
            out.append(f"{a}{b}")
        elif kind == 1:
            lines.append(f"console.log('{a}{c}' - {b});")
            out.append(_js_number(int(f"{a}{c}") - b))
        elif kind == 2:
            lines.append(f"console.log('{a}' * '{b}');")
            out.append(_js_number(a * b))
        elif kind == 3:
            lines.append(f"console.log({a} + true);")
            out.append(_js_number(a + 1))
        elif kind == 4:
            lines.append(f"console.log('{a}' + {b} + {c});")
            out.append(f"{a}{b}{c}")
        else:
            lines.append(f"console.log({a} + {b} + '{c}');")
            out.append(f"{a + b}{c}")
    return Instance(PROMPT, " ".join(out), {"lines": lines}, code="\n".join(lines))


def array_pipeline(rng: random.Random) -> Instance:
    nums = [rng.randint(-20, 40) for _ in range(rng.randint(6, 9))]
    m = rng.randint(2, 3)
    # Множитель не кратен делителю: иначе после map остаток у всех 0 и ответ почти всегда 0.
    k = rng.choice([v for v in range(2, 10) if v % m])
    r = rng.randrange(m)
    mapped = [x * k for x in nums]
    code = (
        f"const nums = [{', '.join(map(str, nums))}];\n"
        "const result = nums\n"
        f"  .map(x => x * {k})\n"
        f"  .filter(x => x % {m} === {r})\n"
        "  .reduce((sum, x) => sum + x, 0);\n"
        "console.log(result);\n"
    )
    # % в JS сохраняет знак делимого: -10 % 3 === -1, а не 2, как в Python.
    kept = [x for x in mapped if _js_mod(x, m) == r]
    return Instance(PROMPT, str(sum(kept)), {"nums": nums, "k": k, "m": m, "r": r}, code=code)


def _js_mod(a: int, b: int) -> int:
    result = abs(a) % abs(b)
    return -result if a < 0 else result


def var_let_loop(rng: random.Random) -> Instance:
    n, k, c = rng.randint(2, 4), rng.randint(2, 9), rng.randint(0, 9)
    keyword = rng.choice(["var", "let"])
    code = (
        f"for ({keyword} i = 0; i < {n}; i++) {{\n"
        f"  setTimeout(() => console.log(i * {k} + {c}), 0);\n"
        "}\n"
    )
    values = [(n if keyword == "var" else i) * k + c for i in range(n)]
    return Instance(
        PROMPT, " ".join(map(str, values)), {"keyword": keyword, "n": n, "k": k, "c": c}, code=code
    )


def default_sort(rng: random.Random) -> Instance:
    nums = rng.sample([*range(1, 30), 100, 200, 1000, 25, 250], rng.randint(5, 7))
    numeric = rng.random() < 0.3
    if numeric:
        code = f"console.log([{', '.join(map(str, nums))}].sort((a, b) => a - b).join(' '));\n"
        ordered = sorted(nums)
    else:
        code = f"console.log([{', '.join(map(str, nums))}].sort().join(' '));\n"
        ordered = sorted(nums, key=str)
    return Instance(
        PROMPT, " ".join(map(str, ordered)), {"nums": nums, "numeric": numeric}, code=code
    )


def loose_equality(rng: random.Random) -> Instance:
    rows = []
    for _ in range(6):
        a = rng.randint(1, 9)
        b = rng.choice([x for x in range(1, 10) if x != a])
        rows.append(
            rng.choice(
                [
                    (f"'{a}' == {a}", True),
                    (f"'{a}' === {a}", False),
                    (f"'{a}' == {b}", False),
                    ("0 == ''", True),
                    ("null == undefined", True),
                    ("null === undefined", False),
                    ("null == 0", False),
                    ("NaN == NaN", False),
                    ("'1' == true", True),
                    ("[] == false", True),
                    (f"[{a}] == {a}", True),
                    (f"'{a}0' == {a}", False),
                ]
            )
        )
    code = "\n".join(f"console.log({expr});" for expr, _ in rows)
    answer = " ".join("true" if value else "false" for _, value in rows)
    return Instance(PROMPT, answer, {"rows": [expr for expr, _ in rows]}, code=code)


def destructuring(rng: random.Random) -> Instance:
    a, b, d = rng.randint(1, 30), rng.randint(1, 30), rng.randint(1, 30)
    has_b = rng.random() < 0.5
    extra = rng.sample(["x", "y", "z", "w"], rng.randint(0, 3))
    source = {"a": a, **({"b": b} if has_b else {}), **{k: rng.randint(1, 9) for k in extra}}
    rendered = ", ".join(f"{k}: {v}" for k, v in source.items())
    code = (
        f"const source = {{ {rendered} }};\n"
        f"const {{ a, b = {d}, ...rest }} = source;\n"
        "console.log(a + b + Object.keys(rest).length);\n"
    )
    total = a + (b if has_b else d) + len(extra)
    return Instance(PROMPT, str(total), {"source": source, "default": d}, code=code)


def event_loop(rng: random.Random) -> Instance:
    """Синхронный код → микрозадачи → по таймеру макрозадачи, после каждой — её микрозадачи."""
    letters = iter("ABCDEFGHIJKLMNOP")
    lines: list[str] = []
    sync: list[str] = []
    micro: list[list[str]] = []  # цепочки then: каждая следующая — новая микрозадача
    timers: list[tuple[int, int, list[str], list[str]]] = []
    for order in range(rng.randint(5, 6)):
        kind = rng.choice(["log", "timeout", "then", "chain", "micro", "timeout_then"])
        x = next(letters)
        if kind == "log":
            lines.append(f"console.log('{x}');")
            sync.append(x)
        elif kind == "timeout":
            delay = rng.choice([0, 0, 100])
            lines.append(f"setTimeout(() => console.log('{x}'), {delay});")
            timers.append((delay, order, [x], []))
        elif kind == "then":
            lines.append(f"Promise.resolve().then(() => console.log('{x}'));")
            micro.append([x])
        elif kind == "chain":
            y = next(letters)
            lines.append(
                f"Promise.resolve().then(() => console.log('{x}')).then(() => console.log('{y}'));"
            )
            micro.append([x, y])
        elif kind == "micro":
            lines.append(f"queueMicrotask(() => console.log('{x}'));")
            micro.append([x])
        else:
            y = next(letters)
            delay = rng.choice([0, 100])
            lines.append(
                f"setTimeout(() => {{ console.log('{x}'); "
                f"Promise.resolve().then(() => console.log('{y}')); }}, {delay});"
            )
            timers.append((delay, order, [x], [y]))

    out = list(sync)
    # Микрозадачи: первые звенья всех цепочек по порядку, потом вторые — по очереди готовности.
    queue = [chain for chain in micro]
    step = 0
    while any(len(chain) > step for chain in queue):
        out += [chain[step] for chain in queue if len(chain) > step]
        step += 1
    for _, _, logs, then in sorted(timers, key=lambda t: (t[0], t[1])):
        out += logs + then
    return Instance(PROMPT, " ".join(out), {"lines": lines}, code="\n".join(lines))


def closure_counter(rng: random.Random) -> Instance:
    start, a1, b1, a2, b2 = (rng.randint(1, 30) for _ in range(5))
    code = (
        "function makeCounter(start) {\n"
        "  let count = start;\n"
        "  return (delta) => (count += delta);\n"
        "}\n"
        f"const first = makeCounter({start});\n"
        f"const second = makeCounter({start});\n"
        f"first({a1});\n"
        f"second({b1});\n"
        f"console.log(first({a2}) * 2 + second({b2}));\n"
    )
    answer = (start + a1 + a2) * 2 + (start + b1 + b2)
    return Instance(PROMPT, str(answer), {"start": start, "deltas": [a1, b1, a2, b2]}, code=code)


def promise_combinators(rng: random.Random) -> Instance:
    combinator = rng.choice(["all", "allSettled", "race", "any"])
    promises = []
    for i in range(3):
        delay = rng.choice([10, 20, 30, 40, 50])
        ok = rng.random() < 0.65
        value = rng.randint(1, 99)
        promises.append((delay + i, ok, value))  # +i — без одновременных таймеров
    rendered = [f"later({d}, {'true' if ok else 'false'}, {v})" for d, ok, v in promises]
    code = (
        "// later(ms, ok, value): через ms мс выполнится со значением value или отклонится с ним\n"
        f"Promise.{combinator}([{', '.join(rendered)}])\n"
        "  .then(r => console.log(Array.isArray(r) "
        "? r.map(x => x.value ?? x.reason ?? x).join(' ') : r))\n"
        "  .catch(e => console.log('ошибка', e.errors ? e.errors.join(' ') : e));\n"
    )
    by_time = sorted(promises)
    if combinator == "all":
        failed = [p for p in by_time if not p[1]]
        out = f"ошибка {failed[0][2]}" if failed else " ".join(str(p[2]) for p in promises)
    elif combinator == "allSettled":
        out = " ".join(str(p[2]) for p in promises)
    elif combinator == "race":
        first = by_time[0]
        out = str(first[2]) if first[1] else f"ошибка {first[2]}"
    else:
        fulfilled = [p for p in by_time if p[1]]
        out = (
            str(fulfilled[0][2]) if fulfilled else "ошибка " + " ".join(str(p[2]) for p in promises)
        )
    return Instance(PROMPT, out, {"combinator": combinator, "promises": promises}, code=code)


def array_mutation(rng: random.Random) -> Instance:
    arr = rng.sample(range(1, 50), 5)
    js = list(arr)
    lines = [f"const arr = [{', '.join(map(str, arr))}];"]
    for _ in range(4):
        kind = rng.randrange(4)
        v = rng.randint(50, 99)
        if kind == 0:
            lines.append(f"arr.push({v});")
            js.append(v)
        elif kind == 1:
            start, count = rng.randint(0, len(js) - 1), rng.randint(0, 2)
            lines.append(f"arr.splice({start}, {count}, {v});")
            js[start : start + count] = [v]
        elif kind == 2:
            # slice возвращает копию: push в неё исходный массив не меняет.
            lines.append(f"arr.slice(1, 3).push({v});")
        else:
            lines.append("arr.unshift(arr.pop());")
            js.insert(0, js.pop())
    lines.append("console.log(arr.join(' '));")
    return Instance(PROMPT, " ".join(map(str, js)), {"lines": lines}, code="\n".join(lines))


def await_timing(rng: random.Random) -> Instance:
    delays = [rng.randint(1, 30) * 50 for _ in range(3)]
    sequential = rng.random() < 0.5
    names = ["user", "orders", "prices"]
    if sequential:
        body = "".join(
            f"  const {n} = await wait({d});\n" for n, d in zip(names, delays, strict=True)
        )
        total = sum(delays)
    else:
        body = (
            f"  const [{', '.join(names)}] = await Promise.all([\n"
            + "".join(f"    wait({d}),\n" for d in delays)
            + "  ]);\n"
        )
        total = max(delays)
    extra = rng.randint(1, 10) * 50
    code = (
        "const wait = (ms) => new Promise(r => setTimeout(r, ms));\n\n"
        "async function load() {\n" + body + f"  await wait({extra});\n"
        "}\n\n"
        "const t0 = Date.now();\n"
        "load().then(() => console.log(Date.now() - t0));\n"
    )
    prompt = "Что выведет код, если таймеры точные, а остальное мгновенно? Ответ — число."
    return Instance(
        prompt,
        str(total + extra),
        {"delays": delays, "sequential": sequential, "extra": extra},
        code=code,
    )


def float_sums(rng: random.Random) -> Instance:
    pairs = [(rng.randint(1, 9), rng.randint(1, 9)) for _ in range(3)]
    lines = [f"console.log(0.{a} + 0.{b});" for a, b in pairs]
    out = [_js_number(a / 10 + b / 10) for a, b in pairs]
    code = "\n".join(lines)
    return Instance(PROMPT, " ".join(out), {"pairs": pairs}, code=code)
