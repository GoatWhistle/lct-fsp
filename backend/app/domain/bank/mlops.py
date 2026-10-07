"""Внедрение и эксплуатация моделей: разбиения данных, пакетный инференс, DAG пайплайнов,
дрейф данных, реестр моделей, мощности, канареечный выпуск, A/B-тест, расписания cron."""

import math
import random

from app.domain.bank.family import Instance, rounded


def split_sizes(rng: random.Random) -> Instance:
    n = rng.randint(500, 20000)
    test = rng.choice([0.1, 0.15, 0.2, 0.25])
    val = rng.choice([0.1, 0.2, 0.25])
    test_n = math.ceil(n * test)
    rest = n - test_n
    val_n = math.ceil(rest * val)
    prompt = (
        f"Датасет из {n} строк сначала делят train_test_split(test_size={test}), затем обучающую "
        f"часть ещё раз — train_test_split(test_size={val}) на обучение и валидацию. scikit-learn "
        "округляет тестовую долю вверх. Сколько строк окажется в обучении, валидации и тесте? "
        "Ответ — три числа через пробел."
    )
    return Instance(prompt, f"{rest - val_n} {val_n} {test_n}", {"n": n, "test": test, "val": val})


def batch_inference(rng: random.Random) -> Instance:
    samples = rng.randint(1000, 200000)
    batch = rng.choice([32, 64, 128, 256, 512])
    per_batch = rng.choice([20, 35, 50, 80, 120])
    workers = rng.randint(1, 4)
    batches = math.ceil(samples / batch)
    seconds = math.ceil(batches / workers) * per_batch / 1000
    prompt = (
        f"Нужно разметить {samples} объектов, батч — {batch}, один батч считается {per_batch} мс, "
        f"параллельно работают {workers} одинаковых процесса, батчи раздаются поровну. Сколько "
        "батчей получится и сколько секунд займёт разметка? Ответ — два числа через пробел, "
        "секунды округлите до десятых."
    )
    params = {"samples": samples, "batch": batch, "per_batch": per_batch, "workers": workers}
    return Instance(prompt, f"{batches} {rounded(seconds, 1)}", params)


def dag_duration(rng: random.Random) -> Instance:
    names = ["extract", "clean", "features", "train", "evaluate", "report"]
    durations = {n: rng.randint(2, 30) for n in names}
    deps: dict[str, list[str]] = {"extract": []}
    for i, n in enumerate(names[1:], 1):
        deps[n] = sorted(set(rng.sample(names[:i], rng.randint(1, min(2, i)))))
    finish: dict[str, int] = {}
    for n in names:
        finish[n] = max((finish[d] for d in deps[n]), default=0) + durations[n]
    lines = [
        f"{n}: {durations[n]} мин" + (f", после {', '.join(deps[n])}" if deps[n] else "")
        for n in names
    ]
    prompt = (
        "Задачи DAG в Airflow, исполнителей хватает на все готовые задачи сразу. Через сколько "
        "минут закончится весь DAG и когда закончится задача train? Ответ — два числа через пробел."
    )
    answer = f"{max(finish.values())} {finish['train']}"
    return Instance(prompt, answer, {"durations": durations, "deps": deps}, code="\n".join(lines))


def psi_drift(rng: random.Random) -> Instance:
    expected = [rng.randint(5, 40) for _ in range(4)]
    actual = [max(1, e + rng.randint(-12, 12)) for e in expected]
    e_total, a_total = sum(expected), sum(actual)
    psi = 0.0
    for e, a in zip(expected, actual, strict=True):
        pe, pa = e / e_total, a / a_total
        psi += (pa - pe) * math.log(pa / pe)
    verdict = "нет" if psi < 0.1 else "умеренный" if psi < 0.25 else "сильный"
    prompt = (
        f"Распределение признака по четырём корзинам на обучении: {expected} объектов, в "
        f"проде: {actual}. Найдите PSI = Σ (p_прод − p_обуч) · ln(p_прод / p_обуч) по долям "
        "корзин и оцените дрейф по правилу: меньше 0,1 — «нет», меньше 0,25 — «умеренный», "
        "иначе «сильный». Ответ — PSI, округлённый до тысячных, и слово через пробел."
    )
    return Instance(
        prompt, f"{rounded(psi, 3)} {verdict}", {"expected": expected, "actual": actual}
    )


def registry_stages(rng: random.Random) -> Instance:
    versions = {v: "None" for v in range(1, 5)}
    events = []
    for _ in range(rng.randint(5, 7)):
        v = rng.randint(1, 4)
        stage = rng.choice(["Staging", "Production", "Archived"])
        archive = stage == "Production" and rng.random() < 0.6
        events.append(
            f"версия {v} → {stage}" + (" (archive_existing_versions=True)" if archive else "")
        )
        if archive:
            for other, current in versions.items():
                if other != v and current == "Production":
                    versions[other] = "Archived"
        versions[v] = stage
    prompt = (
        "Реестр моделей MLflow: у версий 1–4 сначала стадия None. Переходы ниже выполняются по "
        "порядку; с archive_existing_versions=True остальные версии в Production уходят в "
        "Archived. Какие стадии у версий 1–4 в конце? Ответ — четыре стадии через пробел."
    )
    answer = " ".join(versions[v] for v in range(1, 5))
    return Instance(prompt, answer, {"events": events}, code="\n".join(events))


def replicas_needed(rng: random.Random) -> Instance:
    rps = rng.randrange(50, 3000, 10)
    latency_ms = rng.choice([20, 40, 50, 80, 100, 200])
    concurrency = rng.choice([1, 2, 4, 8])
    headroom = rng.choice([0.5, 0.6, 0.7, 0.8])
    per_replica = concurrency * 1000 / latency_ms
    replicas = math.ceil(rps / (per_replica * headroom))
    prompt = (
        f"Модель отвечает за {latency_ms} мс, одна реплика обрабатывает {concurrency} запроса "
        f"одновременно. Пиковая нагрузка — {rps} RPS, реплики должны быть загружены не больше чем "
        f"на {int(headroom * 100)} %. Сколько запросов в секунду тянет одна реплика и сколько "
        "реплик нужно? Ответ — два числа через пробел."
    )
    params = {
        "rps": rps,
        "latency_ms": latency_ms,
        "concurrency": concurrency,
        "headroom": headroom,
    }
    return Instance(prompt, f"{per_replica:g} {replicas}", params)


def canary_requests(rng: random.Random) -> Instance:
    steps = [rng.choice([1, 5, 10]), rng.choice([20, 25]), rng.choice([50]), 100]
    minutes = rng.choice([10, 15, 30])
    rps = rng.randint(10, 200)
    fail_at = rng.choice([None, 1, 2, 3])
    reached = len(steps)
    total = 0.0
    for i, share in enumerate(steps):
        if fail_at is not None and i == fail_at:
            reached = i
            break
        total += rps * 60 * minutes * share / 100
    prompt = (
        "Канареечный выпуск: доля трафика на новую версию по шагам "
        f"{', '.join(f'{s} %' for s in steps)}, "
        f"каждый шаг длится {minutes} мин, нагрузка ровная — {rps} RPS. "
        + (
            f"Проверка после шага {fail_at} провалилась, выпуск откатили сразу. "
            if fail_at is not None
            else "Все проверки прошли. "
        )
        + "Сколько запросов успела обработать новая версия? Ответ — число."
    )
    _ = reached
    return Instance(
        prompt, f"{total:g}", {"steps": steps, "minutes": minutes, "rps": rps, "fail_at": fail_at}
    )


def ab_test_z(rng: random.Random) -> Instance:
    n_a, n_b = rng.randrange(1000, 20000, 100), rng.randrange(1000, 20000, 100)
    p_a = rng.randint(20, 120) / 1000
    p_b = p_a + rng.randint(-15, 25) / 1000
    conv_a, conv_b = round(n_a * p_a), round(n_b * p_b)
    pa, pb = conv_a / n_a, conv_b / n_b
    pooled = (conv_a + conv_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (pb - pa) / se
    verdict = "да" if abs(z) > 1.96 else "нет"
    prompt = (
        f"A/B-тест модели рекомендаций: в контроле {n_a} пользователей и {conv_a} покупок, в "
        f"тесте {n_b} и {conv_b}. Найдите z-статистику двухвыборочного теста для долей с "
        "объединённой оценкой доли и решите, значима ли разница при α = 0,05 (|z| > 1,96). "
        "Ответ — z, округлённое до сотых, и «да» или «нет» через пробел."
    )
    params = {"n_a": n_a, "n_b": n_b, "conv_a": conv_a, "conv_b": conv_b}
    return Instance(prompt, f"{rounded(z, 2)} {verdict}", params)


def feature_freshness(rng: random.Random) -> Instance:
    ttl = rng.choice([5, 10, 15, 30])
    updates = sorted(rng.sample(range(0, 120, 5), rng.randint(3, 5)))
    reads = sorted(rng.sample(range(1, 150), 5))
    answers = []
    for t in reads:
        last = max((u for u in updates if u <= t), default=None)
        if last is None:
            answers.append("нет")
        elif t - last >= ttl:
            answers.append("устарел")
        else:
            answers.append(str(last))
    prompt = (
        f"Онлайн-хранилище признаков: признак обновляют в минуты {', '.join(map(str, updates))}, "
        f"значение живёт {ttl} мин (в момент обновление + {ttl} оно уже устарело). Модель читает "
        f"признак в минуты {', '.join(map(str, reads))}. Что получит каждое чтение? Ответ — через "
        "пробел: минута обновления, из которого взято значение, «устарел» или «нет» (ещё не было)."
    )
    return Instance(prompt, " ".join(answers), {"ttl": ttl, "updates": updates, "reads": reads})


def degradation_alerts(rng: random.Random) -> Instance:
    threshold = rng.choice([0.80, 0.85, 0.9])
    days = rng.randint(2, 3)
    values = [
        round(threshold + rng.choice([-0.04, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03]), 2)
        for _ in range(14)
    ]
    alerts = []
    streak = 0
    for i, v in enumerate(values, 1):
        streak = streak + 1 if v < threshold else 0
        if streak == days:
            alerts.append(i)
            streak = 0
    prompt = (
        f"Метрика качества модели по дням: {', '.join(map(str, values))}. Алерт на переобучение "
        f"срабатывает, когда метрика ниже {threshold} {days} дня подряд; после алерта счётчик "
        "обнуляется. В какие дни сработают алерты? Ответ — номера дней с 1 через пробел; если ни "
        "одного — 0."
    )
    return Instance(
        prompt,
        " ".join(map(str, alerts)) or "0",
        {"threshold": threshold, "days": days, "values": values},
    )


def _cron_matches(field: str, value: int) -> bool:
    for part in field.split(","):
        if part == "*":
            return True
        if part.startswith("*/"):
            if value % int(part[2:]) == 0:
                return True
        elif "-" in part:
            low, high = map(int, part.split("-"))
            if low <= value <= high:
                return True
        elif int(part) == value:
            return True
    return False


def cron_runs(rng: random.Random) -> Instance:
    minute = rng.choice(["0", "15", "*/15", "*/20", "0,30", "5"])
    hour = rng.choice(["*", "*/2", "*/3", "9-18", "0,12", "6-9,18"])
    runs = [
        (h, m)
        for h in range(24)
        for m in range(60)
        if _cron_matches(minute, m) and _cron_matches(hour, h)
    ]
    start = rng.randint(0, 23 * 60)
    after = [f"{h:02d}:{m:02d}" for h, m in runs if h * 60 + m > start][:2]
    while len(after) < 2:
        after.append("завтра")
    prompt = (
        f"Пайплайн переобучения запускается по cron «{minute} {hour} * * *». Сколько запусков за "
        f"сутки и какие два ближайших запуска после {start // 60:02d}:{start % 60:02d}? Ответ — "
        "число и два времени ЧЧ:ММ через пробел; если в эти сутки запусков больше нет — слово "
        "«завтра» вместо времени."
    )
    return Instance(
        prompt,
        f"{len(runs)} {after[0]} {after[1]}",
        {"minute": minute, "hour": hour, "start": start},
    )


def spot_training_cost(rng: random.Random) -> Instance:
    hours = rng.randint(4, 40)
    price = rng.choice([2.5, 3.2, 4.0, 1.8])
    spot_discount = rng.choice([60, 65, 70])
    interruptions = rng.randint(0, 4)
    checkpoint = rng.choice([0.5, 1, 2])
    # Каждое прерывание теряет в среднем половину интервала между чекпоинтами.
    lost = interruptions * checkpoint / 2
    spot_cost = (hours + lost) * price * (100 - spot_discount) / 100
    on_demand = hours * price
    prompt = (
        f"Обучение занимает {hours} ч на GPU за ${price}/ч. Спотовый инстанс дешевле на "
        f"{spot_discount} %, но его прервут {interruptions} раз; чекпоинт пишется каждые "
        f"{checkpoint} ч, и каждое прерывание в среднем теряет половину интервала. Сколько "
        "стоит обучение на обычном и на спотовом инстансе? Ответ — два числа в долларах через "
        "пробел, округлите до сотых."
    )
    params = {
        "hours": hours,
        "price": price,
        "discount": spot_discount,
        "interruptions": interruptions,
        "checkpoint": checkpoint,
    }
    return Instance(prompt, f"{rounded(on_demand, 2)} {rounded(spot_cost, 2)}", params)
