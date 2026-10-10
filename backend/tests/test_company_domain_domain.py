"""Метка доверия компании: домен сайта и адрес на нём — чистые правила."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.catalog import CatalogRef
from app.domain.company import (
    Company,
    check_domain_email,
    check_domain_verification,
    issue_domain_verification,
    site_domain,
)
from app.domain.errors import CompanyWebsiteRequired, DomainEmailMismatch, TokenExpired

T0 = datetime(2026, 10, 10, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("website", "domain"),
    [
        ("https://www.Acme.ru/careers", "acme.ru"),
        ("acme.ru", "acme.ru"),
        ("http://jobs.acme.ru:8080", "jobs.acme.ru"),
        ("", None),
        (None, None),
        ("localhost", None),
    ],
)
def test_site_domain(website: str | None, domain: str | None) -> None:
    assert site_domain(website) == domain


def test_email_on_site_domain_or_its_parent_is_accepted() -> None:
    assert check_domain_email("HR@acme.ru", "https://acme.ru") == "acme.ru"
    assert check_domain_email("hr@acme.ru", "https://careers.acme.ru") == "careers.acme.ru"


@pytest.mark.parametrize(
    "email", ["hr@gmail.com", "hr@notacme.ru", "hr@careers.acme.ru", "acme.ru"]
)
def test_email_off_site_domain_is_rejected(email: str) -> None:
    with pytest.raises(DomainEmailMismatch):
        check_domain_email(email, "https://acme.ru")


def test_company_without_website_cannot_confirm() -> None:
    with pytest.raises(CompanyWebsiteRequired):
        check_domain_email("hr@acme.ru", None)


def test_mark_holds_only_while_the_site_stays_on_the_domain() -> None:
    company = Company(
        name="Акме",
        industry=CatalogRef("fintech", "Финтех"),
        description="",
        website="https://acme.ru",
        contact_email="hr@acme.ru",
        contact_phone=None,
        updated_at=T0,
        verified_domain="acme.ru",
        domain_verified_at=T0,
    )
    assert company.domain_verified
    moved = Company(**{**company.__dict__, "website": "https://other.ru"})
    assert not moved.domain_verified


def test_link_expires() -> None:
    issued = issue_domain_verification(
        uuid.uuid4(), "hr@acme.ru", "acme.ru", "token", T0, timedelta(hours=24)
    )
    assert check_domain_verification(issued, T0 + timedelta(hours=1)) == issued
    with pytest.raises(TokenExpired):
        check_domain_verification(issued, T0 + timedelta(hours=24))
