"""Деньги на платформе — рубли в месяц до вычета НДФЛ (гросс), mechanics.md §14.

Конвенция одна на все суммы: ожидания кандидата и вилки работодателей сравниваются напрямую,
без пересчёта налога. Каждый ответ API с деньгами подписан полем `salary_basis`, интерфейс —
той же формулировкой. Приглашения и вакансии берут отсюда же.
"""

import enum
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, computed_field


class SalaryBasis(enum.StrEnum):
    """Как считается сумма: `gross` — до вычета НДФЛ."""

    gross = "gross"


SALARY_UNIT = "Рубли в месяц до вычета НДФЛ (гросс)"

Salary = Annotated[StrictInt, Field(le=1_000_000_000, description=SALARY_UNIT)]


class SalaryBasisOut(BaseModel):
    """Основа ответа с деньгами: пометка, гросс это или нетто, — всегда в ответе."""

    # Вычисляемое поле, а не поле со значением по умолчанию: в схеме ответа оно обязательное.
    @computed_field(description="Все суммы платформы — до вычета НДФЛ (`gross`)")  # type: ignore[prop-decorator]
    @property
    def salary_basis(self) -> SalaryBasis:
        return SalaryBasis.gross
