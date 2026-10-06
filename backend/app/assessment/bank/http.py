"""HTTP и API: коды ответов, идемпотентность, пагинация, кэширование."""

import random

from app.assessment.bank.family import Instance

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
