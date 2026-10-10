"""Метка доверия компании через HTTP API: письмо на адрес домена сайта, подтверждение по ссылке и
метка в приглашении и вакансии у кандидата."""

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.domain.account import Role
from tests.candidate_path import grant_category
from tests.conftest import Outbox

COMPANY = "/api/employer/company"
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    c = signed_in(Role.employer)
    c.put(
        COMPANY,
        json={
            "name": "Акме",
            "industry": "fintech",
            "description": "Платёжный шлюз",
            "website": "https://www.acme.example.ru/jobs",
            "contact_email": "hr@acme.example.ru",
        },
    ).raise_for_status()
    return c


def token_from(outbox: Outbox, email: str) -> str:
    match = re.search(r"/verify-domain\?token=(\S+)", outbox.last_to(email).text)
    assert match, "в письме нет ссылки подтверждения домена"
    return match.group(1)


def confirm(employer: TestClient, outbox: Outbox, client: TestClient) -> None:
    response = employer.post(f"{COMPANY}/domain", json={"email": "HR@acme.example.ru"})
    assert response.status_code == 202, response.text
    confirmed = client.post(
        "/api/company-domain/confirm", json={"token": token_from(outbox, "hr@acme.example.ru")}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["domain_verified"] is True


def test_address_off_the_site_domain_is_rejected(employer: TestClient, outbox: Outbox) -> None:
    response = employer.post(f"{COMPANY}/domain", json={"email": "hr@gmail.com"})

    assert response.status_code == 422
    assert response.json()["code"] == "domain_email_mismatch"
    assert not [m for m in outbox.sent if "acme" in m.to or "gmail" in m.to]
    assert employer.get(COMPANY).json()["domain_verified"] is False


def test_company_confirms_its_domain_by_mail(
    employer: TestClient, outbox: Outbox, client: TestClient
) -> None:
    confirm(employer, outbox, client)

    company = employer.get(COMPANY).json()
    assert company["verified_domain"] == "acme.example.ru"
    assert company["domain_verified"] is True
    reused = client.post(
        "/api/company-domain/confirm", json={"token": token_from(outbox, "hr@acme.example.ru")}
    )
    assert reused.status_code == 400


def test_changing_the_site_drops_the_mark(
    employer: TestClient, outbox: Outbox, client: TestClient
) -> None:
    confirm(employer, outbox, client)
    body = employer.get(COMPANY).json()
    employer.put(
        COMPANY,
        json={
            "name": body["name"],
            "industry": "fintech",
            "description": body["description"],
            "website": "https://other.example.ru",
            "contact_email": body["contact_email"],
        },
    ).raise_for_status()

    assert employer.get(COMPANY).json()["domain_verified"] is False


def test_candidate_sees_the_mark_in_the_invitation_and_vacancy(
    employer: TestClient,
    outbox: Outbox,
    client: TestClient,
    signed_in: SignIn,
    db_engine: Engine,
) -> None:
    candidate = signed_in(Role.candidate)
    candidate_id = candidate.get("/api/auth/me").json()["id"]
    grant_category(db_engine, candidate_id)
    terms = {
        "candidate_id": candidate_id,
        "description": "QA в команду платежей",
        "salary_from": 200_000,
        "salary_to": 260_000,
        "contact": "Telegram @qa_hr",
    }
    employer.post("/api/employer/invitations", json=terms).raise_for_status()
    assert candidate.get("/api/candidate/invitations").json()[0]["company_domain_verified"] is False

    confirm(employer, outbox, client)

    assert candidate.get("/api/candidate/invitations").json()[0]["company_domain_verified"] is True
    employer.post(
        "/api/employer/vacancies",
        json={
            "title": "QA-инженер",
            "description": "Тестирование платёжного шлюза",
            "specialization": "qa",
            "grade": "middle",
            "work_formats": ["remote"],
            "salary_from": 200_000,
            "salary_to": 260_000,
        },
    ).raise_for_status()
    vacancies = candidate.get("/api/candidate/vacancies").json()
    assert [v["company_domain_verified"] for v in vacancies] == [True]
