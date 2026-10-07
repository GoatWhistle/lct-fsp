"""Базы данных и SQL: результат запроса к маленькой таблице. Эталон — исполнение в SQLite."""

import random
from collections.abc import Sequence
from typing import Any

from app.domain.bank.family import Instance
from app.domain.bank.runner import CodeRunner, Rows, Schema

CUSTOMERS = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "igor"]
STATUSES = ["paid", "new", "cancelled"]


def run_sql(runner: CodeRunner, schema: Schema, query: str) -> str:
    """Единственное значение первой строки результата."""
    (value,) = runner.sql(schema, query)[0]
    return str(value)


def render(table: str, columns: Sequence[str], rows: Rows) -> str:
    cells = [list(columns)] + [["NULL" if v is None else str(v) for v in row] for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(columns))]
    lines = [" | ".join(v.ljust(w) for v, w in zip(row, widths, strict=True)) for row in cells]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return f"{table}\n" + "\n".join(lines)


def _orders(rng: random.Random, n: int) -> list[tuple[Any, ...]]:
    customers = rng.sample(CUSTOMERS, 4)
    return [
        (i + 1, rng.choice(customers), rng.randrange(100, 1000, 10), rng.choice(STATUSES))
        for i in range(n)
    ]


ORDER_COLUMNS = ("id", "customer", "amount", "status")
PROMPT = "Что вернёт запрос к таблице ниже? Ответ — одно число."


def _instance(runner: CodeRunner, schema: Schema, query: str, params: dict[str, Any]) -> Instance:
    tables = "\n\n".join(render(name, cols, rows) for name, (cols, rows) in schema.items())
    params = {**params, **{name: rows for name, (_, rows) in schema.items()}}
    return Instance(PROMPT, run_sql(runner, schema, query), params, code=f"{tables}\n\n{query}")


def count_where(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 8)
    threshold, status = rng.randrange(200, 800, 50), rng.choice(STATUSES[:2])
    query = f"SELECT COUNT(*) FROM orders WHERE amount > {threshold} AND status <> '{status}';"
    params = {"threshold": threshold, "status": status}
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, params)


def group_having(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 9)
    threshold = rng.randrange(600, 1500, 100)
    query = (
        "SELECT COUNT(*) FROM (\n"
        "  SELECT customer FROM orders\n"
        "  WHERE status <> 'cancelled'\n"
        "  GROUP BY customer\n"
        f"  HAVING SUM(amount) > {threshold}\n"
        ") AS t;"
    )
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, {"threshold": threshold})


def left_join_on(rng: random.Random, runner: CodeRunner) -> Instance:
    names = rng.sample(CUSTOMERS, 5)
    customers: Rows = [(i + 1, name) for i, name in enumerate(names)]
    orders: Rows = [
        (i + 1, rng.randint(1, 4), rng.choice([None, *range(100, 1000, 50)])) for i in range(7)
    ]
    threshold = rng.randrange(200, 700, 50)
    query = (
        "SELECT COUNT(*)\n"
        "FROM customers c\n"
        f"LEFT JOIN orders o ON o.customer_id = c.id AND o.amount > {threshold};"
    )
    schema = {
        "customers": (("id", "name"), customers),
        "orders": (("id", "customer_id", "amount"), orders),
    }
    return _instance(runner, schema, query, {"threshold": threshold})


def window_rank(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 9)
    # Ничья внутри покупателя — ловушка: RANK отдаёт обеим строкам одно место.
    first = rows[0]
    same = [i for i, row in enumerate(rows) if row[1] == first[1] and i > 0]
    if same:
        i = rng.choice(same)
        rows[i] = (rows[i][0], first[1], first[2], rows[i][3])
    rank = rng.randint(1, 2)
    query = (
        "SELECT SUM(amount) FROM (\n"
        "  SELECT amount,\n"
        "         RANK() OVER (PARTITION BY customer ORDER BY amount DESC) AS r\n"
        "  FROM orders\n"
        f") AS t WHERE r <= {rank};"
    )
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, {"rank": rank})


SEQ_PROMPT = (
    "Что вернёт запрос к таблицам ниже? Ответ — значения результата через пробел: по строкам, "
    "внутри строки — по столбцам."
)


def _seq_instance(
    runner: CodeRunner, schema: Schema, query: str, params: dict[str, Any]
) -> Instance:
    result = [str(v) for row in runner.sql(schema, query) for v in row]
    tables = "\n\n".join(render(name, cols, rows) for name, (cols, rows) in schema.items())
    params = {**params, **{name: rows for name, (_, rows) in schema.items()}}
    return Instance(SEQ_PROMPT, " ".join(result), params, code=f"{tables}\n\n{query}")


def sum_where(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 8)
    threshold, status = rng.randrange(200, 800, 50), rng.choice(STATUSES[:2])
    query = f"SELECT SUM(amount) FROM orders WHERE amount > {threshold} AND status <> '{status}';"
    params = {"threshold": threshold, "status": status}
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, params)


def order_limit(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 9)
    limit, offset = rng.randint(2, 4), rng.randint(1, 3)
    direction = rng.choice(["DESC", "ASC"])
    query = (
        "SELECT SUM(amount) FROM (\n"
        f"  SELECT amount FROM orders ORDER BY amount {direction}, id\n"
        f"  LIMIT {limit} OFFSET {offset}\n"
        ") AS t;"
    )
    params = {"limit": limit, "offset": offset, "direction": direction}
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, params)


def group_having_sum(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 10)
    threshold = rng.randrange(600, 1500, 100)
    query = (
        "SELECT SUM(total) FROM (\n"
        "  SELECT customer, SUM(amount) AS total FROM orders\n"
        "  WHERE status <> 'cancelled'\n"
        "  GROUP BY customer\n"
        f"  HAVING SUM(amount) > {threshold}\n"
        ") AS t;"
    )
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, {"threshold": threshold})


def case_when_sum(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 8)
    paid_sign, other = rng.choice([("amount", "0"), ("amount", "-amount"), ("amount / 10", "0")])
    query = (
        "SELECT SUM(CASE\n"
        f"  WHEN status = 'paid' THEN {paid_sign}\n"
        f"  WHEN status = 'cancelled' THEN {other}\n"
        "  ELSE 1\n"
        "END) FROM orders;"
    )
    params = {"paid": paid_sign, "cancelled": other}
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, params)


def like_between(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 9)
    low = rng.randrange(150, 500, 50)
    high = low + rng.randrange(150, 450, 50)
    letter = rng.choice("abdegvz")
    query = (
        "SELECT SUM(amount) FROM orders\n"
        f"WHERE customer LIKE '%{letter}%' OR amount BETWEEN {low} AND {high};"
    )
    params = {"low": low, "high": high, "letter": letter}
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, params)


def null_aggregates(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = [
        (i + 1, rng.choice(CUSTOMERS[:5]), rng.choice([None, None, *range(10, 200, 10)]))
        for i in range(rng.randint(7, 10))
    ]
    query = "SELECT COUNT(*), COUNT(bonus), SUM(bonus), MAX(bonus) FROM payouts;"
    schema = {"payouts": (("id", "employee", "bonus"), rows)}
    return _seq_instance(runner, schema, query, {})


def left_join_groups(rng: random.Random, runner: CodeRunner) -> Instance:
    names = sorted(rng.sample(CUSTOMERS, 5))
    customers: Rows = [(i + 1, name) for i, name in enumerate(names)]
    orders: Rows = [
        (i + 1, rng.randint(1, 5), rng.choice([None, *range(100, 1000, 50)])) for i in range(8)
    ]
    threshold = rng.randrange(200, 700, 50)
    query = (
        "SELECT c.name, COUNT(o.id)\n"
        "FROM customers c\n"
        f"LEFT JOIN orders o ON o.customer_id = c.id AND o.amount > {threshold}\n"
        "GROUP BY c.name\n"
        "ORDER BY c.name;"
    )
    schema = {
        "customers": (("id", "name"), customers),
        "orders": (("id", "customer_id", "amount"), orders),
    }
    instance = _seq_instance(runner, schema, query.replace("c.name, COUNT", "COUNT"), {})
    # В листинге имя оставляем: так понятнее, какая строка чья; в ответе — только счётчики.
    prompt = (
        "Что вернёт запрос к таблицам ниже? Ответ — значения COUNT(o.id) через пробел в "
        "порядке строк результата."
    )
    code = (instance.code or "").replace(query.replace("c.name, COUNT", "COUNT"), query)
    return Instance(prompt, instance.answer, {**instance.params, "threshold": threshold}, code=code)


def correlated_subquery(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, 10)
    op = rng.choice([">", "<"])
    query = (
        "SELECT SUM(amount) FROM orders o\n"
        f"WHERE amount {op} (\n"
        "  SELECT AVG(amount) FROM orders i WHERE i.customer = o.customer\n"
        ");"
    )
    return _instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, {"op": op})


def union_sums(rng: random.Random, runner: CodeRunner) -> Instance:
    shop = [(rng.randrange(100, 600, 50),) for _ in range(rng.randint(4, 6))]
    web = [
        (rng.choice([r[0] for r in shop]),)
        if rng.random() < 0.5
        else (rng.randrange(100, 600, 50),)
        for _ in range(rng.randint(4, 6))
    ]
    query = (
        "SELECT\n"
        "  (SELECT SUM(amount) FROM (SELECT amount FROM shop UNION SELECT amount FROM web)),\n"
        "  (SELECT SUM(amount) FROM (SELECT amount FROM shop UNION ALL SELECT amount FROM web));"
    )
    schema = {"shop": (("amount",), shop), "web": (("amount",), web)}
    return _seq_instance(runner, schema, query, {})


def running_window(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = [(i + 1, rng.randrange(10, 250, 5)) for i in range(rng.randint(6, 8))]
    before = rng.randint(1, 2)
    query = (
        "SELECT MAX(s) FROM (\n"
        "  SELECT SUM(amount) OVER (\n"
        f"    ORDER BY day ROWS BETWEEN {before} PRECEDING AND CURRENT ROW\n"
        "  ) AS s FROM sales\n"
        ") AS t;"
    )
    schema = {"sales": (("day", "amount"), rows)}
    return _instance(runner, schema, query, {"before": before})


def lag_changes(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = [(i + 1, rng.randrange(100, 300, 10)) for i in range(rng.randint(7, 9))]
    query = "SELECT day, price - LAG(price) OVER (ORDER BY day) AS diff\nFROM prices\nORDER BY day;"
    schema = {"prices": (("day", "price"), rows)}
    instance = _seq_instance(runner, schema, query.replace("day, price", "price"), {})
    answer = instance.answer.replace("None", "NULL")
    prompt = (
        "Что вернёт запрос к таблице ниже? Ответ — значения diff через пробел в порядке строк; "
        "пустое значение — NULL."
    )
    code = (instance.code or "").replace(query.replace("day, price", "price"), query)
    return Instance(prompt, answer, instance.params, code=code)


def distinct_count(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = _orders(rng, rng.randint(8, 10))
    status = rng.choice(STATUSES)
    query = (
        "SELECT customer, COUNT(*), COUNT(DISTINCT status)\n"
        f"FROM orders WHERE status <> '{status}'\n"
        "GROUP BY customer ORDER BY customer;"
    )
    instance = _seq_instance(runner, {"orders": (ORDER_COLUMNS, rows)}, query, {"status": status})
    prompt = (
        "Что вернёт запрос к таблице ниже? Ответ — значения результата через пробел: по строкам, "
        "внутри строки — по столбцам."
    )
    return Instance(prompt, instance.answer, instance.params, code=instance.code)


def exists_subquery(rng: random.Random, runner: CodeRunner) -> Instance:
    names = sorted(rng.sample(CUSTOMERS, 5))
    customers: Rows = [(i + 1, name) for i, name in enumerate(names)]
    orders: Rows = [
        (i + 1, rng.randint(1, 6), rng.randrange(100, 1000, 50)) for i in range(rng.randint(5, 8))
    ]
    threshold = rng.randrange(200, 800, 50)
    negate = rng.random() < 0.5
    query = (
        "SELECT id FROM customers c\n"
        f"WHERE {'NOT ' if negate else ''}EXISTS (\n"
        f"  SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > {threshold}\n"
        ")\n"
        "ORDER BY id;"
    )
    schema = {
        "customers": (("id", "name"), customers),
        "orders": (("id", "customer_id", "amount"), orders),
    }
    instance = _seq_instance(runner, schema, query, {"threshold": threshold, "negate": negate})
    prompt = (
        "Что вернёт запрос к таблицам ниже? Ответ — id через пробел по порядку; если строк нет — 0."
    )
    return Instance(prompt, instance.answer or "0", instance.params, code=instance.code)


def self_join(rng: random.Random, runner: CodeRunner) -> Instance:
    names = rng.sample(CUSTOMERS, 6)
    # Начальник — сотрудник с меньшим id или никто: дерево без циклов.
    employees: Rows = [
        (
            i + 1,
            name,
            rng.choice([None, *range(1, i + 1)]) if i else None,
            rng.randrange(80, 300, 10),
        )
        for i, name in enumerate(names)
    ]
    query = (
        "SELECT e.name, e.salary - m.salary\n"
        "FROM employees e JOIN employees m ON e.manager_id = m.id\n"
        "WHERE e.salary > m.salary\n"
        "ORDER BY e.name;"
    )
    schema = {"employees": (("id", "name", "manager_id", "salary"), employees)}
    instance = _seq_instance(runner, schema, query, {})
    prompt = (
        "Что вернёт запрос к таблице ниже? Ответ — значения результата через пробел: по строкам, "
        "внутри строки — по столбцам; если строк нет — 0."
    )
    return Instance(prompt, instance.answer or "0", instance.params, code=instance.code)
