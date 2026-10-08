"""Математика, вероятности и статистика для анализа данных."""

import math
import random
from collections.abc import Callable
from fractions import Fraction
from itertools import product

from app.domain.bank.family import Instance, Kind, kind, rounded
from app.domain.bank.runner import CodeRunner


@kind(Kind.COMPUTE)
def mean_median(rng: random.Random, runner: CodeRunner) -> Instance:
    values = [rng.randint(1, 99) for _ in range(rng.randint(6, 9))]
    ordered = sorted(values)
    n = len(values)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    mean = sum(values) / n
    prompt = (
        f"Выборка: {', '.join(map(str, values))}. Каковы среднее и медиана? Ответ — два числа "
        "через пробел, округлите до десятых."
    )
    return Instance(prompt, f"{rounded(mean, 1)} {rounded(median, 1)}", {"values": values})


@kind(Kind.COMPUTE)
def dice_sum(rng: random.Random, runner: CodeRunner) -> Instance:
    sides = rng.choice([4, 6, 8])
    dice = rng.randint(2, 3)
    target = rng.randint(dice + 1, dice * sides - 1)
    relation = rng.choice(["=", "≥", "≤"])
    outcomes = list(product(range(1, sides + 1), repeat=dice))
    ok: Callable[[int], bool] = {
        "=": lambda s: s == target,
        "≥": lambda s: s >= target,
        "≤": lambda s: s <= target,
    }[relation]
    p = Fraction(sum(1 for o in outcomes if ok(sum(o))), len(outcomes))
    prompt = (
        f"Бросают {dice} честных кубика с гранями 1–{sides}. Какова вероятность, что сумма "
        f"{relation} {target}? Ответ — число, округлите до тысячных."
    )
    return Instance(
        prompt,
        rounded(float(p), 3),
        {"sides": sides, "dice": dice, "target": target, "relation": relation},
    )


@kind(Kind.COMPUTE)
def conditional_table(rng: random.Random, runner: CodeRunner) -> Instance:
    a, b, c, d = (rng.randint(5, 80) for _ in range(4))
    code = (
        "              купил   не купил\n"
        f"видел рекламу  {a:5d}   {b:7d}\n"
        f"не видел       {c:5d}   {d:7d}\n"
    )
    p_buy_given_ad = a / (a + b)
    p_ad_given_buy = a / (a + c)
    prompt = (
        "Таблица сопряжённости по пользователям. Найдите P(купил | видел рекламу) и "
        "P(видел рекламу | купил). Ответ — два числа через пробел, округлите до сотых."
    )
    return Instance(
        prompt,
        f"{rounded(p_buy_given_ad, 2)} {rounded(p_ad_given_buy, 2)}",
        {"table": [a, b, c, d]},
        code=code,
    )


@kind(Kind.COMPUTE)
def variance_std(rng: random.Random, runner: CodeRunner) -> Instance:
    values = [rng.randint(1, 30) for _ in range(rng.randint(5, 7))]
    sample = rng.random() < 0.5
    mean = sum(values) / len(values)
    ss = sum((v - mean) ** 2 for v in values)
    var = ss / (len(values) - 1 if sample else len(values))
    kind = "выборочную (несмещённую, делитель n − 1)" if sample else "генеральную (делитель n)"
    prompt = (
        f"Значения: {', '.join(map(str, values))}. Найдите {kind} дисперсию и стандартное "
        "отклонение. Ответ — два числа через пробел, округлите до сотых."
    )
    return Instance(
        prompt,
        f"{rounded(var, 2)} {rounded(math.sqrt(var), 2)}",
        {"values": values, "sample": sample},
    )


@kind(Kind.COMPUTE)
def combinatorics(rng: random.Random, runner: CodeRunner) -> Instance:
    n = rng.randint(6, 15)
    k = rng.randint(2, min(5, n - 1))
    prompt = (
        f"Из {n} кандидатов выбирают {k}. Сколько способов выбрать команду (порядок не важен) и "
        f"сколько способов раздать {k} разные роли (порядок важен)? Ответ — два числа через пробел."
    )
    return Instance(prompt, f"{math.comb(n, k)} {math.perm(n, k)}", {"n": n, "k": k})


@kind(Kind.COMPUTE)
def expected_value(rng: random.Random, runner: CodeRunner) -> Instance:
    outcomes = [(rng.randint(-50, 200), rng.randint(1, 9)) for _ in range(3)]
    total = sum(w for _, w in outcomes)
    ev = sum(v * w for v, w in outcomes) / total
    lines = [f"выигрыш {v} ₽ — в {w} случаях из {total}" for v, w in outcomes]
    prompt = (
        "Лотерея: исходы и их частоты ниже, других исходов нет. Каково математическое ожидание "
        "выигрыша? Ответ — число, округлите до сотых."
    )
    return Instance(prompt, f"{rounded(ev, 2)}", {"outcomes": outcomes}, code="\n".join(lines))


@kind(Kind.COMPUTE)
def bayes(rng: random.Random, runner: CodeRunner) -> Instance:
    prevalence = rng.choice([0.5, 1, 2, 5, 10])
    sensitivity = rng.choice([80, 90, 95, 99])
    specificity = rng.choice([85, 90, 95, 99])
    p = prevalence / 100
    tp = p * sensitivity / 100
    fp = (1 - p) * (1 - specificity / 100)
    posterior = tp / (tp + fp)
    prompt = (
        f"Мошеннических транзакций {prevalence} %. Детектор ловит {sensitivity} % мошеннических "
        f"и ошибочно помечает {100 - specificity} % честных. Транзакция помечена. Какова "
        "вероятность, что она мошенническая? Ответ — число, округлите до тысячных."
    )
    params = {"prevalence": prevalence, "sensitivity": sensitivity, "specificity": specificity}
    return Instance(prompt, f"{rounded(posterior, 3)}", params)


@kind(Kind.COMPUTE)
def binomial(rng: random.Random, runner: CodeRunner) -> Instance:
    n = rng.randint(5, 15)
    p = rng.choice([0.1, 0.2, 0.3, 0.4, 0.5])
    k = rng.randint(0, min(n, 6))
    at_least = rng.random() < 0.5
    if at_least:
        value = sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))
        what = f"не меньше {k}"
    else:
        value = math.comb(n, k) * p**k * (1 - p) ** (n - k)
        what = f"ровно {k}"
    prompt = (
        f"Каждый из {n} независимых запросов падает с вероятностью {p}. Какова вероятность, что "
        f"упадёт {what}? Ответ — число, округлите до тысячных."
    )
    return Instance(prompt, f"{rounded(value, 3)}", {"n": n, "p": p, "k": k, "at_least": at_least})


@kind(Kind.COMPUTE)
def z_score(rng: random.Random, runner: CodeRunner) -> Instance:
    mean = rng.randrange(50, 500, 10)
    sd = rng.randrange(5, 60, 5)
    x = mean + rng.randint(-25, 25) * sd // 10
    z = (x - mean) / sd
    below = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    prompt = (
        f"Время ответа распределено нормально со средним {mean} мс и стандартным отклонением "
        f"{sd} мс. Каков z-показатель значения {x} мс и какая доля ответов быстрее него? Ответ — "
        "два числа через пробел: z до сотых, долю до тысячных."
    )
    return Instance(
        prompt, f"{rounded(z, 2)} {rounded(below, 3)}", {"mean": mean, "sd": sd, "x": x}
    )


@kind(Kind.COMPUTE)
def pearson(rng: random.Random, runner: CodeRunner) -> Instance:
    xs = [rng.randint(1, 20) for _ in range(5)]
    slope = rng.choice([-2, -1, 1, 2, 3])
    ys = [slope * x + rng.randint(-8, 8) for x in xs]
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        xs[0] += 1
        ys[0] += 3
    mx, my = sum(xs) / 5, sum(ys) / 5
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    r = cov / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    lines = [f"x = {x}, y = {y}" for x, y in zip(xs, ys, strict=True)]
    prompt = "Найдите коэффициент корреляции Пирсона x и y. Ответ — число, округлите до сотых."
    return Instance(prompt, f"{rounded(r, 2)}", {"xs": xs, "ys": ys}, code="\n".join(lines))


@kind(Kind.COMPUTE)
def matrix_product(rng: random.Random, runner: CodeRunner) -> Instance:
    a = [[rng.randint(-3, 5) for _ in range(3)] for _ in range(2)]
    b = [[rng.randint(-3, 5) for _ in range(2)] for _ in range(3)]
    c = [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(2)] for i in range(2)]
    code = "A = " + str(a) + "   # 2×3\nB = " + str(b) + "   # 3×2\n"
    prompt = (
        "Найдите произведение матриц A · B (2×2). Ответ — четыре числа через пробел по строкам."
    )
    answer = " ".join(str(v) for row in c for v in row)
    return Instance(prompt, answer, {"a": a, "b": b}, code=code)


@kind(Kind.COMPUTE)
def gradient_step(rng: random.Random, runner: CodeRunner) -> Instance:
    points = [(rng.randint(0, 5), rng.randint(-5, 15)) for _ in range(3)]
    w, b = rng.randint(-2, 3), rng.randint(-3, 3)
    lr = rng.choice([0.01, 0.05, 0.1])
    n = len(points)
    grad_w = sum(2 * (w * x + b - y) * x for x, y in points) / n
    grad_b = sum(2 * (w * x + b - y) for x, y in points) / n
    new_w, new_b = w - lr * grad_w, b - lr * grad_b
    lines = [f"x = {x}, y = {y}" for x, y in points]
    prompt = (
        f"Линейная модель ŷ = w·x + b, w = {w}, b = {b}, функция потерь — среднеквадратичная "
        f"ошибка MSE по точкам ниже. Сделайте один шаг градиентного спуска с шагом {lr}. Ответ — "
        "новые w и b через пробел, округлите до тысячных."
    )
    return Instance(
        prompt,
        f"{rounded(new_w, 3)} {rounded(new_b, 3)}",
        {"points": points, "w": w, "b": b, "lr": lr},
        code="\n".join(lines),
    )
