"""Сценарии профиля компании работодателя: прочитать и заполнить или изменить."""

import uuid

from app.domain.company import Company, CompanyForm
from app.domain.errors import UnknownIndustry
from app.usecase.interface import CatalogRepository, Clock, CompanyRepository, UnitOfWork


class Companies:
    def __init__(
        self,
        uow: UnitOfWork,
        companies: CompanyRepository,
        catalog: CatalogRepository,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._companies = companies
        self._catalog = catalog
        self._clock = clock

    def get(self, user_id: uuid.UUID) -> Company | None:
        """`None` — профиль ещё не заполнен."""
        with self._uow:
            return self._companies.get(user_id)

    def save(self, user_id: uuid.UUID, form: CompanyForm) -> Company:
        """Сфера деятельности — из справочника сфер бизнеса, иначе `UnknownIndustry`."""
        with self._uow:
            if self._catalog.industry(form.industry) is None:
                raise UnknownIndustry()
            self._companies.save(user_id, form, self._clock.now())
            company = self._companies.get(user_id)
            assert company is not None, "профиль только что сохранён"
            return company
