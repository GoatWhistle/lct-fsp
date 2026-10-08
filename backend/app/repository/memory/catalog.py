"""Справочники в памяти — для сценарных тестов и стенда валидации: тот же `config/catalog.yaml`,
что у прода, доменными типами. Реализация порта `CatalogRepository`."""

from collections.abc import Collection

from app.domain.catalog import (
    Catalog,
    CatalogPart,
    CatalogPlan,
    Grade,
    Industry,
    Specialization,
    Technology,
    catalog_codes,
)
from app.repository.memory.unit_of_work import MemoryStore

_KEY = "catalog"


class MemoryCatalog:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def put(self, catalog: Catalog) -> None:
        self._store.collection(_KEY)[_KEY] = catalog

    def grades(self) -> list[Grade]:
        return sorted(self._catalog().grades, key=lambda g: g.rank)

    def grade(self, code: str) -> Grade | None:
        return next((g for g in self._catalog().grades if g.code == code), None)

    def industries(self) -> list[Industry]:
        return list(self._catalog().industries)

    def industry(self, code: str) -> Industry | None:
        return next((i for i in self._catalog().industries if i.code == code), None)

    def specializations(self) -> list[Specialization]:
        return list(self._catalog().specializations)

    def specialization(self, code: str) -> Specialization | None:
        return next((s for s in self._catalog().specializations if s.code == code), None)

    def technologies(self, codes: Collection[str] | None = None) -> list[Technology]:
        found = self._catalog().technologies
        if codes is not None:
            wanted = set(codes)
            found = tuple(t for t in found if t.code in wanted)
        return sorted(
            (Technology(t.code, t.name, tuple(sorted(t.topics))) for t in found),
            key=lambda t: t.name,
        )

    def codes(self) -> dict[CatalogPart, set[str]]:
        return catalog_codes(self._catalog())

    def apply(self, plan: CatalogPlan) -> None:
        self.put(plan.catalog)

    def _catalog(self) -> Catalog:
        catalog = self._store.collection(_KEY).get(_KEY)
        if catalog is None:
            return Catalog((), (), (), ())
        assert isinstance(catalog, Catalog)
        return catalog
