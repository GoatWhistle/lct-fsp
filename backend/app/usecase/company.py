"""Сценарии профиля компании работодателя: прочитать и заполнить или изменить, подтвердить домен
сайта письмом на адрес этого домена — метка доверия для кандидата."""

import secrets
import uuid
from datetime import timedelta

from app.domain.company import (
    Company,
    CompanyForm,
    check_domain_email,
    check_domain_verification,
    domain_token_hash,
    issue_domain_verification,
)
from app.domain.errors import CompanyProfileRequired, UnknownIndustry
from app.domain.locale import DEFAULT_LOCALE, Locale
from app.usecase.account import VerificationLinks
from app.usecase.interface import (
    CatalogRepository,
    Clock,
    CompanyRepository,
    Mailer,
    MailTemplates,
    UnitOfWork,
)


class Companies:
    def __init__(
        self,
        uow: UnitOfWork,
        companies: CompanyRepository,
        catalog: CatalogRepository,
        clock: Clock,
        mailer: Mailer | None = None,
        templates: MailTemplates | None = None,
        links: VerificationLinks | None = None,
    ) -> None:
        self._uow = uow
        self._companies = companies
        self._catalog = catalog
        self._clock = clock
        self._mailer = mailer
        self._templates = templates
        self._links = links

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

    def request_domain_check(
        self, user_id: uuid.UUID, email: str, locale: Locale = DEFAULT_LOCALE
    ) -> None:
        """Письмо со ссылкой подтверждения на адрес домена сайта компании; адрес вне домена —
        `DomainEmailMismatch`, без сайта — `CompanyWebsiteRequired`. Новая ссылка гасит прежние."""
        assert self._mailer is not None and self._templates is not None
        assert self._links is not None
        with self._uow:
            company = self._companies.get(user_id)
            if company is None:
                raise CompanyProfileRequired()
            domain = check_domain_email(email, company.website)
            now = self._clock.now()
            token = secrets.token_urlsafe(32)
            ttl_hours = self._links.ttl_hours
            verification = issue_domain_verification(
                user_id, email, domain, token, now, timedelta(hours=ttl_hours)
            )
            self._companies.add_domain_verification(verification)
            link = f"{self._links.frontend_url}/verify-domain?token={token}"
            mail = self._templates.domain_verification(
                verification.email, link, ttl_hours, company.name, domain, locale
            )
        self._mailer.send(mail)

    def confirm_domain(self, token: str) -> Company:
        """Ссылка из письма: домен компании подтверждён. Неизвестная ссылка — `TokenInvalid`,
        истёкшая — `TokenExpired`."""
        with self._uow:
            now = self._clock.now()
            found = self._companies.domain_verification(domain_token_hash(token))
            verification = check_domain_verification(found, now)
            self._companies.mark_domain_verified(verification.user_id, verification.domain, now)
            company = self._companies.get(verification.user_id)
            assert company is not None
            return company

    def trusted(self, user_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Работодатели из `user_ids`, у которых домен сайта подтверждён."""
        with self._uow:
            return {
                user_id
                for user_id in user_ids
                if (company := self._companies.get(user_id)) is not None and company.domain_verified
            }
