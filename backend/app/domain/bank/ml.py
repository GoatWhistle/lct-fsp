"""Классическое машинное обучение: метрики классификации, kNN, разбиения, деревья, k-means,
линейная регрессия, ROC-AUC, log loss, ранжирование."""

import math
import random

from app.domain.bank.family import Instance, Kind, kind, rounded
from app.domain.bank.runner import CodeRunner


def _confusion(rng: random.Random) -> tuple[int, int, int, int]:
    return rng.randint(5, 90), rng.randint(1, 40), rng.randint(1, 40), rng.randint(20, 300)


@kind(Kind.COMPUTE)
def precision_recall(rng: random.Random, runner: CodeRunner) -> Instance:
    tp, fp, fn, tn = _confusion(rng)
    code = (
        "                 предсказано 1   предсказано 0\n"
        f"на самом деле 1  {tp:13d}   {fn:13d}\n"
        f"на самом деле 0  {fp:13d}   {tn:13d}\n"
    )
    prompt = (
        "Матрица ошибок классификатора ниже. Каковы precision и recall класса 1? Ответ — два "
        "числа через пробел, округлите до сотых."
    )
    answer = f"{rounded(tp / (tp + fp), 2)} {rounded(tp / (tp + fn), 2)}"
    return Instance(prompt, answer, {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, code=code)


@kind(Kind.COMPUTE)
def majority_baseline(rng: random.Random, runner: CodeRunner) -> Instance:
    positives = rng.randint(5, 200)
    negatives = rng.randint(300, 2000)
    correct = rng.randint(int(0.8 * (positives + negatives)), positives + negatives - 1)
    total = positives + negatives
    prompt = (
        f"В тестовой выборке {positives} мошеннических и {negatives} честных транзакций. Модель "
        f"ответила верно в {correct} случаях. Какова accuracy модели и accuracy константного "
        "ответа «честная»? Ответ — два числа через пробел, в процентах, округлите до десятых."
    )
    answer = f"{rounded(100 * correct / total, 1)} {rounded(100 * negatives / total, 1)}"
    return Instance(
        prompt, answer, {"positives": positives, "negatives": negatives, "correct": correct}
    )


@kind(Kind.COMPUTE)
def f1_score(rng: random.Random, runner: CodeRunner) -> Instance:
    tp, fp, fn, _ = _confusion(rng)
    beta = rng.choice([1, 2])
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    score = (1 + beta**2) * precision * recall / (beta**2 * precision + recall)
    prompt = (
        f"У классификатора TP = {tp}, FP = {fp}, FN = {fn}. Найдите F{beta}-меру. Ответ — число, "
        "округлите до тысячных."
    )
    return Instance(prompt, rounded(score, 3), {"tp": tp, "fp": fp, "fn": fn, "beta": beta})


@kind(Kind.COMPUTE)
def knn_predict(rng: random.Random, runner: CodeRunner) -> Instance:
    while True:
        points: list[tuple[int, int, str]] = []
        used: set[tuple[int, int]] = set()
        while len(points) < 9:
            p = (rng.randint(0, 9), rng.randint(0, 9))
            if p not in used:
                used.add(p)
                points.append((*p, rng.choice("ABC")))
        k = rng.choice([1, 3, 5])
        queries: list[tuple[int, int]] = []
        labels: list[str] = []
        for _ in range(200):
            q = (rng.randint(0, 9), rng.randint(0, 9))
            dists = sorted((math.dist(q, (x, y)), label) for x, y, label in points)
            votes = [label for _, label in dists[:k]]
            counts = sorted((votes.count(c) for c in "ABC"), reverse=True)
            # Без ничьих — ни на границе k-го соседа, ни в голосовании: ответ однозначен.
            if dists[k - 1][0] == dists[k][0] or counts[0] == counts[1]:
                continue
            queries.append(q)
            labels.append(max("ABC", key=votes.count))
            if len(queries) == 5:
                break
        if len(queries) == 5:
            break
    code = "\n".join(f"({x}, {y}) — класс {label}" for x, y, label in points)
    prompt = (
        f"kNN с k = {k} и евклидовым расстоянием обучен на точках ниже. Какие классы он "
        f"предскажет для точек {', '.join(map(str, queries))}? Ответ — буквы через пробел."
    )
    return Instance(
        prompt, " ".join(labels), {"points": points, "k": k, "queries": queries}, code=code
    )


@kind(Kind.COMPUTE)
def kfold_sizes(rng: random.Random, runner: CodeRunner) -> Instance:
    n = rng.randint(50, 999)
    k = rng.randint(3, 10)
    size, extra = divmod(n, k)
    big, small = size + 1, size
    prompt = (
        f"{n} объектов делят KFold(n_splits={k}) из scikit-learn: первые n mod k фолдов на "
        "объект больше. Сколько объектов в самом большом и самом маленьком тестовом фолде и "
        "сколько — в обучающей части, когда тестовый фолд самый маленький? Ответ — три числа "
        "через пробел."
    )
    largest = big if extra else small
    return Instance(prompt, f"{largest} {small} {n - small}", {"n": n, "k": k})


@kind(Kind.COMPUTE)
def one_hot_columns(rng: random.Random, runner: CodeRunner) -> Instance:
    features = {
        "город": rng.randint(2, 30),
        "тариф": rng.randint(2, 6),
        "устройство": rng.randint(2, 5),
    }
    numeric = rng.randint(1, 10)
    drop_first = rng.random() < 0.5
    total = numeric + sum(v - 1 if drop_first else v for v in features.values())
    listing = ", ".join(f"«{k}» — {v} значений" for k, v in features.items())
    prompt = (
        f"В таблице {numeric} числовых признаков и категориальные: {listing}. Их кодируют "
        f"pd.get_dummies(drop_first={drop_first}), числовые остаются как есть. Сколько столбцов "
        "получится? Ответ — число."
    )
    return Instance(
        prompt, str(total), {"features": features, "numeric": numeric, "drop_first": drop_first}
    )


@kind(Kind.COMPUTE)
def gini_split(rng: random.Random, runner: CodeRunner) -> Instance:
    left = (rng.randint(0, 30), rng.randint(0, 30))
    right = (rng.randint(0, 30), rng.randint(0, 30))
    if sum(left) == 0:
        left = (1, 2)
    if sum(right) == 0:
        right = (3, 1)

    def gini(a: int, b: int) -> float:
        n = a + b
        return 1 - (a / n) ** 2 - (b / n) ** 2

    parent = gini(left[0] + right[0], left[1] + right[1])
    n = sum(left) + sum(right)
    weighted = sum(left) / n * gini(*left) + sum(right) / n * gini(*right)
    prompt = (
        f"Узел дерева делится на левый лист ({left[0]} объектов класса 0, {left[1]} класса 1) и "
        f"правый ({right[0]} и {right[1]}). Каковы индекс Джини родителя и взвешенный Джини после "
        "разбиения? Ответ — два числа через пробел, округлите до тысячных."
    )
    return Instance(
        prompt, f"{rounded(parent, 3)} {rounded(weighted, 3)}", {"left": left, "right": right}
    )


@kind(Kind.COMPUTE)
def kmeans_step(rng: random.Random, runner: CodeRunner) -> Instance:
    points = [(rng.randint(0, 20), rng.randint(0, 20)) for _ in range(6)]
    centroids = [(rng.randint(0, 20), rng.randint(0, 20)) for _ in range(2)]
    while centroids[0] == centroids[1]:
        centroids[1] = (rng.randint(0, 20), rng.randint(0, 20))
    clusters: list[list[tuple[int, int]]] = [[], []]
    for p in points:
        d0, d1 = math.dist(p, centroids[0]), math.dist(p, centroids[1])
        clusters[0 if d0 <= d1 else 1].append(p)
    new = []
    for c, members in zip(centroids, clusters, strict=True):
        if members:
            new.append(
                (
                    sum(x for x, _ in members) / len(members),
                    sum(y for _, y in members) / len(members),
                )
            )
        else:
            new.append(c)
    prompt = (
        f"Точки: {', '.join(map(str, points))}. Центроиды k-means: C1 = {centroids[0]}, C2 = "
        f"{centroids[1]}. Выполните один шаг: отнесите точки к ближайшему центроиду (при равенстве "
        "— к C1) и пересчитайте центроиды. Ответ — координаты C1 и C2 через пробел: x1 y1 x2 y2, "
        "округлите до десятых."
    )
    answer = " ".join(rounded(v, 1) for c in new for v in c)
    return Instance(prompt, answer, {"points": points, "centroids": centroids})


@kind(Kind.COMPUTE)
def linear_fit(rng: random.Random, runner: CodeRunner) -> Instance:
    xs = sorted(rng.sample(range(0, 12), 4))
    slope, intercept = rng.choice([-3, -2, -1, 1, 2, 3, 4]), rng.randint(-5, 10)
    ys = [slope * x + intercept + rng.randint(-3, 3) for x in xs]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b1 = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mx) ** 2 for x in xs
    )
    b0 = my - b1 * mx
    lines = [f"x = {x}, y = {y}" for x, y in zip(xs, ys, strict=True)]
    prompt = (
        "Найдите коэффициенты линейной регрессии y = a·x + b методом наименьших квадратов. "
        "Ответ — a и b через пробел, округлите до сотых."
    )
    return Instance(
        prompt, f"{rounded(b1, 2)} {rounded(b0, 2)}", {"xs": xs, "ys": ys}, code="\n".join(lines)
    )


@kind(Kind.COMPUTE)
def roc_auc(rng: random.Random, runner: CodeRunner) -> Instance:
    scores = rng.sample(range(1, 100), 10)
    labels = [rng.choice([0, 1]) for _ in scores]
    if len(set(labels)) == 1:
        labels[0] = 1 - labels[0]
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
    auc = sum(1 for p in pos for q in neg if p > q) / (len(pos) * len(neg))
    lines = [f"скор {s / 100:.2f}, класс {y}" for s, y in zip(scores, labels, strict=True)]
    prompt = (
        "Найдите ROC-AUC по скорам модели и истинным классам (одинаковых скоров нет). Ответ — "
        "число, округлите до тысячных."
    )
    return Instance(
        prompt, rounded(auc, 3), {"scores": scores, "labels": labels}, code="\n".join(lines)
    )


@kind(Kind.COMPUTE)
def log_loss(rng: random.Random, runner: CodeRunner) -> Instance:
    probs = [rng.randint(5, 95) / 100 for _ in range(4)]
    labels = [rng.choice([0, 1]) for _ in probs]
    loss = -sum(math.log(p if y else 1 - p) for p, y in zip(probs, labels, strict=True)) / len(
        probs
    )
    lines = [f"P(класс 1) = {p}, истинный класс {y}" for p, y in zip(probs, labels, strict=True)]
    prompt = (
        "Найдите log loss (среднюю бинарную кросс-энтропию, натуральный логарифм). Ответ — "
        "число, округлите до тысячных."
    )
    return Instance(
        prompt, rounded(loss, 3), {"probs": probs, "labels": labels}, code="\n".join(lines)
    )


@kind(Kind.COMPUTE)
def ndcg_at_k(rng: random.Random, runner: CodeRunner) -> Instance:
    rels = [rng.choice([0, 0, 1, 2, 3]) for _ in range(6)]
    if not any(rels):
        rels[rng.randrange(6)] = 2
    k = rng.choice([3, 5])

    def dcg(values: list[int]) -> float:
        return float(sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(values[:k])))

    score = dcg(rels) / dcg(sorted(rels, reverse=True))
    prompt = (
        f"Выдача из 6 документов с оценками релевантности по порядку: {', '.join(map(str, rels))}. "
        f"Найдите nDCG@{k} с усилением 2^rel − 1 и дисконтом log2(позиция + 1); идеальный порядок "
        "— по убыванию релевантности тех же документов. Ответ — число, округлите до тысячных."
    )
    return Instance(prompt, rounded(score, 3), {"rels": rels, "k": k})
