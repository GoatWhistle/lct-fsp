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


def _pattern(hits: list[bool]) -> str:
    return "".join("П" if hit else "М" for hit in hits)


PATTERN_RULE = "Ответ — по букве на запрос подряд: П — попадание, М — промах, например ММПМ."


def fifo_pattern(rng: random.Random) -> Instance:
    capacity = rng.randint(2, 3)
    requests = _requests(rng, KEYS[: capacity + 2], rng.randint(9, 11))
    cache: list[str] = []
    hits = []
    for key in requests:
        hits.append(key in cache)
        if key not in cache:
            cache.append(key)
            if len(cache) > capacity:
                cache.pop(0)
    prompt = (
        f"Кэш на {capacity} элемента вытесняет то, что попало в него раньше всех (FIFO); "
        f"попадание порядок не меняет. Сначала кэш пуст. Запросы: {' '.join(requests)}. "
        + PATTERN_RULE
    )
    return Instance(prompt, _pattern(hits), {"capacity": capacity, "requests": requests})


def ttl_pattern(rng: random.Random) -> Instance:
    ttl = rng.choice([10, 30, 60])
    keys = KEYS[: rng.randint(2, 3)]
    moments = sorted(rng.sample(range(0, 4 * ttl), rng.randint(8, 10)))
    requests = [(t, rng.choice(keys)) for t in moments]
    loaded: dict[str, int] = {}
    hits = []
    for t, key in requests:
        hit = key in loaded and t - loaded[key] < ttl
        hits.append(hit)
        if not hit:
            loaded[key] = t
    lines = [f"{t} с — {key}" for t, key in requests]
    prompt = (
        f"Кэш хранит значение {ttl} с с момента загрузки: запрос в момент загрузки + {ttl} и "
        "позже — уже промах, он загружает значение заново. Попадание срок не продлевает. "
        "Сначала кэш пуст. " + PATTERN_RULE
    )
    return Instance(
        prompt, _pattern(hits), {"ttl": ttl, "requests": requests}, code="\n".join(lines)
    )


def lru_pattern(rng: random.Random) -> Instance:
    capacity = rng.randint(2, 3)
    requests = _requests(rng, KEYS[: capacity + 2], rng.randint(9, 11))
    cache: OrderedDict[str, None] = OrderedDict()
    hits = []
    for key in requests:
        hits.append(key in cache)
        if key in cache:
            cache.move_to_end(key)
        else:
            cache[key] = None
            if len(cache) > capacity:
                cache.popitem(last=False)
    prompt = (
        f"LRU-кэш на {capacity} элемента, сначала пуст. Запросы: {' '.join(requests)}. "
        + PATTERN_RULE
    )
    return Instance(prompt, _pattern(hits), {"capacity": capacity, "requests": requests})


def partition_counts(rng: random.Random) -> Instance:
    partitions = rng.randint(3, 5)
    messages = [
        (rng.choice(["user-", "order-", "cart-"]) + str(rng.randint(1, 99)))
        for _ in range(rng.randint(8, 11))
    ]
    hashes = {m: rng.randint(100, 999) for m in messages}
    counts = [0] * partitions
    for m in messages:
        counts[hashes[m] % partitions] += 1
    lines = [f"{m}: hash = {hashes[m]}" for m in messages]
    prompt = (
        f"В топике {partitions} партиции, номер партиции сообщения — hash(key) mod "
        f"{partitions}. Ключи сообщений и их хэши ниже. Сколько сообщений попадёт в каждую "
        f"партицию? Ответ — {partitions} чисел через пробел, от партиции 0."
    )
    params = {"partitions": partitions, "hashes": hashes}
    return Instance(prompt, " ".join(map(str, counts)), params, code="\n".join(lines))


def consumer_assignment(rng: random.Random) -> Instance:
    partitions = rng.randint(5, 12)
    consumers = sorted(rng.sample(["c1", "c2", "c3", "c4"], rng.randint(2, 4)))
    strategy = rng.choice(["range", "roundrobin"])
    target = rng.choice(consumers)
    k = consumers.index(target)
    n = len(consumers)
    if strategy == "range":
        size, extra = divmod(partitions, n)
        start = k * size + min(k, extra)
        assigned = list(range(start, start + size + (1 if k < extra else 0)))
        rule = (
            "range: партиции идут подряд, каждому консьюмеру по ⌊P/C⌋, первые P mod C "
            "консьюмеров получают на одну больше"
        )
    else:
        assigned = list(range(k, partitions, n))
        rule = "round-robin: партиции раздаются по кругу в порядке консьюмеров"
    prompt = (
        f"В топике партиции 0–{partitions - 1}, в группе консьюмеры {', '.join(consumers)} "
        f"(в этом порядке). Стратегия {rule}. Какие партиции достанутся {target}? Ответ — "
        "номера через пробел по возрастанию."
    )
    params = {
        "partitions": partitions,
        "consumers": consumers,
        "strategy": strategy,
        "target": target,
    }
    return Instance(prompt, " ".join(map(str, assigned)), params)


def redelivery(rng: random.Random) -> Instance:
    first = rng.randint(1, 500)
    total = rng.randint(10, 16)
    batch = rng.randint(2, 5)
    crash_after = rng.choice([n for n in range(batch + 1, total) if n % batch])
    ids = list(range(first, first + total))
    committed = (crash_after // batch) * batch
    again = ids[committed:crash_after]
    prompt = (
        f"Консьюмер читает сообщения с id {ids[0]}–{ids[-1]} по порядку и фиксирует offset "
        f"после каждых {batch} обработанных сообщений. Обработав {crash_after} сообщений, он "
        "упал, не успев ничего зафиксировать сверх последнего коммита, и после перезапуска "
        "продолжил с зафиксированного offset. Какие сообщения будут обработаны повторно? "
        "Ответ — их id через пробел; если таких нет — 0."
    )
    params = {"first": first, "total": total, "batch": batch, "crash_after": crash_after}
    return Instance(prompt, " ".join(map(str, again)) or "0", params)


def moved_keys(rng: random.Random) -> Instance:
    shards = rng.randint(3, 6)
    keys = sorted(rng.sample(range(10, 200), 8))
    moved = [k for k in keys if k % shards != k % (shards + 1)]
    prompt = (
        f"Ключи раскладываются по шардам как key % N, сейчас N = {shards}. Ключи: "
        f"{', '.join(map(str, keys))}. Какие ключи сменят шард, когда N станет {shards + 1}? "
        "Ответ — ключи через пробел по возрастанию; если таких нет — 0."
    )
    return Instance(prompt, " ".join(map(str, moved)) or "0", {"shards": shards, "keys": keys})


def hash_ring(rng: random.Random) -> Instance:
    nodes = dict(zip(rng.sample("ABCDE", 4), sorted(rng.sample(range(0, 360), 4)), strict=True))
    keys = {f"k{i}": rng.randint(0, 359) for i in range(1, 6)}
    ordered = sorted(nodes.items(), key=lambda item: item[1])

    def owner(position: int) -> str:
        return next((n for n, p in ordered if p >= position), ordered[0][0])

    lines = [f"узел {n}: {p}" for n, p in ordered] + [f"ключ {k}: {p}" for k, p in keys.items()]
    prompt = (
        "Консистентное хэширование: кольцо позиций 0–359, ключ хранится на первом узле по "
        "часовой стрелке — с позицией не меньше позиции ключа, а после 359 отсчёт идёт с 0. "
        "На каких узлах окажутся ключи k1–k5? Ответ — буквы узлов подряд в порядке ключей."
    )
    answer = "".join(owner(p) for p in keys.values())
    return Instance(prompt, answer, {"nodes": nodes, "keys": keys}, code="\n".join(lines))


def vector_clock(rng: random.Random) -> Instance:
    procs = ["P1", "P2", "P3"]
    clocks = {p: [0, 0, 0] for p in procs}
    events: list[str] = []
    inbox: list[tuple[str, list[int], str]] = []
    for i in range(rng.randint(8, 10)):
        p = rng.choice(procs)
        idx = procs.index(p)
        receivable = [m for m in inbox if m[0] == p]
        if receivable and rng.random() < 0.6:
            message = receivable[0]
            inbox.remove(message)
            clocks[p] = [max(a, b) for a, b in zip(clocks[p], message[1], strict=True)]
            clocks[p][idx] += 1
            events.append(f"{i + 1}. {p} получает {message[2]}")
        elif rng.random() < 0.6:
            to = rng.choice([q for q in procs if q != p])
            clocks[p][idx] += 1
            name = f"m{len(events) + 1}"
            inbox.append((to, list(clocks[p]), name))
            events.append(f"{i + 1}. {p} отправляет {name} процессу {to}")
        else:
            clocks[p][idx] += 1
            events.append(f"{i + 1}. {p}: локальное событие")
    # Спрашиваем про процесс с самыми интересными часами — где больше всего событий.
    target = max(procs, key=lambda p: (sum(clocks[p]), procs.index(p)))
    prompt = (
        "Векторные часы: у каждого процесса вектор [P1, P2, P3], сначала нули. Любое событие "
        "(локальное, отправка, получение) увеличивает свою компоненту на 1; при получении "
        "сначала берётся поэлементный максимум со штампом сообщения. Каким будет вектор "
        f"{target} после всех событий? Ответ — три числа через пробел."
    )
    params = {"events": events, "target": target}
    return Instance(prompt, " ".join(map(str, clocks[target])), params, code="\n".join(events))


def circuit_breaker(rng: random.Random) -> Instance:
    threshold, cooldown = rng.randint(2, 3), rng.choice([10, 20, 30])
    moments = sorted(rng.sample(range(0, 80), rng.randint(9, 11)))
    outcomes = [rng.random() < 0.55 for _ in moments]  # True — сервис ответил бы ошибкой
    state, failures, opened_at = "closed", 0, 0
    results = []
    for t, fails in zip(moments, outcomes, strict=True):
        if state == "open" and t - opened_at >= cooldown:
            state = "half"
        if state == "open":
            results.append("О")
            continue
        results.append("Е" if fails else "У")
        if fails:
            failures += 1
            if state == "half" or failures >= threshold:
                state, opened_at, failures = "open", t, 0
        else:
            state, failures = "closed", 0
    lines = [
        f"{t} с — сервис {'упадёт' if f else 'ответит'}"
        for t, f in zip(moments, outcomes, strict=True)
    ]
    prompt = (
        f"Предохранитель (circuit breaker) размыкается после {threshold} ошибок подряд и "
        f"{cooldown} с отклоняет вызовы сразу. После паузы пропускает пробный вызов: успех "
        "замыкает его, ошибка снова размыкает на ту же паузу. Что получит каждый вызов? Ответ — "
        "по букве на вызов подряд: У — успех, Е — ошибка сервиса, О — отклонён предохранителем."
    )
    params = {
        "threshold": threshold,
        "cooldown": cooldown,
        "moments": moments,
        "outcomes": outcomes,
    }
    return Instance(prompt, "".join(results), params, code="\n".join(lines))


def quorum_checks(rng: random.Random) -> Instance:
    configs = [(n, rng.randint(1, n), rng.randint(1, n)) for n in rng.choices([3, 5, 7], k=4)]
    lines = [f"{i}. N = {n}, W = {w}, R = {r}" for i, (n, w, r) in enumerate(configs, 1)]
    answers = []
    for n, w, r in configs:
        answers.append(str(r + w - n if r + w > n else 0))
    prompt = (
        "Для каждой конфигурации реплик (N — реплик, W — подтверждений записи, R — опрашиваемых "
        "при чтении): на скольких репликах множество чтения гарантированно пересечётся с "
        "множеством последней подтверждённой записи? Если пересечение не гарантировано — 0. "
        "Ответ — четыре числа через пробел."
    )
    return Instance(prompt, " ".join(answers), {"configs": configs}, code="\n".join(lines))


def replica_reads(rng: random.Random) -> Instance:
    lag = rng.choice([3, 4, 5, 6, 8])
    values = rng.sample(range(10, 100), 3)
    writes = [rng.randint(1, 6)]
    writes.append(writes[0] + rng.randint(2, lag + 2))
    reads = sorted(rng.sample(range(writes[0], writes[1] + 2 * lag), 5))
    sources = [rng.choice(["ведущего", "реплики", "реплики"]) for _ in reads]

    def seen(t: int, source: str) -> int:
        delay = 0 if source == "ведущего" else lag
        applied = [v for w, v in zip(writes, values[1:], strict=True) if t >= w + delay]
        return applied[-1] if applied else values[0]

    answer = [seen(t, s) for t, s in zip(reads, sources, strict=True)]
    lines = [f"{t} с — чтение с {s}" for t, s in zip(reads, sources, strict=True)]
    prompt = (
        f"Значение было {values[0]}. Клиент записал на ведущий узел {values[1]} в момент "
        f"{writes[0]} с и {values[2]} в момент {writes[1]} с. Реплика применяет каждую запись "
        f"с отставанием ровно {lag} с: запись момента t видна на ней с момента t + {lag}. Какие "
        "значения увидят чтения? Ответ — числа через пробел по порядку чтений."
    )
    params = {"lag": lag, "values": values, "writes": writes, "reads": reads, "sources": sources}
    return Instance(prompt, " ".join(map(str, answer)), params, code="\n".join(lines))
