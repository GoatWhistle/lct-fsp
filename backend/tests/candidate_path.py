"""Путь кандидата к категории через HTTP API — шаги для тестов, которым нужна категория."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert, select

from app.adapter.code_runner import InProcessCodeRunner
from app.domain.bank import Family, Instance, families_for_topics
from app.repository.orm import (
    CandidateCategory,
    SkillProfile,
    SkillProfileTopic,
    Survey,
    TestAttempt,
    Topic,
)
from tests.conftest import Seeds, transaction

PATH = "/api/candidate/path"
ITEM = f"{PATH}/item"
WRONG = "ответа нет"
RUNNER = InProcessCodeRunner()

Json = dict[str, Any]


def take_survey(c: TestClient, specialization: str = "qa") -> Json:
    response = c.post(f"{PATH}/survey", json={"specialization": specialization})
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def start(c: TestClient, grade: str) -> Json:
    response = c.post(f"{PATH}/attempts", json={"grade": grade})
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def presented(seeds: Seeds, item: Json) -> tuple[Family, int]:
    """Семейство и seed показанного задания — по seed, выданным тесту, а не из базы. Экземпляр
    берёт последний seed показа, поэтому поиск идёт от свежих seed; семейство — то, чей экземпляр
    совпал с заданием."""
    candidates = families_for_topics([item["topic"]["code"]])
    for seed in reversed(seeds.issued):
        found = [f for f in candidates if _shows(f.instance(seed, RUNNER), item)]
        if found:
            assert len(found) == 1, (item, [f.code for f in found])
            return found[0], seed
    raise AssertionError(f"задание не выведено ни из одного выданного seed: {item}")


def _shows(instance: Instance, item: Json) -> bool:
    return (instance.prompt, instance.code, list(instance.options)) == (
        item["prompt"],
        item["code"],
        item["options"],
    )


def answer_items(c: TestClient, seeds: Seeds, correct: Callable[[Family], bool]) -> Json:
    """Отвечает на задания до остановки попытки; `correct` решает, отвечать ли верно."""
    path: Json = c.get(PATH).json()
    while path["stage"] == "test":
        item = c.get(ITEM).json()
        assert "id" in item, (item, path)
        family, seed = presented(seeds, item)
        response = family.instance(seed, RUNNER).answer if correct(family) else WRONG
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


def pass_test(c: TestClient, seeds: Seeds, grade: str = "middle") -> Json:
    """Кандидат проходит опрос на QA и тест на `grade`, отвечая верно на всё, — категория есть."""
    take_survey(c)
    start(c, grade)
    path = answer_items(c, seeds, everything)
    assert path["stage"] == "category", path
    return path


def grant_category(db_engine: Engine, user_id: str) -> None:
    """Категория QA · Middle и профиль навыков — прямо в базу, без прохождения теста."""
    uid, survey, attempt, profile = uuid.UUID(user_id), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    with transaction(db_engine) as db:
        topics = db.scalars(select(Topic.code).where(Topic.specialization_code == "qa")).all()
        db.execute(
            insert(Survey),
            [
                {
                    "id": survey,
                    "user_id": uid,
                    "number": 1,
                    "specialization_code": "qa",
                    "created_at": now,
                }
            ],
        )
        db.execute(
            insert(TestAttempt),
            [
                {
                    "id": attempt,
                    "user_id": uid,
                    "number": 1,
                    "survey_id": survey,
                    "specialization_code": "qa",
                    "grade_code": "middle",
                    "started_at": now,
                }
            ],
        )
        db.execute(
            insert(CandidateCategory),
            [
                {
                    "user_id": uid,
                    "specialization_code": "qa",
                    "grade_code": "middle",
                    "attempt_id": attempt,
                    "assigned_at": now,
                }
            ],
        )
        db.execute(
            insert(SkillProfile),
            [
                {
                    "id": profile,
                    "user_id": uid,
                    "specialization_code": "qa",
                    "overall_theta": 0.5,
                    "overall_theta_sd": 0.4,
                    "observations": 20,
                    "last_signal_at": now,
                    "updated_at": now,
                }
            ],
        )
        db.execute(
            insert(SkillProfileTopic),
            [
                {"profile_id": profile, "topic_code": t, "theta": 0.5, "theta_sd": 0.4}
                for t in topics
            ],
        )


def with_company(employer: TestClient, name: str = "Платёжные решения") -> TestClient:
    """Работодатель с профилем компании — он может приглашать."""
    employer.put(
        "/api/employer/company",
        json={
            "name": name,
            "industry": "fintech",
            "description": "Платёжный шлюз",
            "contact_email": "hr@pay.example.ru",
        },
    ).raise_for_status()
    return employer
