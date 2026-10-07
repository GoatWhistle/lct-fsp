"""Условия работы: формат и вилка зарплаты (mechanics.md, §12–14).

Деньги на платформе — рубли в месяц до вычета НДФЛ (гросс). Конвенция одна на все суммы:
ожидания кандидата и вилки работодателей сравниваются напрямую, без пересчёта налога.
"""

import enum
from dataclasses import dataclass

from app.domain.errors import InvalidSalaryRange


class WorkFormat(enum.StrEnum):
    office = "office"
    hybrid = "hybrid"
    remote = "remote"


class SalaryBasis(enum.StrEnum):
    """Как считается сумма: `gross` — до вычета НДФЛ."""

    gross = "gross"


@dataclass(frozen=True)
class SalaryRange:
    """Вилка «от–до»: обе границы больше нуля, «от» не больше «до»."""

    low: int
    high: int

    def __post_init__(self) -> None:
        if not 0 < self.low <= self.high:
            raise InvalidSalaryRange()

    @classmethod
    def optional(cls, low: int | None, high: int | None) -> "SalaryRange | None":
        """Необязательная вилка указывается целиком или не указывается вовсе."""
        if low is None and high is None:
            return None
        if low is None or high is None:
            raise InvalidSalaryRange()
        return cls(low, high)
