"""Глубокое обучение: размеры и параметры слоёв, прямой и обратный проход, softmax и
кросс-энтропия, нормализация, расписания шага, внимание, рецептивное поле."""

import math
import random
from itertools import pairwise

from app.domain.bank.family import Instance, Kind, kind, rounded
from app.domain.bank.runner import CodeRunner


@kind(Kind.COMPUTE)
def dense_params(rng: random.Random, runner: CodeRunner) -> Instance:
    sizes = [rng.choice([8, 16, 32, 64, 100, 128, 256, 784])] + [
        rng.choice([4, 10, 16, 32, 64, 128]) for _ in range(rng.randint(2, 3))
    ]
    bias = rng.random() < 0.7
    total = sum((a + (1 if bias else 0)) * b for a, b in pairwise(sizes))
    layers = " → ".join(map(str, sizes))
    prompt = (
        f"Полносвязная сеть с размерами слоёв {layers} "
        f"{'со смещениями' if bias else 'без смещений'} (bias). Сколько у неё обучаемых "
        "параметров? Ответ — число."
    )
    return Instance(prompt, str(total), {"sizes": sizes, "bias": bias})


@kind(Kind.COMPUTE)
def relu_forward(rng: random.Random, runner: CodeRunner) -> Instance:
    x = [rng.randint(-3, 3) for _ in range(2)]
    w = [[rng.randint(-2, 2) for _ in range(2)] for _ in range(3)]
    b = [rng.randint(-2, 2) for _ in range(3)]
    v = [rng.randint(-2, 2) for _ in range(3)]
    hidden = [
        max(0, sum(wi * xi for wi, xi in zip(row, x, strict=True)) + bi)
        for row, bi in zip(w, b, strict=True)
    ]
    out = sum(vi * hi for vi, hi in zip(v, hidden, strict=True))
    code = f"x = {x}\nW = {w}\nb = {b}\nv = {v}\n\nh = relu(W @ x + b)\ny = v @ h\n"
    prompt = "Посчитайте h и y. Ответ — три значения h и y через пробел."
    return Instance(
        prompt, " ".join(map(str, [*hidden, out])), {"x": x, "w": w, "b": b, "v": v}, code=code
    )


@kind(Kind.TRACE)
def conv_shape(rng: random.Random, runner: CodeRunner) -> Instance:
    size = rng.choice([28, 32, 64, 96, 128, 224])
    channels = [3, rng.choice([8, 16, 32]), rng.choice([32, 64, 128])]
    layers = []
    for _ in range(2):
        k = rng.choice([1, 3, 5, 7])
        layers.append((k, rng.choice([1, 2]), rng.choice([0, k // 2])))
    h = size
    for k, stride, padding in layers:
        h = (h + 2 * padding - k) // stride + 1
    code = (
        "model = nn.Sequential(\n"
        + "".join(
            f"    nn.Conv2d({channels[i]}, {channels[i + 1]}, kernel_size={k}, stride={st}, "
            f"padding={p}),\n"
            for i, (k, st, p) in enumerate(layers)
        )
        + ")\n"
        f"x = torch.randn(1, 3, {size}, {size})\n"
        "print(tuple(model(x).shape))\n"
    )
    prompt = "Что выведет программа? Ответ — четыре числа через пробел."
    return Instance(
        prompt,
        f"1 {channels[-1]} {h} {h}",
        {"size": size, "channels": channels, "layers": layers},
        code=code,
    )


@kind(Kind.COMPUTE)
def conv_params(rng: random.Random, runner: CodeRunner) -> Instance:
    c_in = rng.choice([1, 3, 16, 32, 64])
    c_out = rng.choice([8, 16, 32, 64, 128])
    k = rng.choice([1, 3, 5])
    groups = rng.choice([1, 1, c_in]) if c_in in (16, 32, 64) else 1
    if groups > 1:
        c_out = c_in
    bias = rng.random() < 0.7
    params = c_out * (c_in // groups) * k * k + (c_out if bias else 0)
    prompt = (
        f"Сколько обучаемых параметров у nn.Conv2d(in_channels={c_in}, out_channels={c_out}, "
        f"kernel_size={k}, groups={groups}, bias={bias})? Ответ — число."
    )
    return Instance(
        prompt, str(params), {"c_in": c_in, "c_out": c_out, "k": k, "groups": groups, "bias": bias}
    )


@kind(Kind.COMPUTE)
def softmax_probs(rng: random.Random, runner: CodeRunner) -> Instance:
    logits = [rng.randint(-2, 4) for _ in range(3)]
    temperature = rng.choice([1, 1, 2, 0.5])
    exps = [math.exp(z / temperature) for z in logits]
    total = sum(exps)
    probs = [e / total for e in exps]
    prompt = (
        f"Логиты модели: {logits}. Найдите softmax с температурой T = {temperature} "
        "(логиты делятся на T). Ответ — три вероятности через пробел, округлите до тысячных."
    )
    return Instance(
        prompt,
        " ".join(rounded(p, 3) for p in probs),
        {"logits": logits, "temperature": temperature},
    )


@kind(Kind.COMPUTE)
def cross_entropy(rng: random.Random, runner: CodeRunner) -> Instance:
    batch = []
    for _ in range(3):
        logits = [rng.randint(-2, 3) for _ in range(3)]
        target = rng.randrange(3)
        batch.append((logits, target))
    losses = []
    for logits, target in batch:
        log_sum = math.log(sum(math.exp(z) for z in logits))
        losses.append(log_sum - logits[target])
    mean = sum(losses) / len(losses)
    lines = [f"логиты {lg}, верный класс {t}" for lg, t in batch]
    prompt = (
        "Посчитайте nn.CrossEntropyLoss() (среднее по батчу, натуральный логарифм) для батча "
        "ниже; классы нумеруются с 0. Ответ — число, округлите до тысячных."
    )
    return Instance(prompt, rounded(mean, 3), {"batch": batch}, code="\n".join(lines))


@kind(Kind.COMPUTE)
def backprop(rng: random.Random, runner: CodeRunner) -> Instance:
    x, w1, w2, t = rng.randint(1, 4), rng.randint(-2, 3), rng.randint(-2, 3), rng.randint(-5, 10)
    h_pre = w1 * x
    h = max(0, h_pre)
    y = w2 * h
    loss = (y - t) ** 2
    dy = 2 * (y - t)
    dw2 = dy * h
    dh = dy * w2
    dw1 = dh * (1 if h_pre > 0 else 0) * x
    code = (
        f"x = {x}, w1 = {w1}, w2 = {w2}, t = {t}\nh = relu(w1 * x)\ny = w2 * h\nL = (y - t) ** 2\n"
    )
    prompt = (
        "Найдите L, ∂L/∂w1 и ∂L/∂w2 (производная ReLU в нуле — 0). Ответ — три числа через пробел."
    )
    return Instance(prompt, f"{loss} {dw1} {dw2}", {"x": x, "w1": w1, "w2": w2, "t": t}, code=code)


@kind(Kind.COMPUTE)
def batchnorm(rng: random.Random, runner: CodeRunner) -> Instance:
    batch = [rng.randint(-10, 20) for _ in range(4)]
    if len(set(batch)) == 1:
        batch[0] += 3
    gamma, beta = rng.choice([1, 2, 0.5]), rng.choice([0, 1, -1])
    mean = sum(batch) / len(batch)
    var = sum((v - mean) ** 2 for v in batch) / len(batch)
    outputs = [gamma * (v - mean) / math.sqrt(var) + beta for v in batch]
    prompt = (
        f"BatchNorm в режиме обучения нормирует батч активаций {batch} по среднему и смещённой "
        f"дисперсии (делитель n, ε пренебречь), затем умножает на γ = {gamma} и прибавляет "
        f"β = {beta}. Каковы выходы? Ответ — четыре числа через пробел, округлите до сотых."
    )
    return Instance(
        prompt,
        " ".join(rounded(o, 2) for o in outputs),
        {"batch": batch, "gamma": gamma, "beta": beta},
    )


@kind(Kind.COMPUTE)
def lr_schedule(rng: random.Random, runner: CodeRunner) -> Instance:
    base = rng.choice([0.1, 0.05, 0.02, 0.01, 0.003, 0.001])
    kind = rng.choice(["step", "cosine", "cosine", "warmup"])
    epoch = rng.randint(1, 30)
    if kind == "step":
        step, gamma = rng.choice([5, 10]), rng.choice([0.1, 0.5])
        lr = base * gamma ** (epoch // step)
        rule = f"StepLR(step_size={step}, gamma={gamma})"
    elif kind == "cosine":
        total = rng.choice([30, 50, 100])
        lr = base * (1 + math.cos(math.pi * epoch / total)) / 2
        rule = f"CosineAnnealingLR(T_max={total}, eta_min=0)"
    else:
        warm = rng.choice([10, 20, 40])
        lr = base * min(1, (epoch + 1) / warm)
        rule = f"линейный разогрев: lr = base · min(1, (epoch + 1) / {warm})"
    prompt = (
        f"Базовый шаг обучения {base}, расписание {rule}. Какой шаг будет в эпоху номер {epoch} "
        "(эпохи считаются с 0, расписание обновляется в конце каждой эпохи)? Ответ — число, "
        "округлите до шести знаков после точки."
    )
    return Instance(prompt, rounded(lr, 6), {"base": base, "kind": kind, "epoch": epoch})


@kind(Kind.COMPUTE)
def max_pool(rng: random.Random, runner: CodeRunner) -> Instance:
    grid = [[rng.randint(0, 9) for _ in range(4)] for _ in range(4)]
    kind = rng.choice(["max", "avg"])
    out = []
    for i in (0, 2):
        for j in (0, 2):
            cell = [grid[i + a][j + b] for a in (0, 1) for b in (0, 1)]
            out.append(max(cell) if kind == "max" else sum(cell) / 4)
    code = "\n".join(" ".join(map(str, row)) for row in grid)
    prompt = (
        f"К карте признаков 4×4 ниже применяют {'MaxPool2d' if kind == 'max' else 'AvgPool2d'}"
        "(kernel_size=2, stride=2). Каков результат? Ответ — четыре числа через пробел по строкам."
    )
    return Instance(
        prompt, " ".join(f"{v:g}" for v in out), {"grid": grid, "kind": kind}, code=code
    )


@kind(Kind.COMPUTE)
def attention_weights(rng: random.Random, runner: CodeRunner) -> Instance:
    d = rng.choice([4, 16, 64])
    dots = [rng.randint(-8, 16) for _ in range(3)]
    exps = [math.exp(x / math.sqrt(d)) for x in dots]
    weights = [e / sum(exps) for e in exps]
    prompt = (
        f"Скалярные произведения запроса с тремя ключами: {dots}, размерность ключей d_k = {d}. "
        "Каковы веса внимания scaled dot-product attention? Ответ — три числа через пробел, "
        "округлите до тысячных."
    )
    return Instance(prompt, " ".join(rounded(w, 3) for w in weights), {"dots": dots, "d": d})


@kind(Kind.COMPUTE)
def receptive_field(rng: random.Random, runner: CodeRunner) -> Instance:
    layers = [(rng.choice([3, 5, 7]), rng.choice([1, 2])) for _ in range(rng.randint(3, 4))]
    rf, jump = 1, 1
    for k, s in layers:
        rf += (k - 1) * jump
        jump *= s
    code = "\n".join(f"Conv2d(kernel_size={k}, stride={s})" for k, s in layers)
    prompt = (
        "Свёрточные слои идут подряд, без пулинга и дилатации. Каково рецептивное поле одного "
        "выхода последнего слоя и общий шаг (во сколько раз уменьшилось разрешение)? Ответ — два "
        "числа через пробел."
    )
    return Instance(prompt, f"{rf} {jump}", {"layers": layers}, code=code)
