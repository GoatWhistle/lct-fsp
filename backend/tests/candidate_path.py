"""Путь кандидата к категории через HTTP API — шаги для тестов, которым нужна категория."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.assessment.bank import Family, get_family

PATH = "/api/candidate/path"
ITEM = f"{PATH}/item"
WRONG = "ответа нет"

Json = dict[str, Any]


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


def everything(_: Family) -> bool:
    return True


def nothing(_: Family) -> bool:
    return False


def pass_test(c: TestClient, db_engine: Engine, grade: str = "middle") -> Json:
    """Кандидат проходит опрос на QA и тест на `grade`, отвечая верно на всё, — категория есть."""
    take_survey(c)
    start(c, grade)
    path = answer_items(c, db_engine, everything)
    assert path["stage"] == "category", path
    return path
