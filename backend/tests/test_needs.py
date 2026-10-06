"""Потребность работодателя через HTTP API: форма, справочники, вилка, важность тем (§12)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.identity.models import Role

NEEDS = "/api/employer/needs"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return signed_in(Role.employer)


def need_body(**changes: Any) -> Json:
    body: Json = {
        "title": "Бэкенд-разработчик в команду платежей",
        "team_description": "Платёжный шлюз: приём платежей и сверка с банками",
        "specialization": "backend",
        "grade": "middle",
        "stack": ["python", "postgresql", "django", "kafka"],
        "work_format": "hybrid",
        "city": "Москва",
        "salary_from": 200_000,
        "salary_to": 280_000,
    }
    return body | changes


def create(c: TestClient, **changes: Any) -> Json:
    response = c.post(NEEDS, json=need_body(**changes))
    assert response.status_code == 201, response.text
    body: Json = response.json()
    return body


def importance(need: Json) -> dict[str, str]:
    return {t["topic"]["code"]: t["importance"] for t in need["topics"]}


def test_employer_creates_need_and_reads_it_back(employer: TestClient) -> None:
    created = create(employer)

    need = employer.get(f"{NEEDS}/{created['id']}").json()
    assert need == created
    assert need["title"] == "Бэкенд-разработчик в команду платежей"
    assert need["team_description"] == "Платёжный шлюз: приём платежей и сверка с банками"
    assert need["specialization"] == {"code": "backend", "name": "Бэкенд"}
    assert need["grade"] == {"code": "middle", "name": "Middle"}
    assert [t["code"] for t in need["stack"]] == ["django", "kafka", "postgresql", "python"]
    assert need["work_format"] == "hybrid"
    assert need["city"] == "Москва"
    assert (need["salary_from"], need["salary_to"]) == (200_000, 280_000)
    assert need["salary_basis"] == "gross"
    assert need["created_at"].endswith("Z") and need["updated_at"].endswith("Z")
    assert [n["id"] for n in employer.get(NEEDS).json()] == [created["id"]]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", NEEDS),
        ("POST", NEEDS),
        ("POST", f"{NEEDS}/topic-importance"),
        ("GET", f"{NEEDS}/{{id}}"),
        ("PUT", f"{NEEDS}/{{id}}"),
        ("DELETE", f"{NEEDS}/{{id}}"),
    ],
)
def test_candidate_gets_403_on_needs_api(
    signed_in: SignIn, employer: TestClient, method: str, path: str
) -> None:
    need = create(employer)
    candidate = signed_in(Role.candidate)

    response = candidate.request(method, path.format(id=need["id"]), json=need_body())

    assert response.status_code == 403
    assert response.json()["code"] == "wrong_role"
    assert employer.get(f"{NEEDS}/{need['id']}").json() == need


@pytest.mark.parametrize(
    ("salary_from", "salary_to"),
    [(0, 100_000), (-50_000, 100_000), (150_000, 100_000), (100_000, None), (None, 100_000)],
)
def test_salary_range_needs_both_bounds_above_zero_in_order(
    employer: TestClient, salary_from: int | None, salary_to: int | None
) -> None:
    response = employer.post(NEEDS, json=need_body(salary_from=salary_from, salary_to=salary_to))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_salary_range"
    assert employer.get(NEEDS).json() == []


@pytest.mark.parametrize("salary_from", [True, "150000", 150_000.5])
def test_salary_bound_is_whole_rubles(employer: TestClient, salary_from: object) -> None:
    response = employer.post(NEEDS, json=need_body(salary_from=salary_from))

    assert response.status_code == 422
    assert employer.get(NEEDS).json() == []


@pytest.mark.parametrize(("salary_from", "salary_to"), [(150_000, 150_000), (1, 2), (None, None)])
def test_salary_range_may_be_one_value_or_absent(
    employer: TestClient, salary_from: int | None, salary_to: int | None
) -> None:
    need = create(employer, salary_from=salary_from, salary_to=salary_to)

    assert (need["salary_from"], need["salary_to"]) == (salary_from, salary_to)


def test_salary_range_is_checked_on_update(employer: TestClient) -> None:
    need = create(employer)

    response = employer.put(
        f"{NEEDS}/{need['id']}", json=need_body(salary_from=300_000, salary_to=200_000)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_salary_range"
    assert employer.get(f"{NEEDS}/{need['id']}").json() == need


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"specialization": "gamedev"}, "unknown_specialization"),
        ({"grade": "lead"}, "unknown_grade"),
        ({"stack": ["python", "cobol"]}, "unknown_technology"),
        ({"topic_importance": {"qa.api": "key"}}, "topic_not_in_specialization"),
    ],
)
def test_specialization_grade_and_stack_come_from_catalog(
    employer: TestClient, changes: Json, code: str
) -> None:
    response = employer.post(NEEDS, json=need_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == code


def test_stack_takes_any_catalog_technology(employer: TestClient) -> None:
    need = create(employer, stack=["python", "docker", "python"])

    assert [t["code"] for t in need["stack"]] == ["docker", "python"]


@pytest.mark.parametrize("work_format", ["office", "hybrid"])
def test_city_is_required_for_office_and_hybrid(employer: TestClient, work_format: str) -> None:
    response = employer.post(NEEDS, json=need_body(work_format=work_format, city="  "))

    assert response.status_code == 422
    assert response.json()["code"] == "city_required"


def test_remote_need_goes_without_city(employer: TestClient) -> None:
    need = create(employer, work_format="remote", city=None)

    assert need["city"] is None


def test_employer_edits_need(employer: TestClient) -> None:
    need = create(employer)

    response = employer.put(
        f"{NEEDS}/{need['id']}",
        json=need_body(
            title="QA-инженер",
            specialization="qa",
            grade="junior",
            stack=["postman"],
            work_format="remote",
            city=None,
            salary_from=None,
            salary_to=None,
        ),
    )

    assert response.status_code == 200, response.text
    edited = employer.get(f"{NEEDS}/{need['id']}").json()
    assert edited == response.json()
    assert edited["title"] == "QA-инженер"
    assert (edited["specialization"]["code"], edited["grade"]["code"]) == ("qa", "junior")
    assert [t["code"] for t in edited["stack"]] == ["postman"]
    assert (edited["work_format"], edited["city"]) == ("remote", None)
    assert (edited["salary_from"], edited["salary_to"]) == (None, None)
    assert edited["created_at"] == need["created_at"]


def test_employer_deletes_need(employer: TestClient) -> None:
    need = create(employer)
    kept = create(employer, title="Второй бэкенд")

    response = employer.delete(f"{NEEDS}/{need['id']}")

    assert response.status_code == 204
    assert employer.get(f"{NEEDS}/{need['id']}").status_code == 404
    assert [n["id"] for n in employer.get(NEEDS).json()] == [kept["id"]]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_employer_does_not_reach_another_employers_need(
    signed_in: SignIn, employer: TestClient, method: str
) -> None:
    need = create(employer)
    other = signed_in(Role.employer)

    response = other.request(method, f"{NEEDS}/{need['id']}", json=need_body(title="Чужая"))

    assert response.status_code == 404
    assert response.json()["code"] == "need_not_found"
    assert other.get(NEEDS).json() == []
    assert employer.get(f"{NEEDS}/{need['id']}").json() == need


BACKEND_FROM_STACK = {
    "backend.programming": "important",
    "backend.algorithms": "nice",
    "backend.databases": "key",
    "backend.api": "important",
    "backend.concurrency": "nice",
    "backend.distributed": "important",
    "backend.testing": "nice",
    "backend.security": "nice",
}


def test_topic_importance_comes_from_stack(employer: TestClient) -> None:
    need = create(employer, stack=["python", "postgresql", "django", "kafka", "docker"])

    assert importance(need) == BACKEND_FROM_STACK
    assert not any(t["edited"] for t in need["topics"])
    databases = next(t for t in need["topics"] if t["topic"]["code"] == "backend.databases")
    assert databases["topic"]["name"] == "Базы данных и SQL"
    assert [t["name"] for t in databases["technologies"]] == ["Django", "PostgreSQL"]


def test_employer_edits_importance_and_stack_still_drives_the_rest(employer: TestClient) -> None:
    edits = {"backend.security": "key", "backend.databases": "nice"}
    need = create(employer, topic_importance=edits)
    assert importance(need) == BACKEND_FROM_STACK | edits
    assert {t["topic"]["code"] for t in need["topics"] if t["edited"]} == set(edits)

    response = employer.put(
        f"{NEEDS}/{need['id']}",
        json=need_body(stack=["python", "postgresql", "django"], topic_importance=edits),
    )

    assert response.status_code == 200, response.text
    assert importance(response.json()) == BACKEND_FROM_STACK | edits | {
        "backend.distributed": "nice"
    }


def test_preview_shows_importance_of_unsaved_need(employer: TestClient) -> None:
    edits = {"backend.security": "key"}
    need = create(employer, topic_importance=edits)

    response = employer.post(
        f"{NEEDS}/topic-importance",
        json={
            "specialization": "backend",
            "stack": need_body()["stack"],
            "topic_importance": edits,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == need["topics"]
