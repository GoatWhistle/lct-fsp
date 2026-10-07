"""HTTP и API: коды ответов, идемпотентность, пагинация, кэширование."""

import random

from app.domain.bank.family import Instance

ENTITIES = ["заказ", "счёт", "отчёт", "профиль", "товар", "платёж"]

# (ситуация с подстановкой {entity} и {id}, код ответа)
STATUS_CASES = [
    ("{entity} с id={id} запрошен, но такого нет", 404),
    ("запрос к закрытому ресурсу пришёл без токена входа", 401),
    ("пользователь вошёл, но его роли {entity} с id={id} недоступен", 403),
    ("{entity} успешно создан методом POST", 201),
    ("{entity} с id={id} удалён, тела ответа нет", 204),
    ("клиент превысил лимит запросов в минуту", 429),
    ("метод DELETE для этого ресурса не поддерживается", 405),
    ("создание пользователя с уже занятым email", 409),
    ("ресурс навсегда переехал на новый адрес", 301),
    ("{entity} с id={id} не менялся с прошлого запроса с If-None-Match", 304),
    ("шлюз не дождался ответа от сервиса за ним", 504),
]


def status_code(rng: random.Random) -> Instance:
    case, code = rng.choice(STATUS_CASES)
    situation = case.format(entity=rng.choice(ENTITIES), id=rng.randint(10, 9999))
    prompt = (
        f"Сервис следует семантике HTTP. Ситуация: {situation}. Какой код ответа он вернёт? "
        "Ответ — число."
    )
    return Instance(prompt, str(code), {"situation": situation})


def idempotency(rng: random.Random) -> Instance:
    existing, repeats = rng.randint(3, 40), rng.randint(2, 5)
    order_id = rng.randint(100, 999)
    requests = [
        ("POST /orders", existing + repeats),
        ("POST /orders с одинаковым заголовком Idempotency-Key", existing + 1),
        (f"PUT /orders/{order_id} (такого заказа ещё нет)", existing + 1),
        (f"DELETE /orders/{order_id} (заказ есть)", existing - 1),
        (f"GET /orders/{order_id}", existing),
    ]
    request, total = rng.choice(requests)
    prompt = (
        f"Заказов в системе: {existing}. Из-за обрывов сети клиент повторял запрос {request}, "
        f"всего отправок — {repeats}, и каждая дошла до сервера. Сервер реализует методы по "
        "семантике HTTP. Сколько заказов станет в системе? Ответ — число."
    )
    params = {"existing": existing, "repeats": repeats, "request": request}
    return Instance(prompt, str(total), params)


def pagination(rng: random.Random) -> Instance:
    total, per_page = rng.randint(30, 200), rng.choice([10, 20, 25, 50])
    pages = -(-total // per_page)
    page = rng.randint(max(1, pages - 2), pages + 1)
    start = (page - 1) * per_page
    last = min(page * per_page, total) if start < total else 0
    prompt = (
        f"В каталоге {total} товаров с id от 1 до {total}, API отдаёт их по возрастанию id. "
        f"Клиент запрашивает GET /items?page={page}&per_page={per_page}, страницы нумеруются "
        "с 1. Какой id у последнего товара в ответе? Если страница пустая — ответ 0."
    )
    return Instance(prompt, str(last), {"total": total, "per_page": per_page, "page": page})


def cache_max_age(rng: random.Random) -> Instance:
    max_age = rng.choice([30, 60, 90, 120])
    moments = sorted(rng.sample(range(5, 7 * max_age), rng.randint(6, 10)))
    if max_age not in moments:  # ровно на границе свежести — ловушка
        moments = sorted([*moments[:-1], max_age])
    cached_at, to_server = 0, 1
    for t in moments:
        if t - cached_at >= max_age:
            cached_at, to_server = t, to_server + 1
    prompt = (
        f"Ответ API приходит с заголовком Cache-Control: max-age={max_age}, клиент кэширует "
        "его по HTTP. Первый запрос в момент 0 ушёл на сервер. Дальше клиент делает запросы в "
        f"моменты {', '.join(map(str, moments))} (секунды). Сколько запросов всего, считая "
        "первый, уйдут на сервер?"
    )
    return Instance(prompt, str(to_server), {"max_age": max_age, "moments": moments})


def offset_drift(rng: random.Random) -> Instance:
    total, limit = rng.randint(25, 60), rng.choice([5, 10])
    deleted_at_page = rng.randint(1, 2)
    # Удалённые до текущего offset сдвигают выдачу, удалённые дальше — нет.
    candidates = list(range(1, (deleted_at_page + 2) * limit + 1))
    deleted = sorted(rng.sample(candidates, rng.randint(2, 4)))

    ids, seen, offset, page = list(range(1, total + 1)), set(), 0, 0
    while offset < len(ids):
        seen.update(ids[offset : offset + limit])
        offset, page = offset + limit, page + 1
        if page == deleted_at_page:
            ids = [i for i in ids if i not in deleted]
    missed = total - len(deleted) - len(seen - set(deleted))

    prompt = (
        f"Клиент выгружает {total} записей (id от 1 до {total}) запросами "
        f"GET /records?offset=…&limit={limit}, сортировка по id, offset растёт на {limit}. "
        f"Сразу после страницы {deleted_at_page} из базы удалили записи с id "
        f"{', '.join(map(str, deleted))}. Сколько из оставшихся записей клиент так и не получит?"
    )
    params = {"total": total, "limit": limit, "page": deleted_at_page, "deleted": deleted}
    return Instance(prompt, str(missed), params)


def status_codes(rng: random.Random) -> Instance:
    cases = rng.sample(STATUS_CASES, 4)
    lines = [
        f"{i}. " + case.format(entity=rng.choice(ENTITIES), id=rng.randint(10, 9999))
        for i, (case, _) in enumerate(cases, 1)
    ]
    prompt = (
        "Сервис следует семантике HTTP. Какие коды ответа он вернёт в ситуациях ниже? Ответ — "
        "четыре числа через пробел по порядку ситуаций."
    )
    answer = " ".join(str(code) for _, code in cases)
    return Instance(prompt, answer, {"situations": lines}, code="\n".join(lines))


# (запрос, безопасный, идемпотентный) по семантике HTTP (RFC 9110, §9.2).
METHOD_CASES = [
    ("GET /{entity}s/{id}", True, True),
    ("HEAD /{entity}s/{id}", True, True),
    ("OPTIONS /{entity}s", True, True),
    ("PUT /{entity}s/{id} — замена целиком", False, True),
    ("DELETE /{entity}s/{id}", False, True),
    ("POST /{entity}s — создание", False, False),
    ('PATCH /{entity}s/{id} с телом {{"op": "increment"}}', False, False),
    ("POST /{entity}s/{id}/cancel", False, False),
]
ENTITY_PATHS = ["order", "invoice", "report", "user", "item", "payment"]


def safe_methods(rng: random.Random) -> Instance:
    cases = [rng.choice(METHOD_CASES) for _ in range(6)]
    lines = [
        f"{i}. " + text.format(entity=rng.choice(ENTITY_PATHS), id=rng.randint(1, 999))
        for i, (text, _, _) in enumerate(cases, 1)
    ]
    letters = ["Б" if safe else "И" if idem else "Н" for _, safe, idem in cases]
    prompt = (
        "Для каждого запроса определите по семантике HTTP: Б — безопасный (и потому "
        "идемпотентный), И — идемпотентный, но не безопасный, Н — ни то ни другое. Ответ — "
        "шесть букв через пробел по порядку запросов."
    )
    return Instance(prompt, " ".join(letters), {"requests": lines}, code="\n".join(lines))


def page_bounds(rng: random.Random) -> Instance:
    total, per_page = rng.randint(30, 400), rng.choice([10, 20, 25, 50])
    pages = -(-total // per_page)
    page = rng.randint(max(1, pages - 3), pages)
    first = (page - 1) * per_page + 1
    last = min(page * per_page, total)
    prompt = (
        f"В каталоге {total} товаров с id от 1 до {total}, API отдаёт их по возрастанию id. "
        f"Клиент запрашивает GET /items?page={page}&per_page={per_page}, страницы нумеруются "
        "с 1. Какие id у первого и последнего товара в ответе? Ответ — два числа через пробел."
    )
    params = {"total": total, "per_page": per_page, "page": page}
    return Instance(prompt, f"{first} {last}", params)


SIMPLE_TYPES = ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"]


def cors_preflight(rng: random.Random) -> Instance:
    requests, answers = [], []
    for i in range(1, 7):
        method = rng.choice(["GET", "POST", "PUT", "DELETE", "PATCH", "GET", "POST"])
        headers: list[str] = []
        if method in ("POST", "PUT", "PATCH"):
            headers.append(f"Content-Type: {rng.choice([*SIMPLE_TYPES, 'application/json'])}")
        if rng.random() < 0.3:
            headers.append(rng.choice(["Authorization: Bearer …", "X-Request-Id: 42"]))
        if rng.random() < 0.3:
            headers.append(rng.choice(["Accept-Language: ru", "Accept: application/json"]))
        simple_method = method in ("GET", "HEAD", "POST")
        simple_headers = all(
            h.startswith(("Accept", "Content-Language"))
            or (h.startswith("Content-Type") and h.split(": ")[1] in SIMPLE_TYPES)
            for h in headers
        )
        answers.append("да" if not (simple_method and simple_headers) else "нет")
        requests.append(f"{i}. {method} " + ("; ".join(headers) if headers else "без заголовков"))
    prompt = (
        "Страница с app.example.ru вызывает fetch к api.example.ru — другой origin. Для каких "
        "запросов браузер сначала отправит предварительный запрос OPTIONS? Ответ — «да» или "
        "«нет» для каждого запроса через пробел по порядку."
    )
    return Instance(prompt, " ".join(answers), {"requests": requests}, code="\n".join(requests))


def retry_backoff(rng: random.Random) -> Instance:
    base, factor = rng.choice([0.5, 1, 2]), rng.choice([2, 3])
    cap, attempt = rng.choice([10, 20, 30, 60]), rng.randint(4, 7)
    timeout = rng.choice([1, 2, 5])
    moment, delay = 0.0, float(base)
    for _ in range(attempt - 1):
        moment += timeout + delay
        delay = min(delay * factor, cap)
    prompt = (
        f"Клиент повторяет упавший запрос: каждая попытка ждёт ответа {timeout} с и падает по "
        f"таймауту, пауза перед первым повтором — {base} с, каждая следующая пауза в {factor} "
        f"раза длиннее, но не больше {cap} с. Первая попытка ушла в момент 0. В какой момент "
        f"(в секундах) уйдёт попытка номер {attempt}? Ответ — число."
    )
    params = {"base": base, "factor": factor, "cap": cap, "attempt": attempt, "timeout": timeout}
    return Instance(prompt, f"{moment:g}", params)


def etag_conditional(rng: random.Random) -> Instance:
    version, cached, events, codes = 1, None, [], []
    for i in range(1, 8):
        if i > 1 and rng.random() < 0.35:
            version += 1
            events.append(f"{i}. ресурс изменили на сервере")
            continue
        if cached is None or rng.random() < 0.2:
            events.append(f"{i}. GET /profile без заголовков кэша")
            codes.append(200)
        else:
            events.append(f'{i}. GET /profile с If-None-Match: "v{cached}"')
            codes.append(304 if cached == version else 200)
        cached = version
    prompt = (
        'Сервер отдаёт /profile с заголовком ETag: "v<номер версии>", начиная с версии 1, и '
        "поддерживает условные запросы. Клиент запоминает ETag из каждого ответа 200. Какие "
        "коды ответа получат запросы? Ответ — коды через пробел по порядку запросов."
    )
    return Instance(prompt, " ".join(map(str, codes)), {"events": events}, code="\n".join(events))


def cache_revalidation(rng: random.Random) -> Instance:
    max_age = rng.choice([30, 60, 90, 120])
    moments = sorted(rng.sample(range(5, 7 * max_age), rng.randint(6, 9)))
    if max_age not in moments:  # ровно на границе свежести — ловушка
        moments = sorted([*moments[:-1], max_age])
    cached_at, to_server = 0, []
    for t in moments:
        if t - cached_at >= max_age:
            cached_at = t
            to_server.append(t)
    prompt = (
        f"Ответ API приходит с заголовком Cache-Control: max-age={max_age}, клиент кэширует "
        "его по HTTP. Первый запрос в момент 0 ушёл на сервер. Дальше клиент делает запросы в "
        f"моменты {', '.join(map(str, moments))} (секунды). Какие из этих запросов уйдут на "
        "сервер? Ответ — их моменты через пробел; если ни один — 0."
    )
    answer = " ".join(map(str, to_server)) or "0"
    return Instance(prompt, answer, {"max_age": max_age, "moments": moments})


def fixed_window(rng: random.Random) -> Instance:
    limit, window = rng.randint(2, 4), rng.choice([10, 30, 60])
    moments = sorted(rng.sample(range(0, 3 * window), rng.randint(8, 10)))
    counts: dict[int, int] = {}
    codes = []
    for t in moments:
        bucket = t // window
        counts[bucket] = counts.get(bucket, 0) + 1
        codes.append(200 if counts[bucket] <= limit else 429)
    prompt = (
        f"API пропускает не больше {limit} запросов за окно в {window} с; окна фиксированные: "
        f"[0, {window}), [{window}, {2 * window}) и так далее. Лишние запросы получают 429. "
        f"Клиент шлёт запросы в моменты {', '.join(map(str, moments))} (секунды). Какие коды "
        "получат запросы? Ответ — коды через пробел по порядку."
    )
    return Instance(
        prompt, " ".join(map(str, codes)), {"limit": limit, "window": window, "moments": moments}
    )


def optimistic_locking(rng: random.Random) -> Instance:
    version = 1
    lines, codes = [], []
    clients = {"A": version, "B": version}
    for i in range(1, 9):
        client = rng.choice("AB")
        if rng.random() < 0.35:
            clients[client] = version
            lines.append(f"{i}. {client}: GET /accounts/7 → запоминает версию")
            continue
        lines.append(f"{i}. {client}: PUT /accounts/7 с If-Match — последняя известная версия")
        if clients[client] == version:
            version += 1
            clients[client] = version
            codes.append(200)
        else:
            codes.append(412)
    prompt = (
        "Счёт 7 сейчас в версии 1. Оба клиента A и B уже "
        "сделали GET и знают версию 1. Сервер применяет PUT только при совпадении If-Match с "
        "текущей версией и тогда увеличивает версию на 1; после своего успешного PUT клиент "
        "знает новую версию. Какие коды ответа получат запросы PUT? Ответ — коды через пробел "
        "по порядку."
    )
    return Instance(
        prompt, " ".join(map(str, codes)) or "0", {"lines": lines}, code="\n".join(lines)
    )


def offset_drift_missed(rng: random.Random) -> Instance:
    limit = rng.choice([5, 10, 20])
    pages_before = rng.randint(1, 3)
    total = limit * (pages_before + rng.randint(2, 4))
    fetched = pages_before * limit
    shifted = rng.randint(1, min(4, limit - 1))
    deleted = sorted(
        rng.sample(range(1, fetched + 1), shifted) + rng.sample(range(fetched + 1, total + 1), 2)
    )

    ids, seen, offset, page = list(range(1, total + 1)), set(), 0, 0
    while offset < len(ids):
        seen.update(ids[offset : offset + limit])
        offset, page = offset + limit, page + 1
        if page == pages_before:
            ids = [i for i in ids if i not in deleted]
    missed = sorted(set(range(1, total + 1)) - set(deleted) - seen)

    prompt = (
        f"Клиент выгружает {total} записей (id от 1 до {total}) запросами "
        f"GET /records?offset=…&limit={limit}, сортировка по id, offset растёт на {limit}. "
        f"Сразу после страницы {pages_before} из базы удалили записи с id "
        f"{', '.join(map(str, deleted))}. Какие из оставшихся записей клиент так и не получит? "
        "Ответ — их id через пробел по возрастанию; если таких нет — 0."
    )
    params = {"total": total, "limit": limit, "page": pages_before, "deleted": deleted}
    return Instance(prompt, " ".join(map(str, missed)) or "0", params)


def timeout_budget(rng: random.Random) -> Instance:
    gateway = rng.randint(4, 24) / 2
    service_timeout, retries = rng.choice([1, 2, 3]), rng.randint(1, 3)
    backoff = rng.choice([0.2, 0.5, 1])
    downstream = rng.randint(2, 50) / 10
    attempt_time = min(downstream, service_timeout)
    ok = downstream < service_timeout
    total = attempt_time if ok else (retries + 1) * attempt_time + retries * backoff
    answer = f"{min(total, gateway):g}"
    prompt = (
        f"Шлюз ждёт ответа сервиса A не дольше {gateway} с. Сервис A вызывает сервис B с "
        f"таймаутом {service_timeout} с и при таймауте повторяет вызов до {retries} раз с паузой "
        f"{backoff} с между вызовами. Сервис B сейчас отвечает за {downstream} с. Через сколько "
        "секунд после запроса клиент получит ответ шлюза (успешный или ошибку)? Остальным "
        "временем пренебречь. Ответ — число."
    )
    params = {
        "gateway": gateway,
        "timeout": service_timeout,
        "retries": retries,
        "backoff": backoff,
        "downstream": downstream,
    }
    return Instance(prompt, answer, params)
