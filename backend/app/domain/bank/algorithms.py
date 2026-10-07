"""Алгоритмы и структуры данных: циклы, бинарный поиск, обход графа, кратчайший путь."""

import heapq
import random
import string
from collections import deque

from app.domain.bank.family import Instance
from app.domain.bank.python_code import PROMPT, run_python
from app.domain.bank.runner import CodeRunner

LETTERS = string.ascii_uppercase


def range_count(rng: random.Random, runner: CodeRunner) -> Instance:
    step = rng.randint(2, 7)
    start, stop = rng.randint(-10, 20), rng.randint(30, 90)
    if rng.random() < 0.5:
        start, stop, step = stop, start, -step
    code = f"for i in range({start}, {stop}, {step}):\n    work(i)\n"
    prompt = "Сколько раз будет вызвана функция work? Ответ — целое число."
    answer = str(len(range(start, stop, step)))
    return Instance(prompt, answer, {"start": start, "stop": stop, "step": step}, code=code)


BINARY_SEARCH = """\
def search(items, target):
    lo, hi = 0, len(items) - 1
    steps = 0
    while lo <= hi:
        steps += 1
        mid = (lo + hi) // 2
        if items[mid] == target:
            return steps
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return steps
"""


def binary_search_steps(rng: random.Random, runner: CodeRunner) -> Instance:
    items = sorted(rng.sample(range(1, 100), rng.randint(11, 18)))
    target = (
        rng.choice(items)
        if rng.random() < 0.7
        else rng.choice([v for v in range(1, 100) if v not in items])
    )
    code = BINARY_SEARCH + f"\nitems = {items}\nprint(search(items, {target}))\n"
    prompt = "Что выведет программа? Ответ — целое число."
    return Instance(prompt, run_python(runner, code), {"items": items, "target": target}, code=code)


def _connected_graph(rng: random.Random, n: int, extra: int) -> list[tuple[int, int]]:
    edges = {(rng.randrange(v), v) for v in range(1, n)}
    while len(edges) < n - 1 + extra:
        a, b = sorted(rng.sample(range(n), 2))
        edges.add((a, b))
    return sorted(edges)


def bfs_order(rng: random.Random, runner: CodeRunner) -> Instance:
    n = rng.randint(6, 7)
    adjacency: dict[int, list[int]] = {v: [] for v in range(n)}
    for a, b in _connected_graph(rng, n, extra=rng.randint(1, 3)):
        adjacency[a].append(b)
        adjacency[b].append(a)
    for neighbours in adjacency.values():
        rng.shuffle(neighbours)

    seen, order, queue = {0}, [], deque([0])
    while queue:
        v = queue.popleft()
        order.append(LETTERS[v])
        for u in adjacency[v]:
            if u not in seen:
                seen.add(u)
                queue.append(u)

    code = "\n".join(
        f"{LETTERS[v]}: {', '.join(LETTERS[u] for u in adjacency[v])}" for v in range(n)
    )
    prompt = (
        "Неориентированный граф задан списками смежности. Обход в ширину начинается с A, соседи "
        "перебираются в порядке списка. В каком порядке будут посещены вершины? Ответ — буквы "
        "подряд, например ABCD."
    )
    params = {"adjacency": {LETTERS[v]: [LETTERS[u] for u in us] for v, us in adjacency.items()}}
    return Instance(prompt, "".join(order), params, code=code)


def shortest_path(rng: random.Random, runner: CodeRunner) -> Instance:
    n = 6
    # Прямое ребро A — F всегда есть и тяжёлое: короткий путь приходится искать в обход.
    edges = [
        (a, b, rng.randint(12, 20) if (a, b) == (0, n - 1) else rng.randint(1, 9))
        for a, b in _connected_graph(rng, n, extra=4)
    ]
    if not any((a, b) == (0, n - 1) for a, b, _ in edges):
        edges.append((0, n - 1, rng.randint(12, 20)))

    graph: dict[int, list[tuple[int, int]]] = {v: [] for v in range(n)}
    for a, b, w in edges:
        graph[a].append((b, w))
        graph[b].append((a, w))
    dist = {0: 0}
    heap = [(0, 0)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for u, w in graph[v]:
            if d + w < dist.get(u, d + w + 1):
                dist[u] = d + w
                heapq.heappush(heap, (d + w, u))

    code = "\n".join(f"{LETTERS[a]} — {LETTERS[b]}: {w}" for a, b, w in edges)
    prompt = (
        f"Неориентированный граф, у рёбер — веса. Какова длина кратчайшего пути из A в "
        f"{LETTERS[n - 1]}? Ответ — целое число."
    )
    params = {"edges": [[LETTERS[a], LETTERS[b], w] for a, b, w in edges]}
    return Instance(prompt, str(dist[n - 1]), params, code=code)


def nested_loops(rng: random.Random, runner: CodeRunner) -> Instance:
    n, m, shift = rng.randint(4, 12), rng.randint(5, 15), rng.randint(0, 3)
    code = (
        "count = 0\n"
        f"for i in range({n}):\n"
        f"    for j in range(i + {shift}, {m}):\n"
        "        count += 1\n"
        "print(count)\n"
    )
    params = {"n": n, "m": m, "shift": shift}
    return Instance(PROMPT, run_python(runner, code), params, code=code)


def binary_search_probes(rng: random.Random, runner: CodeRunner) -> Instance:
    items = sorted(rng.sample(range(1, 100), rng.randint(11, 18)))
    target = (
        rng.choice(items)
        if rng.random() < 0.6
        else rng.choice([v for v in range(1, 100) if v not in items])
    )
    code = BINARY_SEARCH.replace(
        "        mid = (lo + hi) // 2\n",
        "        mid = (lo + hi) // 2\n        print(items[mid])\n",
    ) + (f"\nitems = {items}\nsearch(items, {target})\n")
    prompt = (
        "Функция печатает каждый элемент, с которым сравнивает искомое значение. Что она "
        "напечатает? Ответ — числа через пробел по порядку."
    )
    answer = " ".join(run_python(runner, code).split())
    return Instance(prompt, answer, {"items": items, "target": target}, code=code)


def stack_ops(rng: random.Random, runner: CodeRunner) -> Instance:
    ops: list[str] = []
    stack: list[int] = []
    popped: list[int] = []
    pushed = 0
    while len(ops) < 12 or not popped:
        if stack and (pushed >= 7 or rng.random() < 0.45):
            ops.append("pop")
            popped.append(stack.pop())
        else:
            value = rng.randint(1, 99)
            ops.append(f"push {value}")
            stack.append(value)
            pushed += 1
    prompt = (
        "Над пустым стеком выполнили операции по порядку. Какие значения вернули операции pop? "
        "Ответ — числа через пробел по порядку."
    )
    return Instance(prompt, " ".join(map(str, popped)), {"ops": ops}, code="\n".join(ops))


PAIRS = """\
def count_pairs(nums, limit):
    nums = sorted(nums)
    lo, hi, count = 0, len(nums) - 1, 0
    while lo < hi:
        if nums[lo] + nums[hi] <= limit:
            count += hi - lo
            lo += 1
        else:
            hi -= 1
    return count
"""


def pairs_count(rng: random.Random, runner: CodeRunner) -> Instance:
    nums = [rng.randint(1, 50) for _ in range(rng.randint(8, 12))]
    limit = rng.randint(30, 70)
    code = PAIRS + f"\nprint(count_pairs({nums}, {limit}))\n"
    prompt = "Что выведет программа? Ответ — целое число."
    return Instance(prompt, run_python(runner, code), {"nums": nums, "limit": limit}, code=code)


def log_loop(rng: random.Random, runner: CodeRunner) -> Instance:
    n, k = rng.randint(20, 300), rng.choice([2, 3])
    code = (
        "count = 0\n"
        f"for i in range({n}):\n"
        "    j = 1\n"
        f"    while j < i:\n"
        f"        j *= {k}\n"
        "        count += 1\n"
        "print(count)\n"
    )
    prompt = "Что выведет программа? Ответ — целое число."
    return Instance(prompt, run_python(runner, code), {"n": n, "k": k}, code=code)


def _adjacency(rng: random.Random, n: int, extra: int) -> dict[int, list[int]]:
    adjacency: dict[int, list[int]] = {v: [] for v in range(n)}
    for a, b in _connected_graph(rng, n, extra):
        adjacency[a].append(b)
        adjacency[b].append(a)
    for neighbours in adjacency.values():
        rng.shuffle(neighbours)
    return adjacency


def _render(adjacency: dict[int, list[int]]) -> str:
    return "\n".join(
        f"{LETTERS[v]}: {', '.join(LETTERS[u] for u in us)}" for v, us in adjacency.items()
    )


def dfs_order(rng: random.Random, runner: CodeRunner) -> Instance:
    adjacency = _adjacency(rng, rng.randint(6, 7), extra=rng.randint(1, 3))
    order: list[str] = []
    seen: set[int] = set()

    def visit(v: int) -> None:
        seen.add(v)
        order.append(LETTERS[v])
        for u in adjacency[v]:
            if u not in seen:
                visit(u)

    visit(0)
    prompt = (
        "Неориентированный граф задан списками смежности. Рекурсивный обход в глубину "
        "начинается с A, соседи перебираются в порядке списка. В каком порядке будут посещены "
        "вершины? Ответ — буквы подряд, например ABCD."
    )
    params = {"adjacency": {LETTERS[v]: [LETTERS[u] for u in us] for v, us in adjacency.items()}}
    return Instance(prompt, "".join(order), params, code=_render(adjacency))


def topological_order(rng: random.Random, runner: CodeRunner) -> Instance:
    n = rng.randint(6, 7)
    order = rng.sample(range(n), n)
    edges = sorted(
        {
            (order[i], order[j])
            for i, j in (sorted(rng.sample(range(n), 2)) for _ in range(rng.randint(6, 9)))
        }
    )
    indegree = {v: 0 for v in range(n)}
    for _, b in edges:
        indegree[b] += 1
    ready = [v for v in range(n) if indegree[v] == 0]
    heapq.heapify(ready)
    result: list[str] = []
    while ready:
        v = heapq.heappop(ready)
        result.append(LETTERS[v])
        for a, b in edges:
            if a == v:
                indegree[b] -= 1
                if indegree[b] == 0:
                    heapq.heappush(ready, b)
    prompt = (
        f"Задачи {', '.join(LETTERS[:n])} и зависимости между ними: «X → Y» значит, что X "
        "выполняется раньше Y. Алгоритм Кана каждый раз берёт из готовых к выполнению задач "
        "первую по алфавиту. В каком порядке он выполнит задачи? Ответ — буквы подряд."
    )
    code = "\n".join(f"{LETTERS[a]} → {LETTERS[b]}" for a, b in edges)
    params = {"edges": [[LETTERS[a], LETTERS[b]] for a, b in edges], "n": n}
    return Instance(prompt, "".join(result), params, code=code)


def linear_probing(rng: random.Random, runner: CodeRunner) -> Instance:
    size = rng.choice([7, 11, 13])
    keys = rng.sample(range(10, 100), rng.randint(5, 7))
    table: list[int | None] = [None] * size
    for key in keys:
        slot = key % size
        while table[slot] is not None:
            slot = (slot + 1) % size
        table[slot] = key
    prompt = (
        f"Хэш-таблица на {size} ячеек (номера 0–{size - 1}) с открытой адресацией: ключ k "
        f"кладётся в ячейку k mod {size}, а если она занята — в следующую свободную по кругу. "
        f"Ключи вставляют по порядку: {', '.join(map(str, keys))}. В какие ячейки попадут "
        "ключи? Ответ — номера ячеек через пробел в порядке вставки ключей."
    )
    slots = [table.index(key) for key in keys]
    return Instance(prompt, " ".join(map(str, slots)), {"size": size, "keys": keys})


def knapsack(rng: random.Random, runner: CodeRunner) -> Instance:
    items = [(rng.randint(2, 9), rng.randint(5, 40)) for _ in range(5)]
    capacity = rng.randint(10, 20)
    best = [0] * (capacity + 1)
    for weight, value in items:
        for c in range(capacity, weight - 1, -1):
            best[c] = max(best[c], best[c - weight] + value)
    code = "\n".join(f"{LETTERS[i]}: вес {w}, ценность {v}" for i, (w, v) in enumerate(items))
    prompt = (
        f"Рюкзак вмещает вес не больше {capacity}, каждый предмет можно взять не больше одного "
        "раза. Какая наибольшая суммарная ценность достижима? Ответ — целое число."
    )
    return Instance(prompt, str(best[capacity]), {"items": items, "capacity": capacity}, code=code)


def shortest_distances(rng: random.Random, runner: CodeRunner) -> Instance:
    n = 6
    edges = [(a, b, rng.randint(1, 12)) for a, b in _connected_graph(rng, n, extra=4)]
    graph: dict[int, list[tuple[int, int]]] = {v: [] for v in range(n)}
    for a, b, w in edges:
        graph[a].append((b, w))
        graph[b].append((a, w))
    dist = {0: 0}
    heap = [(0, 0)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for u, w in graph[v]:
            if d + w < dist.get(u, d + w + 1):
                dist[u] = d + w
                heapq.heappush(heap, (d + w, u))
    code = "\n".join(f"{LETTERS[a]} — {LETTERS[b]}: {w}" for a, b, w in edges)
    prompt = (
        "Неориентированный граф, у рёбер — веса. Каковы длины кратчайших путей из A в вершины "
        "B, C, D, E и F? Ответ — пять чисел через пробел в этом порядке."
    )
    params = {"edges": [[LETTERS[a], LETTERS[b], w] for a, b, w in edges]}
    return Instance(prompt, " ".join(str(dist[v]) for v in range(1, n)), params, code=code)
