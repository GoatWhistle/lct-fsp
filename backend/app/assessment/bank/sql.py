"""Базы данных и SQL: результат запроса к маленькой таблице. Эталон — исполнение в SQLite."""

import random
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from typing import Any

from app.assessment.bank.family import Instance

CUSTOMERS = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "igor"]
STATUSES = ["paid", "new", "cancelled"]

Rows = Sequence[tuple[Any, ...]]
Schema = Mapping[str, tuple[Sequence[str], Rows]]


def run_sql(schema: Schema, query: str) -> str:
    with closing(sqlite3.connect(":memory:")) as db:
        for table, (columns, rows) in schema.items():
            db.execute(f"CREATE TABLE {table} ({', '.join(columns)})")
            marks = ", ".join("?" for _ in columns)
            db.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        (value,) = db.execute(query).fetchone()
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


def _instance(schema: Schema, query: str, params: dict[str, Any]) -> Instance:
    tables = "\n\n".join(render(name, cols, rows) for name, (cols, rows) in schema.items())
    params = {**params, **{name: rows for name, (_, rows) in schema.items()}}
    return Instance(PROMPT, run_sql(schema, query), params, code=f"{tables}\n\n{query}")


def count_where(rng: random.Random) -> Instance:
    rows = _orders(rng, 8)
    threshold, status = rng.randrange(200, 800, 50), rng.choice(STATUSES[:2])
    query = f"SELECT COUNT(*) FROM orders WHERE amount > {threshold} AND status <> '{status}';"
    params = {"threshold": threshold, "status": status}
    return _instance({"orders": (ORDER_COLUMNS, rows)}, query, params)


def group_having(rng: random.Random) -> Instance:
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
    return _instance({"orders": (ORDER_COLUMNS, rows)}, query, {"threshold": threshold})


def left_join_on(rng: random.Random) -> Instance:
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
    return _instance(schema, query, {"threshold": threshold})


def window_rank(rng: random.Random) -> Instance:
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
    return _instance({"orders": (ORDER_COLUMNS, rows)}, query, {"rank": rank})
