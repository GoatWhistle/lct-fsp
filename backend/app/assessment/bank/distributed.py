"""Очереди, кэши и распределённые системы: попадания в кэш, шардирование, кворумы."""

import random
from collections import OrderedDict

from app.assessment.bank.family import Instance

KEYS = "abcdefgh"


def _requests(rng: random.Random, alphabet: str, n: int) -> list[str]:
    return [rng.choice(alphabet) for _ in range(n)]


def cache_hits(rng: random.Random) -> Instance:
    requests = _requests(rng, KEYS[: rng.randint(4, 7)], rng.randint(9, 14))
    hits = len(requests) - len(set(requests))
    prompt = (
        "Кэш без ограничения размера, сначала пуст. Промах загружает значение в кэш. Запросы по "
        f"ключам: {' '.join(requests)}. Сколько запросов попадут в кэш?"
    )
    return Instance(prompt, str(hits), {"requests": requests})


def lru_hits(rng: random.Random) -> Instance:
    capacity = rng.randint(2, 3)
    requests = _requests(rng, KEYS[: capacity + 2], rng.randint(10, 13))
    cache: OrderedDict[str, None] = OrderedDict()
    hits = 0
    for key in requests:
        if key in cache:
            hits += 1
            cache.move_to_end(key)
        else:
            cache[key] = None
            if len(cache) > capacity:
                cache.popitem(last=False)
    prompt = (
        f"LRU-кэш на {capacity} элемента, сначала пуст. Запросы по ключам: {' '.join(requests)}. "
        "Сколько запросов попадут в кэш?"
    )
    return Instance(prompt, str(hits), {"capacity": capacity, "requests": requests})


def rehash_moves(rng: random.Random) -> Instance:
    shards = rng.randint(3, 6)
    keys = sorted(rng.sample(range(10, 200), 10))
    moved = sum(1 for k in keys if k % shards != k % (shards + 1))
    prompt = (
        f"Ключи раскладываются по шардам как key % N, сейчас N = {shards}. Ключи: "
        f"{', '.join(map(str, keys))}. Сколько ключей сменят шард, когда N станет {shards + 1}?"
    )
    return Instance(prompt, str(moved), {"shards": shards, "keys": keys})


def quorum(rng: random.Random) -> Instance:
    replicas = rng.choice([3, 5, 7, 9])
    write = rng.randint(1, replicas)
    params: dict[str, int | None] = {"replicas": replicas, "write": write, "read": None}
    if rng.random() < 0.5:
        question = (
            "Какое наименьшее число реплик R нужно опрашивать при чтении, чтобы чтение "
            "гарантированно увидело последнюю подтверждённую запись?"
        )
        answer = replicas - write + 1
    else:
        read = rng.randint(replicas - write + 1, replicas)
        params["read"] = read
        question = (
            f"Чтение опрашивает R реплик, R = {read}. Сколько реплик может отказать одновременно, "
            "чтобы и запись, и чтение оставались доступны?"
        )
        answer = replicas - max(write, read)
    prompt = (
        f"Данные хранятся на {replicas} репликах, запись подтверждается, когда её приняли W "
        f"реплик, W = {write}. {question}"
    )
    return Instance(prompt, str(answer), params)
