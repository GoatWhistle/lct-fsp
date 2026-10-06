"""Безопасность приложений: перебор паролей, SQL-инъекции, ограничение частоты, проверка JWT."""

import random

from app.assessment.bank.family import Instance
from app.assessment.bank.sql import CUSTOMERS, render, run_sql

ALPHABETS = [
    ("только цифры", 10),
    ("строчные латинские буквы", 26),
    ("цифры и строчные латинские буквы", 36),
    ("строчные и заглавные латинские буквы", 52),
]


def password_space(rng: random.Random) -> Instance:
    alphabet, size = rng.choice(ALPHABETS)
    length = rng.randint(4, 8)
    known = rng.randint(0, 2)
    leak = [
        "",
        " Первый символ злоумышленник уже знает.",
        " Первые два символа злоумышленник уже знает.",
    ][known]
    prompt = (
        f"Пароль — ровно {length} символов, алфавит — {alphabet}.{leak} Сколько вариантов "
        "придётся перебрать в худшем случае? Ответ — целое число."
    )
    params = {"alphabet": size, "length": length, "known": known}
    return Instance(prompt, str(size ** (length - known)), params)


def sql_injection(rng: random.Random) -> Instance:
    names = rng.sample(CUSTOMERS, rng.randint(4, 6))
    rows = [
        (i + 1, name, rng.choice(["admin", "user"]), int(rng.random() < 0.75))
        for i, name in enumerate(names)
    ]
    target = rng.choice(names)
    payload = rng.choice(
        [
            "x' OR '1'='1",
            f"{target}' --",
            "' OR role = 'admin' --",
            f"{target}' AND role = 'admin' --",
            target,
        ]
    )
    schema = {"users": (("id", "name", "role", "active"), rows)}
    count = run_sql(schema, f"SELECT COUNT(*) FROM users WHERE name = '{payload}' AND active = 1")
    code = (
        "def find(name):\n"
        '    sql = "SELECT * FROM users WHERE name = \'" + name + "\' AND active = 1"\n'
        "    return db.execute(sql).fetchall()\n\n"
        + render("users", ("id", "name", "role", "active"), rows)
    )
    prompt = f"Сколько строк вернёт find, если пользователь ввёл: {payload}"
    return Instance(prompt, count, {"users": rows, "payload": payload}, code=code)


def token_bucket(rng: random.Random) -> Instance:
    capacity, refill = rng.randint(2, 5), rng.randint(1, 2)
    moments = sorted(rng.choices(range(0, 6), k=rng.randint(9, 13)))
    tokens, second, rejected = capacity, 0, 0
    for t in moments:
        while second < t:
            second += 1
            tokens = min(capacity, tokens + refill)
        if tokens > 0:
            tokens -= 1
        else:
            rejected += 1
    prompt = (
        f"Ограничитель частоты — token bucket: ёмкость {capacity}, в начале каждой секунды "
        f"(t = 1, 2, …) добавляется токенов: {refill}, но не больше ёмкости. В момент 0 ведро "
        "полное. Запрос забирает один токен, без токена — отклоняется. Запросы пришли в секунды: "
        f"{', '.join(map(str, moments))}. Сколько запросов будет отклонено?"
    )
    params = {"capacity": capacity, "refill": refill, "moments": moments}
    return Instance(prompt, str(rejected), params)


def jwt_validity(rng: random.Random) -> Instance:
    now, leeway = rng.randint(1000, 9000), rng.choice([0, 30, 60])
    # (alg, подпись верна, nbf, exp)
    tokens = [
        (
            "none" if rng.random() < 0.15 else "HS256",
            rng.random() > 0.15,
            now + rng.choice([-600, -300, -30, 0, 20, 45]),
            now + rng.choice([-45, -20, 0, 30, 600, 900]),
        )
        for _ in range(6)
    ]
    accepted = sum(
        1
        for alg, signature_ok, nbf, exp in tokens
        if alg == "HS256" and signature_ok and nbf <= now + leeway and exp > now - leeway
    )
    code = "\n".join(
        f"#{i}: alg={alg}, подпись {'верна' if ok else 'не сходится'}, nbf={nbf}, exp={exp}"
        for i, (alg, ok, nbf, exp) in enumerate(tokens, start=1)
    )
    prompt = (
        f"Сервер принимает только HS256 и проверяет nbf и exp с допуском leeway = {leeway} с, как "
        f"PyJWT. Сейчас {now}. Сколько токенов из списка он примет?"
    )
    params = {"now": now, "leeway": leeway, "tokens": tokens}
    return Instance(prompt, str(accepted), params, code=code)
