from datetime import date

import pytest

from app.adapter.brand.mail_templates import BrandMailTemplates
from app.adapter.brand.words import Words
from app.domain.catalog import CatalogRef
from app.domain.locale import Locale

LINK = "http://front.test/verify-email?token=abc<&>"


@pytest.mark.parametrize(("locale", "subject"), [("ru", "Подтвердите"), ("en", "Confirm")])
def test_verification_mail_speaks_the_locale(locale: Locale, subject: str) -> None:
    mail = BrandMailTemplates().verification("anna@example.com", LINK, 24, locale)

    assert mail.subject.startswith(subject)
    assert LINK in mail.text
    assert mail.html is not None
    assert "abc&lt;&amp;&gt;" in mail.html
    assert "abc<&>" not in mail.html


def test_catalog_names_follow_the_locale_and_fall_back_to_backend_name() -> None:
    topic = CatalogRef("devops.linux", "Linux и сети")
    unknown = CatalogRef("devops.unknown", "Неизвестная тема")

    assert Words("en").catalog("topic", topic) != topic.name
    assert Words("ru").catalog("grade", "intern") == "Стажёр"
    assert Words("en").catalog("topic", unknown) == unknown.name


@pytest.mark.parametrize(
    ("locale", "count", "words"),
    [
        ("ru", 1, "1 год"),
        ("ru", 3, "3 года"),
        ("ru", 11, "11 лет"),
        ("en", 1, "1 year"),
        ("en", 4, "4 years"),
    ],
)
def test_years_are_pluralised_per_locale(locale: Locale, count: int, words: str) -> None:
    assert Words(locale).years(count) == words


def test_dates_follow_the_locale() -> None:
    day = date(2026, 10, 8)

    assert Words("ru").date(day) == "8 октября 2026"
    assert Words("en").date(day) == "October 8, 2026"
