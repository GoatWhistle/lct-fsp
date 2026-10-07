"""Исполнитель кода генераторов в процессе — реализация порта `CodeRunner` из банка семейств.

Листинги и запросы строит сам генератор, ввода кандидата в них нет, поэтому исполнение — без
песочницы и лимитов. Песочница встанет второй реализацией порта.
"""

import sqlite3
from contextlib import closing
from typing import Any

from app.domain.bank.runner import Row, Schema


class InProcessCodeRunner:
    def python(self, code: str) -> str:
        out: list[str] = []

        def capture(*args: Any, sep: str = " ", end: str = "\n") -> None:
            out.append(sep.join(str(a) for a in args) + end)

        exec(code, {"print": capture})
        return "".join(out)

    def sql(self, schema: Schema, query: str) -> list[Row]:
        with closing(sqlite3.connect(":memory:")) as db:
            for table, (columns, rows) in schema.items():
                db.execute(f"CREATE TABLE {table} ({', '.join(columns)})")
                marks = ", ".join("?" for _ in columns)
                db.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
            return db.execute(query).fetchall()
