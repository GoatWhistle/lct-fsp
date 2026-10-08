"""Резюме из PDF через HTTP API (mechanics.md, §16): черновик ничего не сохраняет, профиль
меняет только форма, ошибки — 4xx с понятным текстом, подсказка грейда по профилю."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.account import Role
from settings import Mechanics
from tests.resumes import IVANOVA, Hidden, resume_pdf, scanned_pdf
from tests.test_profile import PROFILE, profile_body

RESUME = f"{PROFILE}/resume"
GRADE_HINT = f"{PROFILE}/grade-hint"
PDF_HEADERS = {"Content-Type": "application/pdf"}

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


def upload(c: TestClient, pdf: bytes) -> Any:
    return c.post(RESUME, content=pdf, headers=PDF_HEADERS)


def draft_of(c: TestClient, pdf: bytes) -> Json:
    response = upload(c, pdf)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def test_draft_is_returned_and_nothing_is_saved(candidate: TestClient) -> None:
    draft = draft_of(candidate, resume_pdf(IVANOVA, "one_column"))

    assert draft["full_name"] == IVANOVA.full_name
    assert draft["contact_email"] == IVANOVA.email
    assert draft["contact_phone"] == IVANOVA.phone
    assert draft["telegram"] == IVANOVA.telegram
    assert {t["code"] for t in draft["stack"]} == IVANOVA.stack
    assert draft["experience_years"] == IVANOVA.experience_years
    assert set(draft["job_roles"]) == IVANOVA.roles
    assert draft["grade_hint"]["grade"]["code"] == "senior"
    # Стаж по периодам — неуверенный, экран его подсветит.
    assert "experience_years" in draft["uncertain"]
    assert candidate.get(PROFILE).json() is None
    assert candidate.get(GRADE_HINT).json() is None


def test_draft_does_not_change_a_saved_profile(candidate: TestClient) -> None:
    saved = candidate.put(PROFILE, json=profile_body())
    assert saved.status_code == 200, saved.text

    draft_of(candidate, resume_pdf(IVANOVA, "two_columns"))

    assert candidate.get(PROFILE).json() == saved.json()


def test_confirmed_draft_is_saved_by_the_profile_form(candidate: TestClient) -> None:
    draft = draft_of(candidate, resume_pdf(IVANOVA, "table"))
    body = profile_body(
        full_name=draft["full_name"],
        contact_email=draft["contact_email"],
        contact_phone=draft["contact_phone"],
        telegram=draft["telegram"],
        stack=[t["code"] for t in draft["stack"]],
        job_roles=draft["job_roles"],
        experience_years=draft["experience_years"],
        soft_skills=draft["soft_skills"],
    )

    saved = candidate.put(PROFILE, json=body)

    assert saved.status_code == 200, saved.text
    assert {t["code"] for t in saved.json()["stack"]} == IVANOVA.stack
    hint = candidate.get(GRADE_HINT).json()
    assert hint["grade"]["code"] == draft["grade_hint"]["grade"]["code"]


def test_hidden_text_does_not_reach_the_draft(candidate: TestClient) -> None:
    clean = draft_of(candidate, resume_pdf(IVANOVA, "one_column"))

    for hidden in Hidden:
        assert draft_of(candidate, resume_pdf(IVANOVA, "one_column", hidden=hidden)) == clean


@pytest.mark.parametrize(
    ("content", "status", "code"),
    [
        (b"%PDF-1.7\nbroken", 422, "resume_unreadable"),
        (b"PK\x03\x04 docx", 422, "resume_unreadable"),
        (b"", 422, "resume_unreadable"),
    ],
    ids=["broken", "not-pdf", "empty"],
)
def test_bad_file_is_a_clear_4xx(
    candidate: TestClient, content: bytes, status: int, code: str
) -> None:
    response = upload(candidate, content)

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["message"]


def test_scan_is_a_clear_4xx(candidate: TestClient) -> None:
    response = upload(candidate, scanned_pdf())

    assert response.status_code == 422
    assert response.json()["code"] == "resume_without_text"
    assert "скан" in response.json()["message"]


def test_file_over_the_limit(candidate: TestClient, mechanics: Mechanics) -> None:
    pdf = resume_pdf(IVANOVA, "one_column")
    padded = pdf + b"\n%" + b"0" * (mechanics.resume_max_bytes - len(pdf))

    response = upload(candidate, padded)

    assert response.status_code == 413
    assert response.json()["code"] == "resume_too_large"


def test_only_the_candidate_role_uploads_and_only_for_itself(
    signed_in: SignIn, client: TestClient
) -> None:
    owner = signed_in(Role.candidate)
    other = signed_in(Role.candidate)
    employer = signed_in(Role.employer)
    saved = owner.put(PROFILE, json=profile_body()).json()
    pdf = resume_pdf(IVANOVA, "one_column")

    assert upload(employer, pdf).status_code == 403
    assert employer.get(GRADE_HINT).status_code == 403
    assert upload(client, pdf).status_code == 401
    draft_of(other, pdf)

    assert owner.get(PROFILE).json() == saved
    assert other.get(PROFILE).json() is None


def test_grade_hint_from_the_saved_profile(candidate: TestClient) -> None:
    candidate.put(
        PROFILE, json=profile_body(experience_years=4, job_roles=["QA-инженер", "Тимлид"])
    ).raise_for_status()

    hint = candidate.get(GRADE_HINT).json()

    assert hint["grade"]["code"] == "middle"
    assert hint["by_experience"]["code"] == "middle"
    assert hint["by_roles"]["code"] == "senior"
