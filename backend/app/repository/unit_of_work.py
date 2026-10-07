"""Единица работы над Postgres — реализация порта `UnitOfWork`."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session


class SqlUnitOfWork:
    """Одна сессия на запрос, транзакция заканчивается с блоком `with`. `commit` и `rollback`
    сессии в бэкенде — только здесь; точка сохранения (`begin_nested`) внутри блока откатывает
    лишь свою часть, и блок решает, что делать дальше.

    Транзакция начинается с первого обращения к базе, поэтому чтение перед блоком — например,
    текущего пользователя — входит в транзакцию блока; чтение после блока открывает новую, её
    закрывает следующий блок или `close`. Сессия живёт до `close`, а не до конца блока: объекты,
    загруженные в блоке, читаются и после него, пока сессия создана с `expire_on_commit=False`.
    Блокировки строк (`with_for_update`) держатся до конца блока.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._open = False

    def __enter__(self) -> Self:
        if self._open:
            raise RuntimeError("единица работы уже открыта")
        self._open = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._open = False
        if exc_type is not None:
            self.session.rollback()
            return
        try:
            self.session.commit()
        except BaseException:
            self.session.rollback()
            raise

    def close(self) -> None:
        self.session.close()
