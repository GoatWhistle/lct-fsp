"""Тест по вакансии через HTTP API (mechanics.md, §6): превью у работодателя, тест в
приглашении, прохождение кандидатом и итог только для пригласившей компании."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.domain.account import Role
from tests.candidate_path import ITEM, PATH, WRONG, grant_category, with_company

NEEDS = "/api/employer/needs"
EMPLOYER = "/api/employer/invitations"
CANDIDATE = "/api/candidate/invitations"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return with_company(signed_in(Role.employer))


@pytest.fixture
def candidate(signed_in: SignIn, db_engine: Engine) -> tuple[TestClient, str]:
    """Кандидат с категорией QA · Middle."""
    c = signed_in(Role.candidate)
    candidate_id: str = c.get("/api/auth/me").json()["id"]
    grant_category(db_engine, candidate_id)
    return c, candidate_id


def create_need(c: TestClient, stack: list[str], specialization: str = "qa") -> str:
    response = c.post(
        NEEDS,
        json={
            "title": f"Вакансия {specialization}: {', '.join(stack)}",
            "specialization": specialization,
            "grade": "middle",
            "stack": stack,
            "work_format": "remote",
        },
    )
    assert response.status_code == 201, response.text
    need_id: str = response.json()["id"]
    return need_id


def preview(c: TestClient, need_id: str) -> Json:
    response = c.get(f"{NEEDS}/{need_id}/test")
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def invite(employer: TestClient, candidate_id: str, need_id: str | None) -> Any:
    return employer.post(
        EMPLOYER,
        json={
            "candidate_id": candidate_id,
            "description": "QA в команду платежей",
            "salary_from": 200_000,
            "salary_to": 260_000,
            "contact": "Telegram @qa_hr",
            "test_need_id": need_id,
        },
    )


def topic_codes(plan: Json) -> list[str]:
    return [t["topic"]["code"] for t in plan["topics"]]


def test_preview_shows_topics_items_and_examples(employer: TestClient) -> None:
    need_id = create_need(employer, ["playwright", "postgresql", "pytest"])

    body = preview(employer, need_id)

    plan = body["plan"]
    assert plan["items"] == sum(t["items"] for t in plan["topics"])
    assert set(topic_codes(plan)) == {"qa.automation", "qa.databases"}
    assert {e["topic"]["code"] for e in body["examples"]} == set(topic_codes(plan))
    assert all(e["prompt"] for e in body["examples"])
    assert all("answer" not in e for e in body["examples"])


def test_different_stack_gives_different_topics(employer: TestClient) -> None:
    databases = preview(employer, create_need(employer, ["postgresql", "mysql"]))
    automation = preview(employer, create_need(employer, ["playwright", "selenium"]))

    assert topic_codes(databases["plan"]) != topic_codes(automation["plan"])


def test_two_previews_give_different_instances_of_the_same_difficulty(
    employer: TestClient,
) -> None:
    need_id = create_need(employer, ["playwright", "postgresql", "pytest"])

    first, second = preview(employer, need_id), preview(employer, need_id)

    assert first["plan"] == second["plan"]
    # Семейство — по сложности около требуемого уровня: одно и то же, экземпляр — новый.
    assert [e["family_code"] for e in first["examples"]] == [
        e["family_code"] for e in second["examples"]
    ]
    shown = [(e["prompt"], e["code"], e["options"]) for e in first["examples"]]
    again = [(e["prompt"], e["code"], e["options"]) for e in second["examples"]]
    assert shown != again


def test_preview_of_someone_elses_need_is_not_found(
    employer: TestClient, signed_in: SignIn
) -> None:
    need_id = create_need(employer, ["postgresql"])
    other = with_company(signed_in(Role.employer), "Другая компания")

    assert other.get(f"{NEEDS}/{need_id}/test").status_code == 404


def test_candidate_takes_the_test_from_the_invitation(
    employer: TestClient, candidate: tuple[TestClient, str]
) -> None:
    c, candidate_id = candidate
    need_id = create_need(employer, ["playwright", "postgresql", "pytest"])
    before = c.get(PATH).json()

    response = invite(employer, candidate_id, need_id)
    assert response.status_code == 201, response.text
    invitation = response.json()
    test = invitation["vacancy_test"]
    assert test["status"] == "not_started"
    assert test["result"] is None
    planned = test["plan"]["items"]
    assert c.get(CANDIDATE).json()[0]["vacancy_test"]["plan"] == test["plan"]

    started = c.post(f"{CANDIDATE}/{invitation['id']}/test")
    assert started.status_code == 204, started.text
    path = c.get(PATH).json()
    assert path["vacancy_test"]["items"] == planned
    answered = 0
    while path["vacancy_test"] is not None:
        item = c.get(ITEM).json()
        assert item["vacancy_test"] is True
        assert item["max_items"] == planned
        assert item["topic"]["code"] in topic_codes(test["plan"])
        reply = c.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": WRONG})
        assert reply.status_code == 200, reply.text
        path = reply.json()
        answered += 1
    assert answered == planned

    # Категорию и профиль тест по вакансии не меняет.
    after = c.get(PATH).json()
    assert after["category"] == before["category"]
    assert after["stage"] == before["stage"]
    assert after["profile"]["topics"] == before["profile"]["topics"]

    seen = employer.get(f"{EMPLOYER}/{invitation['id']}").json()["vacancy_test"]
    assert seen["status"] == "finished"
    assert seen["answered"] == planned
    result = seen["result"]
    assert 0 <= result["match"] <= 1
    assert sum(t["answered"] for t in result["topics"]) == planned
    assert all(t["correct"] == 0 for t in result["topics"])

    mine = c.get(CANDIDATE).json()[0]["vacancy_test"]
    assert mine["status"] == "finished"
    assert mine["result"] is None

    again = c.post(f"{CANDIDATE}/{invitation['id']}/test")
    assert again.status_code == 409
    assert again.json()["code"] == "vacancy_test_taken"


def test_invitation_without_test_has_nothing_to_start(
    employer: TestClient, candidate: tuple[TestClient, str]
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id, None).json()

    assert invitation["vacancy_test"] is None
    response = c.post(f"{CANDIDATE}/{invitation['id']}/test")
    assert response.status_code == 404
    assert response.json()["code"] == "vacancy_test_not_found"


def test_test_of_another_specialization_is_not_attached(
    employer: TestClient, candidate: tuple[TestClient, str]
) -> None:
    _, candidate_id = candidate
    need_id = create_need(employer, ["kafka"], specialization="backend")

    response = invite(employer, candidate_id, need_id)

    assert response.status_code == 409
    assert response.json()["code"] == "vacancy_test_specialization_mismatch"


def test_declined_invitation_closes_the_test(
    employer: TestClient, candidate: tuple[TestClient, str]
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id, create_need(employer, ["postgresql"])).json()
    assert c.post(f"{CANDIDATE}/{invitation['id']}/decline").status_code == 200

    response = c.post(f"{CANDIDATE}/{invitation['id']}/test")

    assert response.status_code == 409
    assert response.json()["code"] == "vacancy_test_closed"
