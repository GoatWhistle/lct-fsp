"""Контейнеры и оркестрация: публикация портов, кэш сборки образа, единицы памяти, селекторы
сервисов, HPA, перезапуски, rolling update, планировщик, пробы, квота CPU, PodDisruptionBudget."""

import math
import random

from app.domain.bank.family import Instance, Kind, kind
from app.domain.bank.runner import CodeRunner

_IMAGES = [("web", "nginx", 80), ("api", "api", 8000), ("db", "postgres", 5432)]
_IMAGES += [("cache", "redis", 6379), ("admin", "admin", 3000)]


@kind(Kind.TRACE)
def port_mapping(rng: random.Random, runner: CodeRunner) -> Instance:
    containers = []
    for name, image, port in rng.sample(_IMAGES, 4):
        host = rng.choice([8080, 8081, 9000, 9090, 5433, 6380])
        mode = rng.choice(["publish", "publish", "localhost", "host", "none"])
        containers.append((name, image, port, host, mode))
    # Порты хоста у разных контейнеров разные: иначе второй docker run не запустится.
    used: set[int] = set()
    fixed = []
    for name, image, port, host, mode in containers:
        while host in used:
            host += 1
        if mode in ("publish", "localhost"):
            used.add(host)
        fixed.append((name, image, port, host, mode))
    lines = []
    for name, image, port, host, mode in fixed:
        flag = {
            "publish": f"-p {host}:{port} ",
            "localhost": f"-p 127.0.0.1:{host}:{port} ",
            "host": "--network host ",
            "none": "",
        }[mode]
        lines.append(f"docker run -d --name {name} {flag}{image}  # слушает {port} в контейнере")

    def answer(local: bool, port: int) -> str:
        for name, _, inner, host, mode in fixed:
            if mode == "publish" and port == host:
                return name
            if mode == "localhost" and port == host and local:
                return name
            if mode == "host" and port == inner:
                return name
        return "отказ"

    ports = sorted({h for *_, h, m in fixed if m != "none"} | {p for _, _, p, _, _ in fixed})
    requests = [(rng.random() < 0.5, rng.choice(ports)) for _ in range(5)]
    rows = [
        f"{i}. {'с самого хоста на localhost' if local else 'с другой машины на IP хоста'}:{port}"
        for i, (local, port) in enumerate(requests, 1)
    ]
    prompt = (
        "На хосте запущены контейнеры командами ниже, других процессов на портах нет. Кто "
        "ответит на каждый запрос? Ответ — имя контейнера или «отказ» для каждого запроса через "
        "пробел."
    )
    return Instance(
        prompt,
        " ".join(answer(local, port) for local, port in requests),
        {"containers": fixed, "requests": requests},
        code="\n".join(lines) + "\n\n" + "\n".join(rows),
    )


@kind(Kind.TRACE)
def service_selector(rng: random.Random, runner: CodeRunner) -> Instance:
    app = rng.choice(["shop", "billing"])
    tier = rng.choice(["api", "web"])
    selector = {"app": app, "tier": tier}
    if rng.random() < 0.5:
        selector["track"] = "stable"
    pods = []
    for i in range(1, 8):
        # Половина подов — под селектор, у остальных одна метка расходится.
        labels = dict(selector)
        if rng.random() < 0.5:
            key = rng.choice(list(selector))
            labels[key] = {
                "app": "billing" if app == "shop" else "shop",
                "tier": "web" if tier == "api" else "api",
                "track": "canary",
            }[key]
        if "track" not in selector and rng.random() < 0.5:
            labels["track"] = rng.choice(["stable", "canary"])
        if rng.random() < 0.3:
            labels["team"] = "core"
        ready = rng.random() < 0.8
        pods.append((f"pod-{i}", labels, ready))
    endpoints = [
        name
        for name, labels, ready in pods
        if ready and all(labels.get(k) == v for k, v in selector.items())
    ]
    lines = [
        f"{name}: {', '.join(f'{k}={v}' for k, v in labels.items())}; "
        f"{'Ready' if ready else 'не Ready'}"
        for name, labels, ready in pods
    ]
    prompt = (
        f"У Service selector {{{', '.join(f'{k}: {v}' for k, v in selector.items())}}}. Какие "
        "поды попадут в его endpoints? Ответ — имена через пробел по порядку; если ни один — 0."
    )
    return Instance(
        prompt,
        " ".join(endpoints) or "0",
        {"selector": selector, "pods": pods},
        code="\n".join(lines),
    )


_UNITS = {"Mi": 2**20, "Gi": 2**30, "M": 10**6, "G": 10**9}


@kind(Kind.COMPUTE)
def memory_units(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = []
    for name in ("api", "worker", "web", "cron", "proxy"):
        number, unit = rng.choice([(512, "Mi"), (500, "M"), (1, "Gi"), (1, "G"), (256, "Mi")])
        limit = number * _UNITS[unit]
        # Потребление — рядом с лимитом, в другой единице: вся задача в переводе единиц.
        if unit in ("Mi", "Gi"):
            usage_unit, scale = "МБ", 10**6
        else:
            usage_unit, scale = "МиБ", 2**20
        usage = round(limit / scale * rng.choice([0.93, 0.97, 1.02, 1.05, 1.08]))
        rows.append((name, f"{number}{unit}", usage, usage_unit, usage * scale > limit))
    lines = [
        f"{name}: limits.memory: {limit}, потребление {usage} {unit} "
        f"({'1 МБ = 10^6 байт' if unit == 'МБ' else '1 МиБ = 2^20 байт'})"
        for name, limit, usage, unit, _ in rows
    ]
    prompt = (
        "Контейнер убивают по OOM, если его потребление памяти превышает limits.memory. Каких "
        "из них убьют? Ответ — «да» или «нет» для каждого через пробел по порядку."
    )
    return Instance(
        prompt,
        " ".join("да" if killed else "нет" for *_, killed in rows),
        {"rows": [list(r[:4]) for r in rows]},
        code="\n".join(lines),
    )


@kind(Kind.TRACE)
def build_cache(rng: random.Random, runner: CodeRunner) -> Instance:
    steps = ["FROM python:3.12-slim", "WORKDIR /app"]
    for optional in ("ARG APP_VERSION=dev", "ENV PYTHONUNBUFFERED=1", "LABEL team=platform"):
        if rng.random() < 0.5:
            steps.append(optional)
    if rng.random() < 0.5:
        steps.append("RUN apt-get update && apt-get install -y curl")
    if rng.random() < 0.5:
        steps += ["COPY requirements.txt .", "RUN pip install -r requirements.txt", "COPY . ."]
    else:
        steps += ["COPY . .", "RUN pip install -r requirements.txt"]
    pool = [
        "RUN python -m compileall .",
        "RUN pytest -q",
        "RUN python manage.py collectstatic",
        "RUN useradd app",
    ]
    steps += rng.sample(pool, rng.randint(1, 3))
    if rng.random() < 0.5:
        steps.insert(-1, "EXPOSE 8000")
    runs = [i for i, step in enumerate(steps, 1) if step.startswith("RUN")]
    copy_all = steps.index("COPY . .") + 1
    changes = {
        "в FROM поменяли тег на python:3.13-slim": 2,
        "WORKDIR поменяли на /srv": 2,
        "поменялся requirements.txt": next(
            i for i, step in enumerate(steps, 1) if step.startswith("COPY")
        ),
        "поменялся README.md, он указан в .dockerignore": 0,
        "поменялся main.py": copy_all,
        f"в последней инструкции поменяли текст команды: {steps[-1]} --verbose": len(steps),
    }
    if steps[-1].startswith("EXPOSE") or not steps[-1].startswith("RUN"):
        del changes[next(k for k in changes if k.startswith("в последней"))]
    what, first = rng.choice(list(changes.items()))
    rerun = [i for i in runs if first and i >= first]
    code = "\n".join(f"{i:>2}  {step}" for i, step in enumerate(steps, 1))
    prompt = (
        f"Образ уже собирали, кэш сборки на месте. Затем {what}, и образ собирают заново. "
        "Какие инструкции RUN выполнятся снова, а не возьмутся из кэша? Ответ — их номера через "
        "пробел; если ни одна — 0."
    )
    return Instance(
        prompt,
        " ".join(map(str, rerun)) or "0",
        {"steps": steps, "change": what},
        code=code,
    )


@kind(Kind.COMPUTE)
def hpa_replicas(rng: random.Random, runner: CodeRunner) -> Instance:
    low, high = rng.randint(1, 3), rng.randint(8, 15)
    target = rng.choice([50, 60, 70, 80])
    rows: list[tuple[int, int, int]] = []
    while len(rows) < 3:
        current = rng.randint(low, high)
        usage = rng.choice(
            [
                target + rng.randint(-4, 4),
                rng.randint(10, 100),
                rng.randint(target + 20, 200),
                rng.randint(5, target - 20),
            ]
        )
        ratio = usage / target
        if abs(abs(ratio - 1) - 0.1) < 1e-6:
            # Ровно на границе допуска ответ решает округление float — такие ситуации не даём.
            continue
        # Допуск 10 %: при отношении в [0,9; 1,1] HPA ничего не меняет.
        desired = current if abs(ratio - 1) <= 0.1 else math.ceil(current * ratio)
        rows.append((current, usage, min(max(desired, low), high)))
    lines = [
        f"{i}. сейчас реплик {c}, средняя загрузка CPU {u} % от requests"
        for i, (c, u, _) in enumerate(rows, 1)
    ]
    prompt = (
        f"HorizontalPodAutoscaler: minReplicas {low}, maxReplicas {high}, цель — "
        f"averageUtilization {target} % по CPU, допуск по умолчанию 10 %, окна стабилизации нет. "
        "Сколько реплик он выставит в каждой ситуации? Ответ — три числа через пробел."
    )
    return Instance(
        prompt,
        " ".join(str(r[2]) for r in rows),
        {"min": low, "max": high, "target": target, "rows": rows},
        code="\n".join(lines),
    )


@kind(Kind.COMPUTE)
def crashloop_backoff(rng: random.Random, runner: CodeRunner) -> Instance:
    run = rng.randint(1, 20)
    first, second = sorted(rng.sample(range(2, 10), 2))

    def restart_at(k: int) -> int:
        """Момент k-го перезапуска от первого старта: каждый запуск живёт `run` с, пауза перед
        перезапуском — 10, 20, 40, … с, но не больше 300."""
        t = 0
        for n in range(k):
            t += run + min(10 * 2**n, 300)
        return t

    prompt = (
        f"Контейнер с restartPolicy: Always после каждого старта работает {run} с и падает. "
        "kubelet перед перезапуском ждёт 10 с, затем вдвое дольше после каждого следующего "
        "падения, но не больше 5 минут; запуск мгновенный. Через сколько секунд от первого "
        f"старта произойдут перезапуски № {first} и № {second}? Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{restart_at(first)} {restart_at(second)}",
        {"run": run, "first": first, "second": second},
    )


def _percent_or_count(rng: random.Random) -> tuple[str, float | int]:
    if rng.random() < 0.5:
        value = rng.choice([10, 20, 25, 30, 50])
        return f"{value}%", value / 100
    count = rng.randint(0, 3)
    return str(count), count


@kind(Kind.COMPUTE)
def rolling_update(rng: random.Random, runner: CodeRunner) -> Instance:
    while True:
        replicas = rng.randint(3, 20)
        surge_text, surge = _percent_or_count(rng)
        unavailable_text, unavailable = _percent_or_count(rng)
        # Проценты: maxSurge округляется вверх, maxUnavailable — вниз.
        surge_n = math.ceil(replicas * surge - 1e-9) if isinstance(surge, float) else surge
        unavailable_n = (
            math.floor(replicas * unavailable + 1e-9)
            if isinstance(unavailable, float)
            else unavailable
        )
        if surge_n or unavailable_n:
            break
    prompt = (
        f"Deployment на {replicas} реплик обновляется стратегией RollingUpdate с maxSurge: "
        f"{surge_text} и maxUnavailable: {unavailable_text}. Сколько подов может существовать "
        "одновременно и сколько готовых подов гарантированно останется во время обновления? "
        "Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{replicas + surge_n} {replicas - unavailable_n}",
        {"replicas": replicas, "surge": surge_text, "unavailable": unavailable_text},
    )


def _cpu(millicores: int) -> str:
    return f"{millicores}m" if millicores % 1000 else str(millicores // 1000)


@kind(Kind.COMPUTE)
def pod_scheduling(rng: random.Random, runner: CodeRunner) -> Instance:
    capacity = {
        name: (rng.choice([2000, 4000]), rng.choice([4096, 8192])) for name in ("node-a", "node-b")
    }
    free = {name: list(values) for name, values in capacity.items()}
    pods = []
    for i in range(1, 6):
        cpu = rng.choice([250, 500, 1000, 1500, 2000])
        mem = rng.choice([512, 1024, 2048, 3072])
        pods.append((f"pod-{i}", cpu, mem))
    placed = []
    for _, cpu, mem in pods:
        fit = [n for n, (c, m) in free.items() if c >= cpu and m >= mem]
        if not fit:
            placed.append("Pending")
            continue
        # Больше свободного CPU — раньше; при равенстве — первый по списку.
        best = max(fit, key=lambda n: (free[n][0], -list(free).index(n)))
        free[best][0] -= cpu
        free[best][1] -= mem
        placed.append(best)
    lines = [f"{name}: requests cpu {_cpu(cpu)}, memory {mem}Mi" for name, cpu, mem in pods]
    nodes = "; ".join(
        f"{n}: allocatable cpu {_cpu(c)}, memory {m}Mi" for n, (c, m) in capacity.items()
    )
    prompt = (
        f"Узлы пустые: {nodes}. Поды создаются по одному в порядке списка. Планировщик ставит "
        "под на узел, где после размещения останется больше свободного CPU по requests, при "
        "равенстве — на первый по списку; если не помещается никуда — под остаётся Pending. Куда "
        "попадёт каждый под? Ответ — имя узла или Pending для каждого пода через пробел."
    )
    return Instance(
        prompt,
        " ".join(placed),
        {"capacity": capacity, "pods": pods},
        code="\n".join(lines),
    )


@kind(Kind.COMPUTE)
def probe_restart(rng: random.Random, runner: CodeRunner) -> Instance:
    delay, period = rng.choice([5, 10, 15, 20]), rng.choice([5, 10, 15])
    threshold = rng.randint(2, 5)
    r_period, r_threshold = rng.choice([2, 3, 5]), rng.randint(1, 3)
    hang = rng.randint(delay + 1, delay + 120)

    def detected(start: int, every: int, failures: int) -> int:
        """Момент последней из `failures` подряд неудачных проверок; проверки в start + k·every,
        неудачна каждая не раньше сбоя."""
        k = max(0, math.ceil((hang - start) / every))
        return start + (k + failures - 1) * every

    removed = detected(delay, r_period, r_threshold)
    restarted = detected(delay, period, threshold)
    prompt = (
        f"У пода readinessProbe с initialDelaySeconds {delay}, periodSeconds {r_period}, "
        f"failureThreshold {r_threshold} и livenessProbe с initialDelaySeconds {delay}, "
        f"periodSeconds {period}, failureThreshold {threshold}. Проверки идут с момента старта "
        f"контейнера: в initialDelaySeconds и дальше через каждые periodSeconds. Через {hang} с "
        "после старта приложение стало сразу отвечать на проверки ошибкой 500, и каждая проверка "
        "с этого момента неудачна. Через "
        "сколько секунд после старта под уберут из endpoints сервиса и когда контейнер "
        "перезапустят? Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{removed} {restarted}",
        {
            "delay": delay,
            "period": period,
            "threshold": threshold,
            "r_period": r_period,
            "r_threshold": r_threshold,
            "hang": hang,
        },
    )


@kind(Kind.COMPUTE)
def cpu_throttling(rng: random.Random, runner: CodeRunner) -> Instance:
    limit = rng.choice([250, 500, 1000, 1500, 2000])
    threads = rng.choice([1, 1, 2, 4])
    work = rng.randrange(30, 400, 10)
    # Период CFS 100 мс, квота — limit × 100 мс CPU на период. Потоки идут параллельно и делят
    # квоту поровну: за период каждый получает share мс, потом все ждут конца периода.
    share = min(100.0, limit / 10 / threads)
    if work <= share:
        done = float(work)
    else:
        periods = math.ceil(work / share - 1e-9) - 1
        done = periods * 100 + work - periods * share
    prompt = (
        f"У контейнера limits.cpu: {_cpu(limit)}, период CFS — 100 мс: за каждые 100 мс "
        f"контейнер получает не больше {_cpu(limit)} × 100 мс процессорного времени, потом ждёт "
        f"следующего периода. Запрос обрабатывают {threads} потоков параллельно, каждому нужно "
        f"{work} мс CPU, ядер на узле больше, чем потоков; запрос пришёл в начале периода. Через "
        "сколько миллисекунд он будет обработан? Ответ — число, при необходимости округлите до "
        "десятых."
    )
    return Instance(prompt, _decimal(done), {"limit": limit, "threads": threads, "work": work})


def _decimal(value: float) -> str:
    rounded = round(value, 1)
    return str(int(rounded)) if rounded.is_integer() else str(rounded)


@kind(Kind.COMPUTE)
def pdb_disruptions(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = []
    for _ in range(3):
        replicas = rng.randint(3, 12)
        healthy = rng.randint(max(1, replicas - 3), replicas)
        kind = rng.choice(["minAvailable", "maxUnavailable"])
        if rng.random() < 0.5:
            percent = rng.choice([25, 50, 75, 80, 90])
            text = f"{percent}%"
            # В PDB проценты округляются вверх — и для minAvailable, и для maxUnavailable.
            value = math.ceil(replicas * percent / 100 - 1e-9)
        else:
            value = rng.randint(1, replicas - 1)
            text = str(value)
        if kind == "minAvailable":
            allowed = max(0, healthy - value)
        else:
            allowed = max(0, value - (replicas - healthy))
        rows.append((replicas, healthy, kind, text, allowed))
    lines = [
        f"{i}. реплик {r}, сейчас здоровых {h}, PDB {k}: {t}"
        for i, (r, h, k, t, _) in enumerate(rows, 1)
    ]
    prompt = (
        "Сколько подов можно добровольно выселить прямо сейчас (kubectl drain) в каждой "
        "ситуации, не нарушив PodDisruptionBudget? Ответ — три числа через пробел."
    )
    return Instance(
        prompt,
        " ".join(str(r[4]) for r in rows),
        {"rows": [list(r[:4]) for r in rows]},
        code="\n".join(lines),
    )
