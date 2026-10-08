"""Профиль компании через HTTP API: кто приглашает кандидата."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.account import Role

COMPANY = "/api/employer/company"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return signed_in(Role.employer)


def company_body(**changes: Any) -> Json:
    body: Json = {
        "name": "  Платёжные решения  ",
        "industry": "fintech",
        "description": "Делаем платёжный шлюз для малого бизнеса",
        "website": "pay.example.ru",
        "contact_email": "HR@Pay.Example.ru",
        "contact_phone": "+7 495 000-00-00",
    }
    return body | changes


def test_company_is_empty_until_filled(employer: TestClient) -> None:
    response = employer.get(COMPANY)

    assert response.status_code == 200
    assert response.json() is None


def test_employer_fills_company_profile(employer: TestClient) -> None:
    response = employer.put(COMPANY, json=company_body())

    assert response.status_code == 200, response.text
    company = employer.get(COMPANY).json()
    assert company == response.json()
    assert company["name"] == "Платёжные решения"
    assert company["industry"] == {"code": "fintech", "name": "Финтех и банки"}
    assert company["description"] == "Делаем платёжный шлюз для малого бизнеса"
    assert company["website"] == "https://pay.example.ru"
    assert company["contact_email"] == "hr@pay.example.ru"
    assert company["contact_phone"] == "+7 495 000-00-00"


def test_employer_edits_company_profile(employer: TestClient) -> None:
    employer.put(COMPANY, json=company_body()).raise_for_status()

    response = employer.put(
        COMPANY,
        json=company_body(name="Платёжные решения 2", website="", contact_phone=None),
    )

    assert response.status_code == 200, response.text
    company = employer.get(COMPANY).json()
    assert (company["name"], company["website"], company["contact_phone"]) == (
        "Платёжные решения 2",
        None,
        None,
    )


def test_company_industry_comes_from_catalog(employer: TestClient) -> None:
    response = employer.put(COMPANY, json=company_body(industry="space"))

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_industry"
    assert employer.get(COMPANY).json() is None


def test_website_keeps_cyrillic_domain(employer: TestClient) -> None:
    response = employer.put(COMPANY, json=company_body(website="пример.рф"))

    assert response.status_code == 200, response.text
    assert response.json()["website"] == "https://пример.рф"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "   "},
        {"description": ""},
        {"contact_email": "не почта"},
        {"website": "http:/example.ru"},
        {"website": "mailto:hr@example.ru"},
    ],
)
def test_company_needs_name_description_email_and_valid_site(
    employer: TestClient, changes: Json
) -> None:
    response = employer.put(COMPANY, json=company_body(**changes))

    assert response.status_code == 422
    assert employer.get(COMPANY).json() is None


def test_each_employer_sees_only_own_company(signed_in: SignIn, employer: TestClient) -> None:
    employer.put(COMPANY, json=company_body()).raise_for_status()

    assert signed_in(Role.employer).get(COMPANY).json() is None


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_candidate_gets_403_on_company_api(signed_in: SignIn, method: str) -> None:
    response = signed_in(Role.candidate).request(method, COMPANY, json=company_body())

    assert response.status_code == 403
    assert response.json()["code"] == "wrong_role"
