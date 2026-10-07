"""Контракт порта единицы работы (`app.usecase.interface.UnitOfWork`) — один на обе реализации.

Postgres и in-memory проверяются одними и теми же тестами: записанное в успешном блоке видно
после него, в блоке с исключением — нет, а само исключение доходит до вызывающего.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import UnitOfWork


@dataclass
class Harness:
    """Реализация порта и способ записать и прочитать значение в её хранилище."""

    new: Callable[[], UnitOfWork]
    write: Callable[[UnitOfWork, str], None]
    read: Callable[[], set[str]]


def _postgres(engine: Engine) -> Iterator[Harness]:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE uow_probe (value text NOT NULL)"))

    def write(uow: UnitOfWork, value: str) -> None:
        assert isinstance(uow, SqlUnitOfWork)
        uow.session.execute(text("INSERT INTO uow_probe VALUES (:v)"), {"v": value})

    def read() -> set[str]:
        with engine.connect() as conn:
            return set(conn.scalars(text("SELECT value FROM uow_probe")))

    opened: list[SqlUnitOfWork] = []

    def new() -> UnitOfWork:
        opened.append(SqlUnitOfWork(Session(engine)))
        return opened[-1]

    try:
        yield Harness(new, write, read)
    finally:
        for uow in opened:
            uow.close()
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE uow_probe"))


def _memory() -> Iterator[Harness]:
    store = MemoryStore()

    def write(uow: UnitOfWork, value: str) -> None:
        assert isinstance(uow, MemoryUnitOfWork)
        uow.store.collection("probe")[value] = value

    def read() -> set[str]:
        return set(store.collection("probe").values())

    yield Harness(lambda: MemoryUnitOfWork(store), write, read)


@pytest.fixture(params=["postgres", "memory"])
def harness(request: pytest.FixtureRequest) -> Iterator[Harness]:
    if request.param == "postgres":
        yield from _postgres(request.getfixturevalue("db_engine"))
    else:
        yield from _memory()


class Boom(Exception):
    pass


def test_written_in_successful_block_is_visible_after(harness: Harness) -> None:
    uow = harness.new()
    with uow:
        harness.write(uow, "kept")

    assert harness.read() == {"kept"}


def test_written_in_failed_block_is_rolled_back_and_error_propagates(harness: Harness) -> None:
    uow = harness.new()
    error = Boom()

    with pytest.raises(Boom) as raised, uow:
        harness.write(uow, "lost")
        raise error

    assert raised.value is error
    assert harness.read() == set()


def test_each_block_is_its_own_transaction(harness: Harness) -> None:
    uow = harness.new()
    with uow:
        harness.write(uow, "first")
    with pytest.raises(Boom), uow:
        harness.write(uow, "second")
        raise Boom()
    with uow:
        harness.write(uow, "third")

    assert harness.read() == {"first", "third"}


def test_nested_block_is_refused(harness: Harness) -> None:
    uow = harness.new()

    with uow, pytest.raises(RuntimeError):
        uow.__enter__()
