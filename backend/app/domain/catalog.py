"""Справочники: грейд, специализация, тема и ссылка на запись справочника.

Ключ каждой записи — стабильный `code`: на него ссылаются тест, профиль и подбор. Содержимое
справочников — `app/assessment/catalog.yaml`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogRef:
    """Ссылка на запись справочника с названием для показа."""

    code: str
    name: str


@dataclass(frozen=True)
class Grade:
    """Грейд — вторая половина категории; `rank` растёт от младшего к старшему."""

    code: str
    name: str
    rank: int


@dataclass(frozen=True)
class Topic:
    """Тема специализации — единица профиля навыков. Код темы начинается с кода
    специализации и точки."""

    code: str
    name: str
    specialization_code: str


@dataclass(frozen=True)
class Technology:
    """Технология стека; `topics` — коды тем, с которыми она связана, любых специализаций."""

    code: str
    name: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Specialization:
    """Специализация — IT-направление, «отрасль» в ТЗ; темы — в порядке справочника."""

    code: str
    name: str
    topics: tuple[Topic, ...] = ()
