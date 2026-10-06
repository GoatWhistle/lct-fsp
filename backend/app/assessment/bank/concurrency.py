"""Конкурентность и асинхронность: пул потоков, asyncio, гонки."""

import heapq
import random

from app.assessment.bank.family import Instance


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
