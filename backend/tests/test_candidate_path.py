"""Путь кандидата к категории через HTTP API: опрос → грейд → тест → категория (§4)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.assessment.bank import Family, get_family
from app.identity.models import Role
from tests.conftest import PASSWORD

PATH = "/api/candidate/path"
ITEM = f"{PATH}/item"
WRONG = "ответа нет"
QA_TOPICS = 5

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


def take_survey(c: TestClient, specialization: str = "qa") -> Json:
    response = c.post(
        f"{PATH}/survey", json={"industry": "fintech", "specialization": specialization}
    )
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def start(c: TestClient, grade: str) -> Json:
    response = c.post(f"{PATH}/attempts", json={"grade": grade})
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def presented(db_engine: Engine, presentation_id: str) -> tuple[Family, int]:
    with db_engine.connect() as conn:
        family_code, seed = conn.execute(
            text("SELECT family_code, seed FROM presentations WHERE id = :id"),
            {"id": presentation_id},
        ).one()
    return get_family(family_code), seed


def answer_items(c: TestClient, db_engine: Engine, correct: Callable[[Family], bool]) -> Json:
    """Отвечает на задания до остановки попытки; `correct` решает, отвечать ли верно."""
    path: Json = c.get(PATH).json()
    while path["stage"] == "test":
        item = c.get(ITEM).json()
        assert "id" in item, (item, path)
        family, seed = presented(db_engine, item["id"])
        response = family.instance(seed).answer if correct(family) else WRONG
        answered = c.post(
            f"{ITEM}/answer", json={"presentation_id": item["id"], "response": response}
        )
        assert answered.status_code == 200, answered.text
        path = answered.json()
    return path


def category_rows(db_engine: Engine) -> list[tuple[str, str]]:
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT specialization_code, grade_code FROM candidate_categories")
        )
        return [(s, g) for s, g in rows]


def everything(_: Family) -> bool:
    return True


def nothing(_: Family) -> bool:
    return False


def test_new_candidate_starts_with_survey_and_has_no_category(
    candidate: TestClient, db_engine: Engine
) -> None:
    path = candidate.get(PATH).json()

    assert path["stage"] == "survey"
    assert path["category"] is None
    assert category_rows(db_engine) == []


def test_full_path_to_category(candidate: TestClient, db_engine: Engine) -> None:
    survey = take_survey(candidate)
    assert survey["stage"] == "grade"
    assert survey["survey"]["industry"]["code"] == "fintech"
    assert survey["survey"]["specialization"] == {"code": "qa", "name": "QA"}

    started = start(candidate, "middle")
    assert started["stage"] == "test"
    assert started["attempt"] == {"grade": "middle", "answered": 0, "total": 2 * QA_TOPICS}

    path = answer_items(candidate, db_engine, everything)

    assert path["stage"] == "category"
    assert path["category"]["specialization"]["code"] == "qa"
    assert path["category"]["grade"] == {"code": "middle", "name": "Middle"}
    result = path["result"]
    assert result["grade"] == "middle"
    probabilities = {p["grade"]: p["probability"] for p in result["grade_probabilities"]}
    assert list(probabilities) == ["intern", "junior", "middle", "senior"]
    assert probabilities["middle"] >= 0.8
    assert result["overall"]["theta_sd"] < 1.0
    assert category_rows(db_engine) == [("qa", "middle")]

    profile = path["profile"]
    assert len(profile["topics"]) == QA_TOPICS
    assert profile["topics"][0]["topic"]["code"] == "qa.theory"
    for topic in profile["topics"]:
        assert topic["level"]["theta"] > 0
        assert topic["level"]["band"]["high"] is not None
    # Профиль весит тест меньше, чем оценка теста: weight trust_weight_test < 1.
    assert profile["overall"]["theta_sd"] > result["overall"]["theta_sd"]


def test_item_carries_no_answer(candidate: TestClient, db_engine: Engine) -> None:
    take_survey(candidate, "backend")
    start(candidate, "junior")

    item = candidate.get(ITEM).json()

    assert set(item) == {"id", "number", "total", "topic", "prompt", "code", "options"}
    assert item["number"] == 1 and item["total"] == 16
    family, seed = presented(db_engine, item["id"])
    instance = family.instance(seed)
    assert item["prompt"] == instance.prompt
    assert item["code"] == instance.code

    answered = candidate.post(
        f"{ITEM}/answer", json={"presentation_id": item["id"], "response": instance.answer}
    )
    assert "correct" not in answered.text
    assert answered.json()["attempt"]["answered"] == 1


def test_presentation_is_recorded_with_server_response_time(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "junior")

    with time_machine.travel(datetime.now(UTC), tick=False) as clock:
        item = candidate.get(ITEM).json()
        clock.shift(timedelta(seconds=42.5))
        assert candidate.get(ITEM).json()["id"] == item["id"], "повторный показ — то же задание"
        candidate.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": "7"})

    with db_engine.connect() as conn:
        row = (
            conn.execute(text("SELECT * FROM presentations WHERE id = :id"), {"id": item["id"]})
            .mappings()
            .one()
        )
    assert row["response_time_ms"] == 42500
    assert row["response"] == "7"
    assert row["correct"] is not None
    assert row["family_code"].startswith(row["topic_code"])
    assert row["params"] and row["seed"] is not None
    assert row["discrimination"] == 1.2
    assert row["difficulty"] in (-1.0, 0.0)
    assert row["topic_theta_before"] == 0.0


def test_answer_to_stale_item_is_rejected(candidate: TestClient) -> None:
    take_survey(candidate)
    start(candidate, "junior")
    item = candidate.get(ITEM).json()
    candidate.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": "1"})

    again = candidate.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": "1"})

    assert again.status_code == 409
    assert again.json()["code"] == "item_not_current"


def test_failed_grade_offers_dotest_that_continues_the_estimate(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")

    offer = answer_items(candidate, db_engine, nothing)

    assert offer["stage"] == "offer"
    assert offer["offer_grade"] == "junior"
    assert offer["result"]["grade"] == "middle"
    assert category_rows(db_engine) == []
    wrong_grade = candidate.post(f"{PATH}/attempts", json={"grade": "middle"})
    assert wrong_grade.status_code == 409
    assert wrong_grade.json()["code"] == "grade_not_offered"

    dotest = start(candidate, "junior")

    # Задания junior уже показаны в попытке на middle — дотест добирает только стажёрские.
    assert dotest["attempt"] == {"grade": "junior", "answered": 0, "total": QA_TOPICS}
    item = candidate.get(ITEM).json()
    assert presented(db_engine, item["id"])[0].grade == "intern"


def test_path_order_does_not_depend_on_server_clock(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, db_engine, nothing)

    # Синхронизация отвела часы назад: дотест начат «раньше» первой попытки.
    with time_machine.travel(datetime.now(UTC) - timedelta(seconds=30)):
        dotest = start(candidate, "junior")

    assert dotest["stage"] == "test"
    assert candidate.get(PATH).json()["attempt"]["grade"] == "junior"


def test_dotest_below_is_skipped_when_confidence_is_already_there(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")

    path = answer_items(candidate, db_engine, lambda family: family.grade == "junior")

    assert path["stage"] == "category"
    assert path["category"]["grade"]["code"] == "junior"
    assert path["result"]["grade"] == "middle"
    assert category_rows(db_engine) == [("qa", "junior")]


def test_failed_cascade_leaves_no_category_until_retest_date(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, db_engine, nothing)
    start(candidate, "junior")

    path = answer_items(candidate, db_engine, nothing)

    assert path["stage"] == "no_category"
    assert path["category"] is None
    assert category_rows(db_engine) == []
    retest_after = datetime.fromisoformat(path["retest_after"])
    assert timedelta(days=29) < retest_after - datetime.now(UTC) <= timedelta(days=30)
    for blocked in (
        candidate.post(f"{PATH}/attempts", json={"grade": "intern"}),
        candidate.post(f"{PATH}/survey", json={"industry": "fintech", "specialization": "qa"}),
    ):
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "path_step_unavailable"

    email = candidate.get("/api/auth/me").json()["email"]
    with time_machine.travel(retest_after + timedelta(minutes=1)):
        # Вход за это время истёк — входим заново.
        candidate.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert candidate.get(PATH).json()["stage"] == "grade"


def test_failed_intern_leaves_no_category(candidate: TestClient, db_engine: Engine) -> None:
    take_survey(candidate)
    start(candidate, "intern")

    path = answer_items(candidate, db_engine, nothing)

    assert path["stage"] == "no_category"
    assert path["retest_after"] is not None
    assert path["result"]["overall"]["band"]["high"] in (None, "intern")


def test_path_cannot_be_skipped(candidate: TestClient) -> None:
    attempt = candidate.post(f"{PATH}/attempts", json={"grade": "junior"})
    assert attempt.status_code == 409
    assert attempt.json()["code"] == "path_step_unavailable"

    take_survey(candidate)
    item = candidate.get(ITEM)
    assert item.status_code == 409
    assert item.json()["code"] == "no_test_in_progress"


def test_survey_can_be_changed_before_the_test(candidate: TestClient) -> None:
    take_survey(candidate, "backend")

    path = take_survey(candidate, "qa")

    assert path["stage"] == "grade"
    assert path["survey"]["specialization"]["code"] == "qa"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"industry": "fintech", "specialization": "frontend"}, "specialization_without_test"),
        ({"industry": "fintech", "specialization": "astrology"}, "unknown_specialization"),
        ({"industry": "alchemy", "specialization": "qa"}, "unknown_industry"),
    ],
)
def test_survey_rejects_unknown_choices(candidate: TestClient, body: Json, code: str) -> None:
    response = candidate.post(f"{PATH}/survey", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == code


def test_unknown_grade_is_rejected(candidate: TestClient) -> None:
    take_survey(candidate)

    response = candidate.post(f"{PATH}/attempts", json={"grade": "guru"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_grade"


def test_employer_has_no_candidate_path(signed_in: SignIn) -> None:
    employer = signed_in(Role.employer)

    assert employer.get(PATH).status_code == 403
    assert employer.get(ITEM).status_code == 403


def test_unknown_presentation_is_not_current(candidate: TestClient) -> None:
    take_survey(candidate)
    start(candidate, "junior")
    candidate.get(ITEM)

    response = candidate.post(
        f"{ITEM}/answer", json={"presentation_id": str(uuid.uuid4()), "response": "1"}
    )

    assert response.status_code == 409
