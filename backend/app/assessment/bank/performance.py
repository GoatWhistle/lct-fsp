"""Нагрузочное тестирование: пропускная способность, закон Литтла, перцентили, закрытая модель."""

import math
import random

from app.assessment.bank.family import Instance


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
