"""Алгоритмы и структуры данных: циклы, бинарный поиск, обход графа, кратчайший путь."""

import heapq
import random
import string
from collections import deque

from app.assessment.bank.family import Instance
from app.assessment.bank.python_code import run_python

LETTERS = string.ascii_uppercase


def range_count(rng: random.Random) -> Instance:
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


def binary_search_steps(rng: random.Random) -> Instance:
    items = sorted(rng.sample(range(1, 100), rng.randint(11, 18)))
    target = (
        rng.choice(items)
        if rng.random() < 0.7
        else rng.choice([v for v in range(1, 100) if v not in items])
    )
    code = BINARY_SEARCH + f"\nitems = {items}\nprint(search(items, {target}))\n"
    prompt = "Что выведет программа? Ответ — целое число."
    return Instance(prompt, run_python(code), {"items": items, "target": target}, code=code)


def _connected_graph(rng: random.Random, n: int, extra: int) -> list[tuple[int, int]]:
    edges = {(rng.randrange(v), v) for v in range(1, n)}
    while len(edges) < n - 1 + extra:
        a, b = sorted(rng.sample(range(n), 2))
        edges.add((a, b))
    return sorted(edges)


def bfs_order(rng: random.Random) -> Instance:
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


def shortest_path(rng: random.Random) -> Instance:
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
