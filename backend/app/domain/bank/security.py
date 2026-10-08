"""Безопасность приложений: перебор паролей, SQL-инъекции, ограничение частоты, проверка JWT."""

import random

from app.domain.bank.family import Instance, rounded
from app.domain.bank.runner import CodeRunner
from app.domain.bank.sql import CUSTOMERS, render, run_sql

ALPHABETS = [
    ("только цифры", 10),
    ("строчные латинские буквы", 26),
    ("цифры и строчные латинские буквы", 36),
    ("строчные и заглавные латинские буквы", 52),
]


def password_space(rng: random.Random, runner: CodeRunner) -> Instance:
    alphabet, size = rng.choice(ALPHABETS)
    length = rng.randint(4, 10)
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


def sql_injection(rng: random.Random, runner: CodeRunner) -> Instance:
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
    count = run_sql(
        runner, schema, f"SELECT COUNT(*) FROM users WHERE name = '{payload}' AND active = 1"
    )
    code = (
        "def find(name):\n"
        '    sql = "SELECT * FROM users WHERE name = \'" + name + "\' AND active = 1"\n'
        "    return db.execute(sql).fetchall()\n\n"
        + render("users", ("id", "name", "role", "active"), rows)
    )
    prompt = f"Сколько строк вернёт find, если пользователь ввёл: {payload}"
    return Instance(prompt, count, {"users": rows, "payload": payload}, code=code)


def token_bucket(rng: random.Random, runner: CodeRunner) -> Instance:
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


def jwt_validity(rng: random.Random, runner: CodeRunner) -> Instance:
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


def html_escape(rng: random.Random, runner: CodeRunner) -> Instance:
    import html

    parts = [
        rng.choice(["<b>", "<script>", "<img>", "<a>"]),
        rng.choice(["Tom&Jerry", "R&D", "a&b", "x&y"]),
        rng.choice(['"q"', "'q'", '"hi"', "'ok'"]),
        rng.choice(["1<2", "3>2", "x>=y", "a<b"]),
    ]
    rng.shuffle(parts)
    text = "".join(parts[: rng.randint(2, 4)])
    code = f"import html\n\nprint(html.escape({text!r}))\n"
    prompt = "Что выведет программа? Ответ — строка ровно как в консоли."
    return Instance(prompt, html.escape(text), {"text": text}, code=code)


def injection_rows(rng: random.Random, runner: CodeRunner) -> Instance:
    names = rng.sample(CUSTOMERS, rng.randint(6, 8))
    # id вразброс: иначе совпадающие наборы строк дают одинаковые ответы у разных экземпляров.
    ids = sorted(rng.sample(range(1, 100), len(names)))
    rows = [
        (row_id, name, rng.choice(["admin", "user", "user"]), int(rng.random() < 0.7))
        for row_id, name in zip(ids, names, strict=True)
    ]
    target = rng.choice(names)
    payload = rng.choice(
        [
            "x' OR '1'='1",
            f"{target}' --",
            "' OR role = 'admin' --",
            f"{target}' AND role = 'admin' --",
            "x' OR active = 0 --",
            f"x' OR name > '{rng.choice(names)}' --",
            f"x' OR id >= {rng.choice(ids[1:])} AND '1'='1",
            target,
        ]
    )
    schema = {"users": (("id", "name", "role", "active"), rows)}
    query = f"SELECT id FROM users WHERE name = '{payload}' AND active = 1 ORDER BY id"
    found = [str(r[0]) for r in runner.sql(schema, query)]
    code = (
        "def find(name):\n"
        '    sql = "SELECT id FROM users WHERE name = \'" + name + "\' '
        'AND active = 1 ORDER BY id"\n'
        "    return db.execute(sql).fetchall()\n\n"
        + render("users", ("id", "name", "role", "active"), rows)
    )
    prompt = (
        f"Пользователь ввёл в поле имени: {payload}\nКакие id вернёт find? Ответ — числа через "
        "пробел по возрастанию; если ни одной строки — 0."
    )
    return Instance(prompt, " ".join(found) or "0", {"users": rows, "payload": payload}, code=code)


def cookie_sending(rng: random.Random, runner: CodeRunner) -> Instance:
    path = rng.choice(["/", "/app", "/api"])
    secure = rng.random() < 0.5
    samesite = rng.choice(["Strict", "Lax", "None"])
    if samesite == "None":
        secure = True
    attrs = f"Path={path}" + ("; Secure" if secure else "") + f"; SameSite={samesite}"
    requests, answers = [], []
    inside = [
        path if path != "/" else "/",
        f"{path.rstrip('/')}/home",
        f"{path.rstrip('/')}/orders",
    ]
    outside = ["/apps", "/static/app.js", "/ap"] if path != "/" else []
    for i in range(1, 7):
        # В каждом запросе нарушаем не больше одного условия — ответы не сводятся к «нет».
        broken = rng.choice(["scheme", "path", "site", None, None])
        scheme = "http" if broken == "scheme" else "https"
        req_path = rng.choice(outside) if broken == "path" and outside else rng.choice(inside)
        origin = "чужого сайта" if broken == "site" or rng.random() < 0.2 else "своего сайта"
        kind = rng.choice(["переход по ссылке (GET)", "fetch POST", "картинка <img>"])
        sent = (
            (not secure or scheme == "https")
            and (req_path == path or req_path.startswith(path.rstrip("/") + "/"))
            and (
                origin == "своего сайта"
                or samesite == "None"
                or (samesite == "Lax" and kind.startswith("переход"))
            )
        )
        requests.append(f"{i}. {scheme}://shop.example{req_path} — {kind} со страницы {origin}")
        answers.append("да" if sent else "нет")
    prompt = (
        f"Сайт shop.example поставил cookie session с атрибутами {attrs}. Отправит ли браузер "
        "её с каждым запросом ниже? Ответ — «да» или «нет» для каждого запроса через пробел."
    )
    params = {"path": path, "secure": secure, "samesite": samesite, "requests": requests}
    return Instance(prompt, " ".join(answers), params, code="\n".join(requests))


def hash_cost(rng: random.Random, runner: CodeRunner) -> Instance:
    base_cost, base_ms = rng.randint(8, 10), rng.choice([20, 40, 60, 80, 100])
    cost = base_cost + rng.randint(1, 4)
    guesses = rng.choice([1000, 5000, 10000, 50000])
    ms = base_ms * 2 ** (cost - base_cost)
    hours = guesses * ms / 1000 / 3600
    prompt = (
        f"bcrypt с cost = {base_cost} считает один хэш за {base_ms} мс на сервере атакующего; "
        "каждое увеличение cost на 1 удваивает время. Пароли хранят с cost = "
        f"{cost}. Сколько миллисекунд займёт один хэш и сколько часов — проверка {guesses} "
        "вариантов одного пароля в один поток? Ответ — два числа через пробел, часы округлите "
        "до десятых."
    )
    params = {"base_cost": base_cost, "base_ms": base_ms, "cost": cost, "guesses": guesses}
    return Instance(prompt, f"{ms} {rounded(hours, 1)}", params)


def password_policy(rng: random.Random, runner: CodeRunner) -> Instance:
    min_len = rng.randint(8, 12)
    candidates = []
    for _ in range(6):
        length = rng.randint(min_len - 3, min_len + 4)
        pool = "abcdefgh"
        if rng.random() < 0.6:
            pool += "ABCDEF"
        if rng.random() < 0.6:
            pool += "0123456789"
        if rng.random() < 0.4:
            pool += "!@#$%"
        candidates.append("".join(rng.choice(pool) for _ in range(length)))
    ok = []
    for i, pw in enumerate(candidates, 1):
        classes = sum(
            any(c in group for c in pw) for group in ("abcdefgh", "ABCDEF", "0123456789", "!@#$%")
        )
        if len(pw) >= min_len and classes >= 3:
            ok.append(i)
    lines = [f"{i}. {pw}" for i, pw in enumerate(candidates, 1)]
    prompt = (
        f"Политика паролей: длина не меньше {min_len} символов и символы хотя бы трёх классов из "
        "четырёх — строчные буквы, заглавные буквы, цифры, спецсимволы. Какие пароли пройдут "
        "проверку? Ответ — номера через пробел; если ни один — 0."
    )
    return Instance(
        prompt,
        " ".join(map(str, ok)) or "0",
        {"min_len": min_len, "passwords": candidates},
        code="\n".join(lines),
    )


def bucket_statuses(rng: random.Random, runner: CodeRunner) -> Instance:
    capacity, refill = rng.randint(2, 4), rng.randint(1, 2)
    moments = sorted(rng.choices(range(0, 6), k=rng.randint(9, 11)))
    tokens, second, codes = capacity, 0, []
    for t in moments:
        while second < t:
            second += 1
            tokens = min(capacity, tokens + refill)
        if tokens > 0:
            tokens -= 1
            codes.append(200)
        else:
            codes.append(429)
    prompt = (
        f"Ограничитель частоты — token bucket: ёмкость {capacity}, в начале каждой секунды "
        f"(t = 1, 2, …) добавляется токенов: {refill}, но не больше ёмкости. В момент 0 ведро "
        "полное. Запрос забирает один токен, без токена получает 429. Запросы пришли в секунды: "
        f"{', '.join(map(str, moments))}. Какие коды получат запросы? Ответ — коды через пробел."
    )
    params = {"capacity": capacity, "refill": refill, "moments": moments}
    return Instance(prompt, " ".join(map(str, codes)), params)


ROLE_PERMISSIONS = {
    "viewer": {"read"},
    "editor": {"read", "write"},
    "auditor": {"read", "export"},
    "admin": {"read", "write", "delete", "export"},
}


def rbac_decisions(rng: random.Random, runner: CodeRunner) -> Instance:
    # admin разрешает всё — даём его редко, иначе ответ почти всегда «да».
    pool = ["viewer", "editor", "auditor"] * 3 + ["admin"]
    users = {
        name: sorted({rng.choice(pool) for _ in range(rng.randint(1, 2))})
        for name in rng.sample(["ann", "bob", "eve", "kim", "max"], 3)
    }
    denied = {rng.choice(list(users)): rng.choice(["write", "export", "delete"])}
    requests, answers = [], []
    for i in range(1, 7):
        user = rng.choice(list(users))
        action = rng.choice(["read", "write", "delete", "export"])
        allowed = any(action in ROLE_PERMISSIONS[r] for r in users[user])
        if denied.get(user) == action:
            allowed = False
        requests.append(f"{i}. {user}: {action}")
        answers.append("да" if allowed else "нет")
    roles = "; ".join(f"{r}: {', '.join(sorted(p))}" for r, p in ROLE_PERMISSIONS.items())
    members = "; ".join(f"{u}: {', '.join(rs)}" for u, rs in users.items())
    ((who, what),) = denied.items()
    prompt = (
        f"Права ролей: {roles}. Роли пользователей: {members}. Права ролей складываются, но "
        f"явный запрет сильнее любого разрешения: {who} запрещено {what}. Разрешит ли система "
        "запросы ниже? Ответ — «да» или «нет» для каждого через пробел."
    )
    params = {"users": users, "denied": denied, "requests": requests}
    return Instance(prompt, " ".join(answers), params, code="\n".join(requests))


def replay_window(rng: random.Random, runner: CodeRunner) -> Instance:
    window = rng.choice([30, 60, 120])
    now0 = rng.randint(1000, 9000)
    seen: set[str] = set()
    lines, codes = [], []
    nonces = [f"n{rng.randint(10, 99)}" for _ in range(4)]
    for i in range(1, 7):
        now = now0 + 10 * i
        ts = now - rng.choice([0, 5, window - 5, window, window + 5, 3 * window, -20])
        nonce = rng.choice(nonces)
        signature_ok = rng.random() > 0.15
        ok = signature_ok and abs(now - ts) <= window and nonce not in seen
        if ok:
            seen.add(nonce)
        codes.append(200 if ok else 401)
        lines.append(
            f"{i}. пришёл в {now}: timestamp={ts}, nonce={nonce}, подпись "
            + ("верна" if signature_ok else "не сходится")
        )
    prompt = (
        "Сервер принимает запрос, подписанный HMAC, если подпись верна, |время прихода − "
        f"timestamp| ≤ {window} с и nonce ещё не встречался в принятых запросах. Остальным — 401. "
        "Какие коды получат запросы? Ответ — коды через пробел."
    )
    return Instance(
        prompt, " ".join(map(str, codes)), {"window": window, "lines": lines}, code="\n".join(lines)
    )


def path_traversal(rng: random.Random, runner: CodeRunner) -> Instance:
    import posixpath

    base = "/srv/files"
    inputs = []
    for _ in range(6):
        parts = [
            rng.choice(["docs", "img", "..", ".", "reports", "../..", "a/../b"])
            for _ in range(rng.randint(1, 3))
        ]
        name = rng.choice(["x.txt", "passwd", "1.png", "..", "report.pdf"])
        inputs.append("/".join([*parts, name]))
    escaped = []
    for i, raw in enumerate(inputs, 1):
        full = posixpath.normpath(posixpath.join(base, raw))
        if not (full == base or full.startswith(base + "/")):
            escaped.append(i)
    code = (
        "import posixpath\n\n"
        f"BASE = {base!r}\n\n"
        "def open_user_file(name):\n"
        "    path = posixpath.normpath(posixpath.join(BASE, name))\n"
        "    return open(path)\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(inputs, 1))
    )
    prompt = (
        "Функция открывает файл по имени из запроса — без проверки, что путь остался внутри "
        f"{base}. Какие из имён ниже выведут путь за пределы {base}? Ответ — номера через "
        "пробел; если ни одно — 0."
    )
    return Instance(prompt, " ".join(map(str, escaped)) or "0", {"inputs": inputs}, code=code)


def jwt_checks(rng: random.Random, runner: CodeRunner) -> Instance:
    now, leeway = rng.randint(1000, 9000), rng.choice([0, 30, 60])
    tokens = [
        (
            "none" if rng.random() < 0.15 else "HS256",
            rng.random() > 0.15,
            now + rng.choice([-600, -300, -30, 0, 20, 45]),
            now + rng.choice([-45, -20, 0, 30, 600, 900]),
        )
        for _ in range(6)
    ]
    accepted = [
        i
        for i, (alg, signature_ok, nbf, exp) in enumerate(tokens, start=1)
        if alg == "HS256" and signature_ok and nbf <= now + leeway and exp > now - leeway
    ]
    code = "\n".join(
        f"#{i}: alg={alg}, подпись {'верна' if ok else 'не сходится'}, nbf={nbf}, exp={exp}"
        for i, (alg, ok, nbf, exp) in enumerate(tokens, start=1)
    )
    prompt = (
        f"Сервер принимает только HS256 и проверяет nbf и exp с допуском leeway = {leeway} с, как "
        f"PyJWT: токен годен при nbf ≤ сейчас + leeway и exp > сейчас − leeway. Сейчас {now}. "
        "Какие токены он примет? Ответ — номера через пробел; если ни один — 0."
    )
    params = {"now": now, "leeway": leeway, "tokens": tokens}
    return Instance(prompt, " ".join(map(str, accepted)) or "0", params, code=code)


def timing_compare(rng: random.Random, runner: CodeRunner) -> Instance:
    secret = "".join(rng.choice("0123456789abcdef") for _ in range(6))
    guesses = []
    for _ in range(4):
        keep = rng.randint(0, 5)
        guess = secret[:keep] + "".join(rng.choice("0123456789abcdef") for _ in range(6 - keep))
        guesses.append(guess)

    def comparisons(guess: str) -> int:
        count = 0
        for a, b in zip(secret, guess, strict=True):
            count += 1
            if a != b:
                break
        return count

    code = (
        "def check(token):\n"
        f"    secret = {secret!r}\n"
        "    for a, b in zip(secret, token):\n"
        "        if a != b:\n"
        "            return False\n"
        "    return True\n"
    )
    prompt = (
        f"Злоумышленник меряет время check для токенов {', '.join(guesses)}. Сколько сравнений "
        "символов (a != b) выполнит check для каждого? Именно эта разница во времени и "
        "выдаёт секрет. Ответ — четыре числа через пробел."
    )
    answer = " ".join(str(comparisons(g)) for g in guesses)
    return Instance(prompt, answer, {"secret": secret, "guesses": guesses}, code=code)
