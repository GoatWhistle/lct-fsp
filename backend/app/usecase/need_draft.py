"""Сценарий разбора потребности из свободного текста (mechanics.md, §12;
docs/adr/0002-text-understanding-port.md): текст → черновик «система поняла так» или честный ответ
«вне справочника».

Один и тот же для HTTP и чат-поиска: агент вызывает его инструментом `parse_need`, а подборку по
черновику строит тем же сценарием, что экран, — `Selections.build_draft`. Черновик ничего не
сохраняет: потребностью он становится после правки человеком, обычным заведением.
"""

from app.domain.catalog import Catalog
from app.domain.need_draft import (
    CheckedDraft,
    CheckedOutOfCatalog,
    NeedDraft,
    OutOfCatalog,
    checked,
    checked_out_of_catalog,
    cleaned,
)
from app.usecase.interface import CatalogRepository, TextUnderstanding, UnitOfWork


class NeedDrafts:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        understanding: TextUnderstanding,
        *,
        confident: float,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._understanding = understanding
        self._confident = confident

    def parse(self, text: str) -> CheckedDraft | CheckedOutOfCatalog:
        """Черновик в пределах справочника: что адаптер вывел за справочник, отброшено здесь.
        Ответ не того типа — пустой черновик: разбор не роняет экран, работодатель заполнит
        поля сам."""
        with self._uow:
            catalog = Catalog(
                grades=tuple(self._catalog.grades()),
                industries=tuple(self._catalog.industries()),
                specializations=tuple(self._catalog.specializations()),
                technologies=tuple(self._catalog.technologies()),
            )
        result = self._understanding.need(cleaned(text), catalog)
        if isinstance(result, OutOfCatalog):
            return checked_out_of_catalog(result, catalog)
        if not isinstance(result, NeedDraft):
            result = NeedDraft(None, None, None, (), None, None, None, None, {})
        return checked(result, catalog, confident=self._confident)
