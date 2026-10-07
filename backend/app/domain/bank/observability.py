"""Мониторинг и логирование: объём логов, кардинальность меток, бюджет ошибок, доступность
цепочки, rate по счётчику со сбросом, правило алерта с for, burn rate, сэмплирование трасс."""

import math
import random
from itertools import pairwise

from app.domain.bank.family import Instance, rounded


def log_retention(rng: random.Random) -> Instance:
    per_day = rng.choice([20, 35, 50, 80, 120, 200])
    ratio = rng.choice([4, 5, 8, 10])
    days = rng.choice([7, 14, 30, 90])
    replicas = rng.randint(1, 3)
    disk = rng.choice([500, 1000, 2000, 4000])
    stored = per_day / ratio * days * replicas
    # Сколько полных суток пишем, пока не упрёмся в диск при росте на per_day/ratio·replicas.
    fits = math.floor(disk / (per_day / ratio * replicas))
    prompt = (
        f"Сервисы пишут {per_day} ГБ логов в сутки, хранилище сжимает их в {ratio} раз и держит "
        f"{replicas} копии (реплики) каждого сегмента, срок хранения — {days} суток. Сколько ГБ "
        f"займут логи в установившемся режиме и сколько полных суток логов поместится на "
        f"кластер на {disk} ГБ? Ответ — два числа через пробел, первое округлите до десятых."
    )
    return Instance(
        prompt,
        f"{rounded(stored, 1)} {fits}",
        {"per_day": per_day, "ratio": ratio, "days": days, "replicas": replicas, "disk": disk},
    )


def label_cardinality(rng: random.Random) -> Instance:
    methods = rng.randint(2, 6)
    statuses = rng.randint(3, 8)
    paths = rng.randint(5, 40)
    instances = rng.randint(2, 12)
    buckets = rng.choice([0, 8, 10, 12])
    users = rng.choice([1000, 5000, 20000])
    base = methods * statuses * paths * instances
    # У гистограммы по ряду на каждую корзину le плюс _sum и _count.
    series = base * (buckets + 2 if buckets else 1)
    kind = (
        f"гистограмма с {buckets} корзинами le (вместе с +Inf), плюс _sum и _count"
        if buckets
        else "счётчик"
    )
    prompt = (
        f"Метрика http_requests — {kind}. Метки: method ({methods} значений), status "
        f"({statuses}), path ({paths}), instance ({instances}); встречаются все сочетания. "
        f"Сколько временных рядов она даёт и сколько станет, если добавить метку user_id "
        f"({users} пользователей, каждый ходит во все сочетания)? Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{series} {series * users}",
        {"methods": methods, "statuses": statuses, "paths": paths, "buckets": buckets},
    )


def error_budget(rng: random.Random) -> Instance:
    slo = rng.choice([99.0, 99.5, 99.9, 99.95])
    days = rng.choice([28, 30])
    budget = days * 24 * 60 * (100 - slo) / 100
    incidents = [
        rng.choice([3, 5, 8, 12, 15, 20, 30, 45, 60, 90]) for _ in range(rng.randint(1, 4))
    ]
    spent = sum(incidents)
    left = max(0.0, budget - spent)
    prompt = (
        f"SLO доступности — {slo:g} % за скользящие {days} суток. За это окно были "
        f"инциденты полной недоступности длительностью {', '.join(map(str, incidents))} мин. "
        "Каков бюджет ошибок в минутах и сколько процентов бюджета осталось (не меньше 0)? "
        "Ответ — два числа через пробел, округлите до десятых."
    )
    return Instance(
        prompt,
        f"{rounded(budget, 1)} {rounded(100 * left / budget, 1)}",
        {"slo": slo, "days": days, "incidents": incidents},
    )


def availability_chain(rng: random.Random) -> Instance:
    values = [99.9, 99.95, 99.5, 99.0, 98.0, 99.99]
    a, b, c = (rng.choice(values) for _ in range(3))
    replicas = rng.randint(2, 3)
    serial = a / 100 * b / 100
    pooled = 1 - (1 - c / 100) ** replicas
    total = serial * pooled
    prompt = (
        f"Запрос проходит последовательно через балансировщик (доступность {a:g} %), "
        f"сервис ({b:g} %) и базу, у которой {replicas} независимые реплики по "
        f"{c:g} %: база доступна, если жива хотя бы одна. Отказы независимы. Какова "
        "доступность базы и всей цепочки? Ответ — два процента через пробел, округлите до "
        "тысячных."
    )
    return Instance(
        prompt,
        f"{rounded(100 * pooled, 3)} {rounded(100 * total, 3)}",
        {"a": a, "b": b, "c": c, "replicas": replicas},
    )


def counter_rate(rng: random.Random) -> Instance:
    step = 15
    count = rng.randint(6, 9)
    values = [rng.randint(100, 900)]
    reset_at = rng.randrange(2, count)
    for i in range(1, count):
        if i == reset_at:
            values.append(rng.randint(0, 40))
        else:
            values.append(values[-1] + rng.randint(0, 60))
    increase = 0
    for prev, cur in pairwise(values):
        # Сброс счётчика: значение после сброса — уже прирост от нуля.
        increase += cur - prev if cur >= prev else cur
    window = step * (count - 1)
    rate = increase / window
    lines = [f"t={i * step:>3} с: {v}" for i, v in enumerate(values)]
    prompt = (
        "Отсчёты счётчика http_requests_total за окно ниже (процесс один раз перезапускался). "
        "Посчитайте прирост, как increase в Prometheus, но без экстраполяции к краям окна: "
        "сумма приростов между соседними отсчётами с учётом сброса; и rate — прирост на секунду "
        "между первым и последним отсчётом. Ответ — два числа через пробел, rate округлите до "
        "сотых."
    )
    return Instance(
        prompt,
        f"{increase} {rounded(rate, 2)}",
        {"values": values},
        code="\n".join(lines),
    )


def alert_for(rng: random.Random) -> Instance:
    threshold = rng.choice([80, 90, 95])
    hold = rng.randint(2, 5)
    # Чередуем отрезки ниже и выше порога; хотя бы один отрезок выше порога длиннее for.
    runs: list[tuple[bool, int]] = []
    high = rng.random() < 0.3
    while sum(n for _, n in runs) < 14:
        runs.append((high, rng.randint(1, hold + 3)))
        high = not high
    if not any(h and n > hold for h, n in runs):
        runs.append((True, hold + rng.randint(1, 3)))
        runs.append((False, rng.randint(1, 3)))
    samples = [
        rng.randint(threshold + 1, 100) if h else rng.randint(40, threshold)
        for h, n in runs
        for _ in range(n)
    ]
    firing = []
    resolved = []
    since = None
    state = "inactive"
    for minute, value in enumerate(samples):
        if value > threshold:
            if state == "inactive":
                state, since = "pending", minute
            if state == "pending" and since is not None and minute - since >= hold:
                state = "firing"
                firing.append(minute)
        else:
            if state == "firing":
                resolved.append(minute)
            state, since = "inactive", None
    lines = [f"минута {m}: {v}" for m, v in enumerate(samples)]
    prompt = (
        f"Правило алерта: expr: cpu_usage > {threshold}, for: {hold}m; правила вычисляются раз "
        "в минуту, в минуты ниже. На каких минутах алерт переходит в firing и на каких — в "
        "resolved? Ответ — минуты firing через пробел, затем «|», затем минуты resolved; если "
        "переходов нет — «нет» на месте списка."
    )
    answer = f"{' '.join(map(str, firing)) or 'нет'} | {' '.join(map(str, resolved)) or 'нет'}"
    return Instance(
        prompt,
        answer,
        {"threshold": threshold, "hold": hold, "samples": samples},
        code="\n".join(lines),
    )


def burn_rate(rng: random.Random) -> Instance:
    slo = rng.choice([99.9, 99.5, 99.0])
    budget = (100 - slo) / 100
    rows = []
    verdicts = []
    for _ in range(5):
        # Сначала исход, потом burn rate окон под него — с одним окном у порога для отвода глаз.
        verdict = rng.choice(["page", "ticket", "нет"])
        long_page: float
        short_page: float
        long_ticket: float
        short_ticket: float
        if verdict == "page":
            long_page = rng.choice([15, 20, 40])
            short_page = long_page * rng.choice([1, 1.5])
        else:
            long_page, short_page = rng.choice([(2, 3), (5, 10), (10, 20), (20, 6), (40, 12)])
        if verdict == "ticket" or (verdict == "page" and rng.random() < 0.5):
            long_ticket = rng.choice([8, 10, 12])
            short_ticket = long_ticket * rng.choice([1, 1.5])
        else:
            long_ticket, short_ticket = rng.choice([(0.5, 1), (2, 8), (5, 7.5), (8, 4)])
        rows.append(tuple(x * budget for x in (long_page, short_page, long_ticket, short_ticket)))
        verdicts.append(verdict)

    def pct(x: float) -> str:
        return f"{x * 100:.3g} %"

    lines = [
        f"{i}. ошибок за 1 ч — {pct(lp)}, за 5 мин — {pct(sp)}, за 6 ч — {pct(lt)}, "
        f"за 30 мин — {pct(st)}"
        for i, (lp, sp, lt, st) in enumerate(rows, 1)
    ]
    prompt = (
        f"SLO — {slo:g} % успешных запросов, burn rate — доля ошибок, делённая на "
        "долю бюджета (1 − SLO). Алерты: page, если burn rate за 1 ч и за 5 мин оба больше "
        "14,4; иначе ticket, если за 6 ч и за 30 мин оба больше 6. Что сработает в каждой "
        "ситуации? Ответ — page, ticket или «нет» для каждой через пробел."
    )
    return Instance(
        prompt,
        " ".join(verdicts),
        {"slo": slo, "rows": rows},
        code="\n".join(lines),
    )


def trace_sampling(rng: random.Random) -> Instance:
    traces = rng.choice([10000, 20000, 50000, 100000])
    head = rng.choice([1, 5, 10, 20])
    errors = rng.randint(50, 900)
    slow = rng.randint(100, 2000)
    both = rng.randint(0, min(errors, slow) // 2)
    rest = rng.choice([1, 2, 5])
    head_kept = traces * head / 100
    head_errors = errors * head / 100
    # Хвостовое сэмплирование: все с ошибкой или медленные, из остальных — rest %.
    special = errors + slow - both
    tail_kept = special + (traces - special) * rest / 100
    prompt = (
        f"За час — {traces} трасс, из них {errors} с ошибкой и {slow} медленных; {both} и с "
        f"ошибкой, и медленные. Вариант 1: головное сэмплирование {head} % — решение на входе, "
        "все сервисы его соблюдают. Вариант 2: хвостовое — сохраняются все трассы с ошибкой или "
        f"медленные и {rest} % остальных. Сколько трасс сохранится в каждом варианте и сколько "
        "трасс с ошибкой в среднем попадёт в первый? Ответ — три числа через пробел, при "
        "необходимости округлите до десятых."
    )
    answer = " ".join(rounded(v, 1) for v in (head_kept, tail_kept, head_errors))
    return Instance(
        prompt,
        answer,
        {"traces": traces, "head": head, "errors": errors, "slow": slow, "both": both},
    )
