"""Режим жюри через HTTP API (mechanics.md, §18): выключен по умолчанию и тогда ничего не
открывает, включённый заводит помеченные учётки, а реальные работодатели их не видят."""

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from app.adapter.clock import FrozenClock
from app.adapter.password import Argon2Passwords
from app.domain.account import Role
from app.repository.orm import User
from main import create_app
from settings import Mechanics, Settings
from tests.conftest import Outbox, Seeds, transaction

PATH = "/api/candidate/path"


@pytest.fixture
def demo_app(
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    clock: FrozenClock,
    seeds: Seeds,
    passwords: Argon2Passwords,
) -> Iterator[FastAPI]:
    app = create_app(
        settings.model_copy(update={"demo_mode": True}),
        mechanics,
        outbox,
        clock=clock,
        seeds=seeds,
        passwords=passwords,
    )
    yield app
    app.state.engine.dispose()


@pytest.fixture
def demo(demo_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(demo_app) as c:
        yield c


def users(engine: Engine) -> int:
    with transaction(engine) as session:
        return session.scalar(select(func.count()).select_from(User)) or 0


def test_demo_is_off_by_default_and_opens_nothing(client: TestClient, db_engine: Engine) -> None:
    assert client.get("/api/demo/status").json() == {"enabled": False}
    for path, body in (("employer", {}), ("candidate", {"specialization": "backend"})):
        response = client.post(f"/api/demo/{path}", json=body)
        assert response.status_code == 404
        assert response.json()["code"] == "demo_disabled"
    assert users(db_engine) == 0
    assert client.get("/api/auth/me").status_code == 401


def test_express_is_refused_to_a_regular_candidate(
    signed_in: Callable[[Role], TestClient],
) -> None:
    candidate = signed_in(Role.candidate)
    candidate.post(f"{PATH}/survey", json={"specialization": "qa"}).raise_for_status()
    response = candidate.post(f"{PATH}/attempts", json={"grade": "junior", "express": True})
    assert response.status_code == 409
    assert response.json()["code"] == "express_unavailable"


def test_demo_employer_has_company_needs_and_selections(demo: TestClient) -> None:
    assert demo.get("/api/demo/status").json() == {"enabled": True}
    entered = demo.post("/api/demo/employer")
    assert entered.status_code == 200
    assert entered.json()["role"] == "employer" and entered.json()["demo"]
    assert demo.get("/api/employer/company").json()["name"]
    assert len(demo.get("/api/employer/needs").json()) == 3
    assert demo.get("/api/employer/selections").json()
    # Повторный вход не дублирует ни учётку, ни потребности.
    demo.post("/api/demo/employer").raise_for_status()
    assert len(demo.get("/api/employer/needs").json()) == 3


def test_every_click_makes_a_fresh_candidate_in_an_express_test(demo: TestClient) -> None:
    first = demo.post("/api/demo/candidate", json={"specialization": "qa", "grade": "junior"})
    assert first.status_code == 201
    path = demo.get(PATH).json()
    assert path["stage"] == "test" and path["attempt"]["express"]
    assert path["attempt"]["max_items"] == 8
    assert demo.get(f"{PATH}/item").json()["max_items"] == 8
    second = demo.post("/api/demo/candidate", json={"specialization": "qa", "grade": "junior"})
    assert second.json()["id"] != first.json()["id"]


def test_demo_candidates_are_hidden_from_real_employers(
    demo: TestClient,
    signed_in: Callable[[Role], TestClient],
    db_engine: Engine,
) -> None:
    demo.post("/api/demo/candidate", json={"specialization": "qa", "grade": "junior"})
    demo.post("/api/demo/employer").raise_for_status()
    with transaction(db_engine) as session:
        assert session.scalar(select(func.count()).where(User.is_demo)) == 2
    seen = demo.post("/api/employer/candidates/search", json={})
    assert seen.status_code == 200
    assert seen.json()["total"] == 1
    real = signed_in(Role.employer).post("/api/employer/candidates/search", json={})
    assert real.status_code == 200
    assert real.json()["total"] == 0


def test_demo_answers_do_not_enter_calibration_or_response_time_samples(
    demo: TestClient,
    db_engine: Engine,
    mechanics: Mechanics,
) -> None:
    import uuid

    from app.repository.attempt import SqlAttemptRepository
    from app.repository.calibration import SqlCalibrationRepository
    from app.repository.orm.attempt import Presentation, TestAttempt

    demo.post(
        "/api/demo/candidate", json={"specialization": "qa", "grade": "junior"}
    ).raise_for_status()
    item = demo.get(f"{PATH}/item").json()
    with transaction(db_engine) as session:
        shown = session.get_one(Presentation, uuid.UUID(item["id"]))
        attempt = session.get_one(TestAttempt, shown.attempt_id)
        shown.correct = True
        shown.topic_theta_rest = 0.0
        shown.topic_theta_rest_sd = 0.5
        shown.response_time_ms = 1000
        attempt.finished_at = shown.shown_at
        session.flush()
        calibration = SqlCalibrationRepository(session)
        assert calibration.anchor_answers("qa", [shown.family_code], 100) == []
        assert calibration.rest_answers(shown.family_code) == []
        assert calibration.ready_responses(shown.family_code) == 0
        times = SqlAttemptRepository(
            session, mechanics.grade_thresholds, mechanics.grade_confidence
        ).response_times([shown.family_code], uuid.uuid4())
        assert times[shown.family_code] == []
