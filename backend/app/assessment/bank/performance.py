"""Нагрузочное тестирование: пропускная способность, закон Литтла, перцентили, закрытая модель."""

import math
import random

from app.assessment.bank.family import Instance, rounded


def throughput(rng: random.Random) -> Instance:
    rps, seconds = rng.randint(5, 400), rng.choice([10, 30, 60, 120, 300])
    prompt = (
        f"За {seconds} с нагрузочный тест отправил {rps * seconds} запросов, все получили ответ. "
        "Какова средняя пропускная способность, запросов в секунду?"
    )
    return Instance(prompt, str(rps), {"requests": rps * seconds, "seconds": seconds})


def littles_law(rng: random.Random) -> Instance:
    rps, latency_ms = rng.randrange(50, 2000, 50), rng.choice([20, 40, 80, 100, 200, 400])
    in_flight = rps * latency_ms // 1000
    prompt = (
        f"Сервис стабильно обрабатывает {rps} запросов в секунду, среднее время ответа — "
        f"{latency_ms} мс. Сколько запросов в среднем одновременно находятся в обработке?"
    )
    return Instance(prompt, str(in_flight), {"rps": rps, "latency_ms": latency_ms})


def percentile(rng: random.Random) -> Instance:
    n, p = rng.choice([10, 20]), rng.choice([50, 90, 95])
    latencies = rng.sample(range(40, 900), n)
    rank = math.ceil(p / 100 * n)
    answer = sorted(latencies)[rank - 1]
    prompt = (
        f"Время ответов в миллисекундах: {', '.join(map(str, latencies))}. Найдите p{p} методом "
        "ближайшего ранга: k-я по возрастанию величина, где k = ⌈p/100 · n⌉."
    )
    return Instance(prompt, str(answer), {"latencies": latencies, "p": p})


def closed_model(rng: random.Random) -> Instance:
    response, think = rng.choice([0.5, 1, 2]), rng.choice([1, 2, 3, 4, 8])
    cycle = response + think
    target = rng.randint(2, 50)
    users = target * cycle
    if not users.is_integer():
        target, users = target * 2, target * cycle * 2
    if rng.random() < 0.5:
        question = f"Сколько виртуальных пользователей нужно, чтобы держать нагрузку {target} RPS?"
        answer = int(users)
    else:
        question = (
            f"Какую пропускную способность в RPS покажет тест, если виртуальных пользователей — "
            f"{int(users)}?"
        )
        answer = target
    prompt = (
        f"Закрытая модель нагрузки: каждый виртуальный пользователь отправляет запрос, ждёт ответ "
        f"({response} с), делает паузу {think} с и повторяет. {question} Ответ — целое число."
    )
    params = {"response": response, "think": think, "users": int(users), "target": target}
    return Instance(prompt, str(answer), params)


def error_rate(rng: random.Random) -> Instance:
    total = rng.randint(2000, 90000)
    errors = rng.randint(1, total // 20)
    timeouts = rng.randint(0, total // 50)
    rate = 100 * (errors + timeouts) / total
    prompt = (
        f"Нагрузочный тест отправил {total} запросов: {errors} получили 5xx, {timeouts} не "
        "дождались ответа за таймаут, остальные успешны. Какая доля неуспешных запросов? Ответ "
        "— процент, округлите до сотых."
    )
    return Instance(
        prompt, f"{rounded(rate, 2)}", {"total": total, "errors": errors, "timeouts": timeouts}
    )


def apdex(rng: random.Random) -> Instance:
    threshold = rng.choice([100, 200, 300, 500])
    latencies = [rng.randint(20, 6 * threshold) for _ in range(rng.randint(10, 14))]
    satisfied = sum(1 for x in latencies if x <= threshold)
    tolerating = sum(1 for x in latencies if threshold < x <= 4 * threshold)
    score = (satisfied + tolerating / 2) / len(latencies)
    prompt = (
        f"Apdex с порогом T = {threshold} мс: довольны ответы не дольше T, терпят — не дольше "
        "4T, остальные недовольны; Apdex = (довольные + терпящие / 2) / все. Время ответов, мс: "
        f"{', '.join(map(str, latencies))}. Сколько ответов довольны, сколько терпят и каков "
        "Apdex? Ответ — три числа через пробел, Apdex округлите до сотых."
    )
    answer = f"{satisfied} {tolerating} {rounded(score, 2)}"
    return Instance(prompt, answer, {"threshold": threshold, "latencies": latencies})


def ramp_up(rng: random.Random) -> Instance:
    users = rng.randint(10, 200)
    ramp = rng.choice([30, 60, 120, 300])
    hold = rng.choice([60, 120, 300])
    pacing = rng.choice([1, 2, 5, 10])
    # Пользователи стартуют равномерно за время разгона, каждый шлёт запрос раз в pacing секунд.
    requests = users * hold / pacing + users * ramp / 2 / pacing
    prompt = (
        f"Сценарий: {users} виртуальных пользователей стартуют равномерно за {ramp} с (разгон), "
        f"затем нагрузка держится {hold} с. Каждый активный пользователь отправляет запрос раз в "
        f"{pacing} с. Сколько запросов отправит тест за разгон и удержание вместе? Считайте "
        "приближённо: на разгоне в среднем активна половина пользователей. Ответ — число."
    )
    params = {"users": users, "ramp": ramp, "hold": hold, "pacing": pacing}
    return Instance(prompt, f"{requests:g}", params)


def pacing_rps(rng: random.Random) -> Instance:
    users = rng.randint(5, 300)
    response = rng.choice([0.2, 0.5, 1.0, 1.5])
    pacing = rng.choice([2, 3, 4, 5, 10])
    rps = users / pacing
    prompt = (
        f"{users} виртуальных пользователей работают с фиксированным пейсингом {pacing} с: новая "
        f"итерация начинается раз в {pacing} с, если предыдущая успела закончиться. Ответ "
        f"сервера занимает {response} с, в итерации один запрос. Какую нагрузку в RPS создаст "
        "тест? Ответ — число, округлите до десятых."
    )
    return Instance(
        prompt, f"{rounded(rps, 1)}", {"users": users, "response": response, "pacing": pacing}
    )


def percentile_linear(rng: random.Random) -> Instance:
    n = rng.randint(6, 11)
    p = rng.choice([50, 75, 90, 95])
    latencies = rng.sample(range(40, 900), n)
    ordered = sorted(latencies)
    position = (n - 1) * p / 100
    low = math.floor(position)
    high = min(low + 1, n - 1)
    value = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    prompt = (
        f"Время ответов в миллисекундах: {', '.join(map(str, latencies))}. Найдите p{p} с "
        "линейной интерполяцией, как numpy.percentile по умолчанию: позиция (n − 1) · p / 100 "
        "в отсортированном ряду с нумерацией с нуля. Ответ — число, округлите до десятых."
    )
    return Instance(prompt, f"{rounded(value, 1)}", {"latencies": latencies, "p": p})


def queue_utilization(rng: random.Random) -> Instance:
    service_ms = rng.choice([5, 10, 20, 25, 40, 50])
    capacity = 1000 / service_ms
    rps = round(capacity * rng.choice([0.5, 0.6, 0.7, 0.75, 0.8, 0.9]))
    rho = rps / capacity
    response = service_ms / (1 - rho)
    prompt = (
        f"Сервис обрабатывает запросы по одному, среднее время обработки — {service_ms} мс, "
        f"поток запросов пуассоновский, {rps} запросов в секунду (модель M/M/1). Какова загрузка "
        "сервиса и среднее время ответа с учётом ожидания в очереди? Ответ — два числа через "
        "пробел: загрузка в процентах до целых и время в мс до десятых."
    )
    return Instance(
        prompt,
        f"{rounded(100 * rho, 0)} {rounded(response, 1)}",
        {"service_ms": service_ms, "rps": rps},
    )


def capacity_headroom(rng: random.Random) -> Instance:
    rps = rng.randrange(100, 2000, 50)
    cpu = rng.randint(15, 60)
    target = rng.choice([60, 70, 75, 80])
    nodes = rng.randint(2, 6)
    max_rps = rps * target / cpu
    prompt = (
        f"Кластер из {nodes} одинаковых узлов держит {rps} RPS при загрузке CPU {cpu} %, "
        "нагрузка делится поровну, CPU растёт линейно с RPS. Какой RPS выдержит кластер, пока "
        f"CPU не выше {target} %, и сколько RPS это на один узел? Ответ — два числа через пробел, "
        "округлите до целых."
    )
    params = {"rps": rps, "cpu": cpu, "target": target, "nodes": nodes}
    return Instance(prompt, f"{rounded(max_rps, 0)} {rounded(max_rps / nodes, 0)}", params)


def histogram_quantile(rng: random.Random) -> Instance:
    bounds = sorted(rng.sample([50, 100, 200, 300, 500, 750, 1000, 2000], 5))
    counts = [rng.randint(5, 60) for _ in bounds]
    total = sum(counts)
    q = rng.choice([0.5, 0.9, 0.95, 0.99])
    rank = q * total
    cumulative, lower = 0, 0
    value = float(bounds[-1])
    for bound, count in zip(bounds, counts, strict=True):
        if cumulative + count >= rank:
            value = lower + (bound - lower) * (rank - cumulative) / count
            break
        cumulative += count
        lower = bound
    buckets = []
    running = 0
    for bound, count in zip(bounds, counts, strict=True):
        running += count
        buckets.append(f'le="{bound}": {running}')
    buckets.append(f'le="+Inf": {running}')
    prompt = (
        f"Гистограмма времени ответа (накопительные счётчики, мс) ниже. Найдите квантиль {q} так, "
        "как считает histogram_quantile в Prometheus: найти корзину, где накопленный счётчик "
        "достигает q · всего, и интерполировать линейно внутри неё (нижняя граница первой корзины "
        "— 0). Ответ — число, округлите до десятых."
    )
    params = {"bounds": bounds, "counts": counts, "q": q}
    return Instance(prompt, f"{rounded(value, 1)}", params, code="\n".join(buckets))
