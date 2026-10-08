"""Сценарии справочников: чтение для форм и синхронизация хранилища с файлом справочника.

Синхронизация идёт при каждом старте бэкенда и из командной строки; она идемпотентна —
повторный запуск справочник не дублирует. Правило синхронизации по кодам — в
`app.domain.catalog`.
"""

from dataclasses import dataclass

from app.domain import bank
from app.domain.catalog import Grade, Industry, Specialization, Technology, catalog_plan
from app.domain.errors import SpecializationNotFound
from app.usecase.interface import CatalogRepository, CatalogSource, UnitOfWork


@dataclass(frozen=True)
class SpecializationEntry:
    specialization: Specialization
    # Тест готов: в банке есть задания по всем темам. Без него специализацию нельзя выбрать.
    has_test: bool


class CatalogQueries:
    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository) -> None:
        self._uow = uow
        self._catalog = catalog

    def grades(self) -> list[Grade]:
        with self._uow:
            return self._catalog.grades()

    def industries(self) -> list[Industry]:
        with self._uow:
            return self._catalog.industries()

    def specializations(self) -> list[SpecializationEntry]:
        with self._uow:
            specializations = self._catalog.specializations()
        return [
            SpecializationEntry(s, bank.covers(t.code for t in s.topics)) for s in specializations
        ]

    def technologies(self, specialization: str | None = None) -> list[Technology]:
        """С `specialization` — только технологии, связанные с её темами, и только её темы;
        неизвестная специализация — `SpecializationNotFound`."""
        with self._uow:
            if specialization is None:
                return self._catalog.technologies()
            found = self._catalog.specialization(specialization)
            if found is None:
                raise SpecializationNotFound()
            technologies = self._catalog.technologies()
        own = {t.code for t in found.topics}
        result = []
        for tech in technologies:
            topics = tuple(t for t in tech.topics if t in own)
            if topics:
                result.append(Technology(tech.code, tech.name, topics))
        return result


class CatalogSync:
    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository, source: CatalogSource) -> None:
        self._uow = uow
        self._catalog = catalog
        self._source = source

    def run(self) -> None:
        """Хранилище — как источник: записи добавляются или обновляются по коду, коды, которых в
        источнике нет, снимаются."""
        catalog = self._source.load()
        with self._uow:
            self._catalog.apply(catalog_plan(self._catalog.codes(), catalog))
