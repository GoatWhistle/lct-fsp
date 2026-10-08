"""Исполнитель кода генераторов — порт (docs/adr/0001-layers-and-ports.md).

Часть генераторов считает эталон исполнением: листинг на Python, запрос к таблицам на SQL. Порт
объявлен в банке, а не в `app.usecase.interface`: генераторы — домен, а домен не видит
сценариев. Исполнитель приходит в генератор значением, как seed. Порт отдаёт сырой результат,
а что из него эталон — одно значение, все значения через пробел, id — решает генератор.

Экземпляр восстанавливается по seed при проверке ответа, поэтому любая реализация обязана давать
тот же результат байт-в-байт: вывод `print` с его `sep` и `end`, строки в порядке базы. Проверка —
снимок банка `tests/test_bank_snapshot.py` с новой реализацией.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

Row = tuple[Any, ...]
Rows = Sequence[Row]
# Таблица по имени: столбцы и строки.
Schema = Mapping[str, tuple[Sequence[str], Rows]]


class CodeRunner(Protocol):
    def python(self, code: str) -> str:
        """Консольный вывод листинга — всё, что напечатал `print`, как есть."""
        ...

    def sql(self, schema: Schema, query: str) -> list[Row]:
        """Все строки результата запроса к пустой базе, в которой созданы и заполнены таблицы
        `schema`."""
        ...
