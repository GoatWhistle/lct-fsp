"""Python для анализа данных: списки и словари, NumPy и pandas.

NumPy и pandas на бэкенде нет: эталон считает модель их поведения на чистом Python — ровно для
операций шаблона (форма при broadcasting, срезы, groupby, merge, rolling, переполнение int8).
"""

import random

from app.assessment.bank.family import Instance, rounded
from app.assessment.bank.python_code import PROMPT, run_python

CITIES = ["Казань", "Москва", "Пермь", "Томск", "Уфа"]


def _frame(rng: random.Random, n: int) -> list[tuple[str, int, int]]:
    return [
        (rng.choice(CITIES[:4]), rng.randint(1, 9), rng.randrange(100, 1000, 10)) for _ in range(n)
    ]


def _render(rows: list[tuple[str, int, int]]) -> str:
    body = ",\n".join(f"    ({c!r}, {q}, {a})" for c, q, a in rows)
    return (
        "import pandas as pd\n\n"
        f"df = pd.DataFrame([\n{body},\n], columns=['city', 'qty', 'amount'])\n"
    )


def comprehension_stats(rng: random.Random) -> Instance:
    values = [rng.randint(-20, 60) for _ in range(rng.randint(7, 10))]
    low, high = rng.randint(-10, 10), rng.randint(20, 50)
    clean = [v for v in values if low <= v <= high]
    if not clean:
        return comprehension_stats(rng)
    code = (
        f"values = {values}\n"
        f"clean = [v for v in values if {low} <= v <= {high}]\n"
        "print(len(clean), sum(clean) / len(clean))\n"
    )
    prompt = "Что выведет программа? Ответ — два числа через пробел, второе округлите до сотых."
    answer = f"{len(clean)} {rounded(sum(clean) / len(clean), 2)}"
    return Instance(prompt, answer, {"values": values, "low": low, "high": high}, code=code)


def dict_grouping(rng: random.Random) -> Instance:
    rows = [
        (rng.choice(["a", "b", "c", "d"]), rng.randint(1, 50)) for _ in range(rng.randint(7, 10))
    ]
    code = (
        f"rows = {rows}\n"
        "totals = {}\n"
        "for key, value in rows:\n"
        "    totals.setdefault(key, []).append(value)\n"
        "print(*(f'{k}={max(v)}' for k, v in sorted(totals.items())))\n"
    )
    return Instance(PROMPT, run_python(code), {"rows": rows}, code=code)


def broadcast_shape(rng: random.Random) -> Instance:
    target = [rng.choice([2, 3, 4, 5]) for _ in range(rng.randint(2, 3))]

    def derive() -> list[int]:
        dims = [d if rng.random() < 0.5 else 1 for d in target]
        return dims[rng.randint(0, len(dims) - 1) :]

    a, b = derive(), derive()
    if rng.random() < 0.12:
        # Несовместимая пара: в одной оси разные размеры, и ни один не 1.
        b[-1] = a[-1] + 1 if a[-1] > 1 else 3
        a[-1] = max(a[-1], 2)
    x, y = rng.randint(1, 9), rng.randint(1, 9)
    shape: list[int] = []
    ok = True
    for i in range(1, max(len(a), len(b)) + 1):
        da = a[-i] if i <= len(a) else 1
        db = b[-i] if i <= len(b) else 1
        if da != db and 1 not in (da, db):
            ok = False
            break
        shape.insert(0, max(da, db))
    size = 1
    for d in shape:
        size *= d
    answer = f"{' '.join(map(str, shape))} {(x + y) * size}" if ok else "ошибка"
    code = (
        "import numpy as np\n\n"
        f"a = np.full({tuple(a)}, {x})\n"
        f"b = np.full({tuple(b)}, {y})\n"
        "c = a + b\n"
        "print(*c.shape, c.sum())\n"
    )
    prompt = (
        "Что выведет программа? Ответ — размеры c и сумма её элементов через пробел; если "
        "сложение упадёт с ошибкой — слово «ошибка»."
    )
    return Instance(prompt, answer, {"a": a, "b": b, "x": x, "y": y}, code=code)


def array_slicing(rng: random.Random) -> Instance:
    rows, cols = rng.randint(3, 6), rng.randint(3, 6)
    r0, r1 = sorted(rng.sample(range(0, rows + 1), 2))
    c0 = rng.randint(0, cols - 1)
    step = rng.choice([1, 2])
    data = [[r * cols + c for c in range(cols)] for r in range(rows)]
    picked = [data[r][c] for r in range(r0, r1) for c in range(c0, cols, step)]
    code = (
        "import numpy as np\n\n"
        f"a = np.arange({rows * cols}).reshape({rows}, {cols})\n"
        f"part = a[{r0}:{r1}, {c0}::{step}]\n"
        "print(part.shape, part.sum())\n"
    )
    prompt = (
        "Что выведет программа? Ответ — три числа через пробел: размеры part и сумма её элементов."
    )
    answer = f"{r1 - r0} {len(range(c0, cols, step))} {sum(picked)}"
    return Instance(
        prompt,
        answer,
        {"rows": rows, "cols": cols, "r": [r0, r1], "c0": c0, "step": step},
        code=code,
    )


def pandas_filter(rng: random.Random) -> Instance:
    rows = _frame(rng, rng.randint(7, 10))
    qty = rng.randint(2, 7)
    city = rng.choice(CITIES[:4])
    kept = [r for r in rows if r[1] > qty and r[0] != city]
    code = _render(rows) + (
        f"part = df[(df['qty'] > {qty}) & (df['city'] != {city!r})]\n"
        "print(len(part), part['amount'].sum())\n"
    )
    prompt = "Что выведет программа? Ответ — два числа через пробел."
    return Instance(
        prompt,
        f"{len(kept)} {sum(r[2] for r in kept)}",
        {"rows": rows, "qty": qty, "city": city},
        code=code,
    )


def groupby_sum(rng: random.Random) -> Instance:
    rows = _frame(rng, rng.randint(7, 10))
    column = rng.choice(["qty", "amount"])
    agg = rng.choice(["sum", "max", "count"])
    groups: dict[str, list[int]] = {}
    for c, q, a in rows:
        groups.setdefault(c, []).append(q if column == "qty" else a)
    values = []
    for c in sorted(groups):
        v = groups[c]
        values.append(sum(v) if agg == "sum" else max(v) if agg == "max" else len(v))
    code = _render(rows) + f"print(df.groupby('city')['{column}'].{agg}().tolist())\n"
    prompt = (
        "Что выведет программа? Группы groupby по умолчанию идут по возрастанию ключа. Ответ — "
        "числа из списка через пробел."
    )
    return Instance(
        prompt, " ".join(map(str, values)), {"rows": rows, "column": column, "agg": agg}, code=code
    )


def merge_rows(rng: random.Random) -> Instance:
    left_keys = [rng.choice("ABCDE") for _ in range(rng.randint(4, 6))]
    right_keys = [rng.choice("ABCDEF") for _ in range(rng.randint(3, 5))]
    how = rng.choice(["inner", "left", "outer"])
    rows = 0
    x_sum = 0
    for i, k in enumerate(left_keys):
        matches = right_keys.count(k)
        if matches:
            rows += matches
            x_sum += i * matches
        elif how in ("left", "outer"):
            rows += 1
            x_sum += i
    if how == "outer":
        rows += sum(1 for k in right_keys if k not in left_keys)
    code = (
        "import pandas as pd\n\n"
        f"left = pd.DataFrame({{'key': {left_keys}, 'x': range({len(left_keys)})}})\n"
        f"right = pd.DataFrame({{'key': {right_keys}, 'y': range({len(right_keys)})}})\n"
        f"m = pd.merge(left, right, on='key', how='{how}')\n"
        "print(len(m), int(m['x'].sum()))\n"
    )
    prompt = "Что выведет программа? sum пропускает NaN. Ответ — два числа через пробел."
    return Instance(
        prompt, f"{rows} {x_sum}", {"left": left_keys, "right": right_keys, "how": how}, code=code
    )


def missing_values(rng: random.Random) -> Instance:
    values: list[int | None] = [rng.choice([None, *range(1, 40)]) for _ in range(rng.randint(6, 9))]
    if all(v is None for v in values):
        values[0] = 5
    present = [v for v in values if v is not None]
    mean = sum(present) / len(present)
    filled = [v if v is not None else 0 for v in values]
    rendered = ", ".join("np.nan" if v is None else str(v) for v in values)
    code = (
        "import numpy as np\nimport pandas as pd\n\n"
        f"s = pd.Series([{rendered}])\n"
        "print(s.mean(), s.fillna(0).mean(), s.count())\n"
    )
    answer = f"{rounded(mean, 2)} {rounded(sum(filled) / len(filled), 2)} {len(present)}"
    prompt = "Что выведет программа? Ответ — три числа через пробел, первые два округлите до сотых."
    return Instance(prompt, answer, {"values": values}, code=code)


def rolling_mean(rng: random.Random) -> Instance:
    values = [rng.randint(1, 50) for _ in range(rng.randint(6, 9))]
    window = rng.randint(2, 4)
    means = [
        None if i + 1 < window else sum(values[i + 1 - window : i + 1]) / window
        for i in range(len(values))
    ]
    nan_count = sum(1 for m in means if m is None)
    last = means[-1]
    assert last is not None
    peak = max(m for m in means if m is not None)
    code = (
        "import pandas as pd\n\n"
        f"s = pd.Series({values})\n"
        f"r = s.rolling({window}).mean()\n"
        "print(r.isna().sum(), r.iloc[-1], r.max())\n"
    )
    prompt = (
        "Что выведет программа? Ответ — три числа через пробел, второе и третье округлите до сотых."
    )
    answer = f"{nan_count} {rounded(last, 2)} {rounded(peak, 2)}"
    return Instance(prompt, answer, {"values": values, "window": window}, code=code)


def pivot_cell(rng: random.Random) -> Instance:
    city, quarter = rng.choice(CITIES[:3]), rng.choice(["Q1", "Q2"])
    rows: list[tuple[str, str, int]] = []
    # Строка города и оба столбца кварталов должны быть в сводной таблице, иначе loc упадёт.
    while not (any(c == city for c, _, _ in rows) and {q for _, q, _ in rows} == {"Q1", "Q2"}):
        rows = [
            (rng.choice(CITIES[:3]), rng.choice(["Q1", "Q2"]), rng.randrange(100, 1000, 10))
            for _ in range(rng.randint(7, 10))
        ]
    cell = sum(a for c, q, a in rows if c == city and q == quarter)
    total_city = sum(a for c, _, a in rows if c == city)
    body = ",\n".join(f"    ({c!r}, {q!r}, {a})" for c, q, a in rows)
    code = (
        "import pandas as pd\n\n"
        f"df = pd.DataFrame([\n{body},\n], columns=['city', 'quarter', 'amount'])\n"
        "pt = df.pivot_table(index='city', columns='quarter', values='amount',\n"
        "                    aggfunc='sum', fill_value=0, margins=True)\n"
        f"print(pt.loc[{city!r}, {quarter!r}], pt.loc[{city!r}, 'All'])\n"
    )
    prompt = "Что выведет программа? Ответ — два числа через пробел."
    return Instance(
        prompt, f"{cell} {total_city}", {"rows": rows, "city": city, "quarter": quarter}, code=code
    )


def view_or_copy(rng: random.Random) -> Instance:
    n = rng.randint(5, 12)
    start, stop = sorted(rng.sample(range(0, n), 2))
    value = rng.randint(50, 999)
    fancy = rng.random() < 0.5
    base = list(range(n))
    if fancy:
        index = sorted(rng.sample(range(n), 2))
        taken = f"a[{index}]"
    else:
        taken = f"a[{start}:{stop + 1}]"
    if not fancy:
        base[start] = value
    code = (
        f"import numpy as np\n\na = np.arange({n})\nb = {taken}\nb[0] = {value}\nprint(a.sum())\n"
    )
    prompt = "Что выведет программа? Ответ — число."
    return Instance(prompt, str(sum(base)), {"n": n, "taken": taken, "value": value}, code=code)


def int8_overflow(rng: random.Random) -> Instance:
    dtype = rng.choice(["int8", "uint8"])
    low, high = (-128, 127) if dtype == "int8" else (0, 255)
    values = [rng.randint(max(low, -60), high) for _ in range(3)]
    add = rng.randint(30, high)

    def wrap(x: int) -> int:
        return (x - low) % 256 + low

    result = [wrap(v + add) for v in values]
    code = (
        "import numpy as np\n\n"
        f"a = np.array({values}, dtype=np.{dtype})\n"
        f"b = a + np.array({add}, dtype=np.{dtype})\n"
        "print(*b)\n"
    )
    prompt = (
        "Что выведет программа? Арифметика массивов NumPy с фиксированным типом не проверяет "
        "переполнение. Ответ — числа через пробел."
    )
    return Instance(
        prompt,
        " ".join(map(str, result)),
        {"dtype": dtype, "values": values, "add": add},
        code=code,
    )
