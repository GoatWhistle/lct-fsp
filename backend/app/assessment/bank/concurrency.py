"""Конкурентность и асинхронность: пул потоков, asyncio, гонки."""

import heapq
import random

from app.assessment.bank.family import Instance, rounded


def pool_rounds(rng: random.Random) -> Instance:
    tasks, workers, seconds = rng.randint(5, 40), rng.randint(2, 8), rng.randint(2, 9)
    prompt = (
        f"{tasks} независимых задач, каждая выполняется ровно {seconds} с и не ждёт ввода-вывода. "
        f"Их отдают в пул из {workers} рабочих процессов. Через сколько секунд завершится "
        "последняя задача? Ответ — число."
    )
    answer = -(-tasks // workers) * seconds
    return Instance(prompt, str(answer), {"tasks": tasks, "workers": workers, "seconds": seconds})


def asyncio_gather(rng: random.Random) -> Instance:
    lines, total = [], 0
    for _ in range(rng.randint(2, 3)):
        if rng.random() < 0.6:
            delays = [rng.randint(1, 9) for _ in range(rng.randint(2, 3))]
            calls = ", ".join(f"asyncio.sleep({d})" for d in delays)
            lines.append(f"    await asyncio.gather({calls})")
            total += max(delays)
        else:
            delay = rng.randint(1, 9)
            lines.append(f"    await asyncio.sleep({delay})")
            total += delay
    code = "import asyncio\n\nasync def main():\n" + "\n".join(lines) + "\n\nasyncio.run(main())\n"
    prompt = "Сколько секунд будет работать программа? Накладными расходами пренебречь."
    return Instance(prompt, str(total), {"lines": lines}, code=code)


def pool_makespan(rng: random.Random) -> Instance:
    workers = rng.randint(2, 3)
    durations = [rng.randint(1, 9) for _ in range(rng.randint(6, 8))]
    free_at = [0] * workers
    for d in durations:
        start = heapq.heappop(free_at)
        heapq.heappush(free_at, start + d)
    prompt = (
        f"Задачи с длительностями {', '.join(map(str, durations))} (секунды) отправлены по "
        f"порядку в пул из {workers} потоков. Освободившийся поток сразу берёт следующую задачу из "
        "очереди. Через сколько секунд завершится последняя задача?"
    )
    params = {"workers": workers, "durations": durations}
    return Instance(prompt, str(max(free_at)), params)


def lost_update(rng: random.Random) -> Instance:
    threads = ["A", "B", "C"][: rng.randint(2, 3)]
    per_thread = 2
    start = rng.randint(0, 20)
    pending = {t: ["read", "write"] * per_thread for t in threads}
    schedule: list[str] = []
    while any(pending.values()):
        t = rng.choice([t for t, steps in pending.items() if steps])
        schedule.append(f"{t}:{pending[t].pop(0)}")

    counter, local = start, {}
    for step in schedule:
        t, op = step.split(":")
        if op == "read":
            local[t] = counter
        else:
            counter = local[t] + 1
    code = f"counter = {start}\n\ndef worker():\n    global counter\n"
    code += f"    for _ in range({per_thread}):\n"
    code += "        tmp = counter        # read\n        counter = tmp + 1    # write\n"
    prompt = (
        f"Потоки {', '.join(threads)} одновременно выполняют worker() без блокировок. Планировщик "
        f"выполнил шаги в таком порядке: {' '.join(schedule)}. Каким станет counter?"
    )
    return Instance(prompt, str(counter), {"start": start, "schedule": schedule}, code=code)


def threads_join(rng: random.Random) -> Instance:
    delays = [rng.randint(1, 25) for _ in range(rng.randint(3, 4))]
    joined_inside = rng.random() < 0.5
    body = (
        "for d in delays:\n    t = threading.Thread(target=time.sleep, args=(d,))\n    t.start()\n"
    )
    if joined_inside:
        body += "    t.join()\n"
        total = sum(delays)
    else:
        body = (
            "threads = [threading.Thread(target=time.sleep, args=(d,)) for d in delays]\n"
            "for t in threads:\n    t.start()\nfor t in threads:\n    t.join()\n"
        )
        total = max(delays)
    code = f"import threading\nimport time\n\ndelays = {delays}\n" + body
    prompt = "Сколько секунд будет работать программа? Накладными расходами пренебречь."
    return Instance(
        prompt, str(total), {"delays": delays, "joined_inside": joined_inside}, code=code
    )


def gather_total(rng: random.Random) -> Instance:
    lines, total = [], 0
    for _ in range(rng.randint(2, 4)):
        if rng.random() < 0.6:
            delays = [rng.randint(1, 20) for _ in range(rng.randint(2, 3))]
            calls = ", ".join(f"asyncio.sleep({d})" for d in delays)
            lines.append(f"    await asyncio.gather({calls})")
            total += max(delays)
        else:
            delay = rng.randint(1, 20)
            lines.append(f"    await asyncio.sleep({delay})")
            total += delay
    code = "import asyncio\n\nasync def main():\n" + "\n".join(lines) + "\n\nasyncio.run(main())\n"
    prompt = "Сколько секунд будет работать программа? Накладными расходами пренебречь."
    return Instance(prompt, str(total), {"lines": lines}, code=code)


def event_loop_order(rng: random.Random) -> Instance:
    names = rng.sample("ABCDEFGH", 3)
    delays = [rng.choice([0, 1, 2, 3]) for _ in names]
    steps = [rng.randint(1, 2) for _ in names]
    # Модель: корутина печатает «имя+шаг» после каждого sleep; sleep(0) отдаёт ход по кругу.
    events: list[tuple[float, int, str]] = []
    seq = 0
    for name, delay, count in zip(names, delays, steps, strict=True):
        for k in range(1, count + 1):
            events.append((delay * k, seq, f"{name}{k}"))
            seq += 1
    # Готовые к одному моменту корутины идут в порядке постановки в очередь на этот момент:
    # при равных моментах — в порядке шага, затем запуска.
    order = sorted(events, key=lambda e: (e[0], int(e[2][1]), names.index(e[2][0])))
    lines = [
        "async def task(name, delay, steps):\n"
        "    for k in range(1, steps + 1):\n"
        "        await asyncio.sleep(delay)\n"
        "        print(f'{name}{k}')\n",
        "async def main():\n    await asyncio.gather(\n"
        + "".join(
            f"        task('{n}', {d}, {s}),\n"
            for n, d, s in zip(names, delays, steps, strict=True)
        )
        + "    )\n",
    ]
    code = "import asyncio\n\n" + "\n".join(lines) + "\nasyncio.run(main())\n"
    prompt = "В каком порядке появятся строки в консоли? Ответ — строки через пробел по порядку."
    params = {"names": names, "delays": delays, "steps": steps}
    return Instance(prompt, " ".join(e[2] for e in order), params, code=code)


def producer_consumer(rng: random.Random) -> Instance:
    produce = [rng.randint(1, 8) for _ in range(rng.randint(5, 7))]
    consume = rng.randint(1, 7)
    made, consumer_free = 0, 0
    for gap in produce:
        made += gap
        consumer_free = max(made, consumer_free) + consume
    prompt = (
        f"Производитель делает элементы с паузами {', '.join(map(str, produce))} с (пауза — "
        "перед каждым элементом) и сразу кладёт их в очередь. Потребитель берёт элементы из "
        f"очереди по одному и обрабатывает каждый {consume} с. Очередь неограниченная. Через "
        "сколько секунд от старта потребитель закончит последний элемент? Ответ — число."
    )
    params = {"produce": produce, "consume": consume}
    return Instance(prompt, str(consumer_free), params)


def amdahl(rng: random.Random) -> Instance:
    parallel = rng.choice(range(50, 100, 5))
    cores = rng.choice([2, 4, 8, 16, 32])
    speedup = 1 / ((1 - parallel / 100) + parallel / 100 / cores)
    prompt = (
        f"{parallel} % времени работы программы распараллеливается идеально, остальное "
        f"выполняется последовательно. Во сколько раз программа ускорится на {cores} ядрах по "
        "закону Амдала? Ответ — число, округлите до сотых."
    )
    return Instance(prompt, f"{rounded(speedup, 2)}", {"parallel": parallel, "cores": cores})


def makespan(rng: random.Random) -> Instance:
    workers = rng.randint(2, 4)
    durations = [rng.randint(1, 15) for _ in range(rng.randint(6, 9))]
    free_at = [0] * workers
    for d in durations:
        start = heapq.heappop(free_at)
        heapq.heappush(free_at, start + d)
    prompt = (
        f"Задачи с длительностями {', '.join(map(str, durations))} (секунды) отправлены по "
        f"порядку в пул из {workers} потоков. Освободившийся поток сразу берёт следующую задачу из "
        "очереди. Через сколько секунд завершится последняя задача?"
    )
    params = {"workers": workers, "durations": durations}
    return Instance(prompt, str(max(free_at)), params)


def as_completed_order(rng: random.Random) -> Instance:
    workers = rng.randint(2, 3)
    names = rng.sample("ABCDEFGH", rng.randint(5, 6))
    durations = [rng.randint(1, 9) for _ in names]
    free_at = [(0, i) for i in range(workers)]
    finished = []
    for i, (name, d) in enumerate(zip(names, durations, strict=True)):
        start, worker = heapq.heappop(free_at)
        heapq.heappush(free_at, (start + d, worker))
        finished.append((start + d, i, name))
    order = "".join(name for _, _, name in sorted(finished))
    code = (
        "from concurrent.futures import ThreadPoolExecutor, as_completed\n\n"
        f"jobs = {dict(zip(names, durations, strict=True))}  # имя: секунд работы\n\n"
        f"with ThreadPoolExecutor(max_workers={workers}) as pool:\n"
        "    futures = {pool.submit(time.sleep, sec): name for name, sec in jobs.items()}\n"
        "    for future in as_completed(futures):\n"
        "        print(futures[future], end='')\n"
    )
    prompt = (
        "Задачи отправлены в пул по порядку словаря. В каком порядке напечатаются имена? При "
        "одновременном завершении первой печатается задача, отправленная раньше. Ответ — "
        "буквы подряд."
    )
    params = {"workers": workers, "names": names, "durations": durations}
    return Instance(prompt, order, params, code=code)


def deadlock_cycle(rng: random.Random) -> Instance:
    procs = rng.sample("PQRSTUVW", 6)
    resources = rng.sample("abcdefgh", 6)
    holds = dict(zip(procs, resources, strict=True))
    cycle = rng.sample(procs, rng.randint(2, 4))
    waits = {p: holds[cycle[(i + 1) % len(cycle)]] for i, p in enumerate(cycle)}
    for p in procs:
        if p not in waits:
            # Вне цикла: ждёт чужую блокировку или ничего — но цикла не замыкает.
            target = rng.choice([q for q in procs if q != p and q in waits] + [""])
            waits[p] = holds[target] if target else ""
    lines = [
        f"{p} держит {holds[p]}" + (f", ждёт {waits[p]}" if waits[p] else ", ничего не ждёт")
        for p in procs
    ]
    prompt = (
        "Каждый процесс держит одну блокировку и, возможно, ждёт другую. Какие процессы "
        "образуют цикл ожидания — взаимную блокировку? Ответ — их имена подряд по алфавиту."
    )
    params = {"holds": holds, "waits": waits}
    return Instance(prompt, "".join(sorted(cycle)), params, code="\n".join(lines))


def semaphore_timeline(rng: random.Random) -> Instance:
    limit = rng.randint(2, 3)
    arrivals = sorted(rng.sample(range(0, 12), rng.randint(5, 6)))
    durations = [rng.randint(2, 7) for _ in arrivals]
    # Моменты освобождения мест, занятых начатыми или уже назначенными корутинами.
    busy: list[int] = []
    starts = []
    for at, d in zip(arrivals, durations, strict=True):
        busy = [t for t in busy if t > at]
        start = at if len(busy) < limit else min(busy)
        if len(busy) >= limit:
            busy.remove(start)
        busy.append(start + d)
        starts.append(start)
    lines = [
        f"{chr(65 + i)}: приходит в {a} с, работает {d} с"
        for i, (a, d) in enumerate(zip(arrivals, durations, strict=True))
    ]
    prompt = (
        f"Корутины ограничены asyncio.Semaphore({limit}); ждущие входят в порядке прихода. В "
        "какие моменты каждая корутина начнёт работу? Ответ — моменты через пробел по порядку "
        "корутин."
    )
    params = {"limit": limit, "arrivals": arrivals, "durations": durations}
    return Instance(prompt, " ".join(map(str, starts)), params, code="\n".join(lines))


def lost_update_wide(rng: random.Random) -> Instance:
    threads = ["A", "B", "C"][: rng.randint(2, 3)]
    per_thread = rng.randint(2, 3)
    start = rng.randint(0, 50)
    step = rng.randint(1, 5)
    pending = {t: ["read", "write"] * per_thread for t in threads}
    schedule: list[str] = []
    while any(pending.values()):
        t = rng.choice([t for t, steps in pending.items() if steps])
        schedule.append(f"{t}:{pending[t].pop(0)}")

    counter, local = start, {}
    for item in schedule:
        t, op = item.split(":")
        if op == "read":
            local[t] = counter
        else:
            counter = local[t] + step
    code = f"counter = {start}\n\ndef worker():\n    global counter\n"
    code += f"    for _ in range({per_thread}):\n"
    code += f"        tmp = counter        # read\n        counter = tmp + {step}    # write\n"
    prompt = (
        f"Потоки {', '.join(threads)} одновременно выполняют worker() без блокировок. Планировщик "
        f"выполнил шаги в таком порядке: {' '.join(schedule)}. Каким станет counter?"
    )
    params = {"start": start, "step": step, "schedule": schedule}
    return Instance(prompt, str(counter), params, code=code)


def cas_retries(rng: random.Random) -> Instance:
    threads = rng.sample("ABC", rng.randint(2, 3))
    start = rng.randint(0, 40)
    # Каждый поток делает read и cas; cas неудачен, если значение сменилось после его read, —
    # тогда поток повторяет read и cas. Порядок шагов задан расписанием.
    schedule: list[str] = []
    seen: dict[str, int] = {}
    done: set[str] = set()
    value, retries = start, 0
    increments = {t: rng.randint(1, 9) for t in threads}
    while len(done) < len(threads) and len(schedule) < 14:
        t = rng.choice([t for t in threads if t not in done])
        if t not in seen:
            seen[t] = value
            schedule.append(f"{t}:read")
        else:
            schedule.append(f"{t}:cas")
            if seen[t] == value:
                value += increments[t]
                done.add(t)
            else:
                retries += 1
            del seen[t]
    lines = [f"{t}: прибавляет {increments[t]}" for t in threads]
    prompt = (
        f"Счётчик равен {start}. Потоки прибавляют к нему свои числа через compare-and-swap: "
        "read запоминает значение, cas записывает запомненное + своё число, только если счётчик "
        "не изменился с этого read, иначе поток повторяет read и cas. Планировщик выполнил шаги: "
        f"{' '.join(schedule)}. Каким стал счётчик и сколько cas оказались неудачными? Ответ — "
        "два числа через пробел."
    )
    params = {"start": start, "increments": increments, "schedule": schedule}
    return Instance(prompt, f"{value} {retries}", params, code="\n".join(lines))
