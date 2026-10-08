"""Обратная связь кандидату через HTTP API (mechanics.md, §15): только о себе, порог k по
компаниям, в ответе — ни работодателей, ни потребностей, ни подборок, ни других кандидатов."""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from settings import Mechanics
from tests.candidate_path import grant_category, with_company
from tests.test_selections import Seed, build, create_need, seed, user_id

FEEDBACK = "/api/candidate/feedback"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def me(signed_in: SignIn, db_engine: Engine) -> TestClient:
    """Кандидат QA · Middle: уровни тем 0,5 ± 0,4 — у порога грейда, есть что поднимать."""
    c = signed_in(Role.candidate)
    grant_category(db_engine, user_id(c))
    return c


def feedback(c: TestClient) -> Json:
    response = c.get(FEEDBACK)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def selections_by(signed_in: SignIn, companies: int) -> list[tuple[TestClient, Json]]:
    """`companies` работодателей с профилем компании — каждый строит подборку по своей
    потребности."""
    built = []
    for i in range(companies):
        employer = with_company(signed_in(Role.employer), name=f"Компания {i}")
        built.append((employer, build(employer, create_need(employer))))
    return built


def test_only_candidate_gets_feedback(
    signed_in: SignIn, new_client: Callable[[], TestClient]
) -> None:
    assert signed_in(Role.employer).get(FEEDBACK).status_code == 403
    assert new_client().get(FEEDBACK).status_code == 401


def test_without_selections_feedback_is_few_with_general_hint(me: TestClient) -> None:
    body = feedback(me)

    assert body["enough"] is False
    assert body["placement"] is None
    kinds = [h["action"]["kind"] for h in body["hints"]]
    assert kinds == ["topic_block", "link_fsp"]
    general, fsp = body["hints"]
    assert general["topic"]["code"].startswith("qa.")
    assert (general["gain"], general["scenario"], general["places"]) == (None, None, None)
    assert general["action"] == {"kind": "topic_block", "available": True, "available_at": None}
    assert (fsp["topic"], fsp["gain"]) == (None, None)


def test_topic_block_is_held_until_interval_after_start(
    me: TestClient, clock: FrozenClock, mechanics: Mechanics
) -> None:
    """Блок по теме подсказки начат — до конца интервала действие недоступно с датой, когда
    можно; блок по другой теме по-прежнему доступен."""
    (general,) = [h for h in feedback(me)["hints"] if h["action"]["kind"] == "topic_block"]
    topic = general["topic"]["code"]
    started = me.post("/api/candidate/path/topic-block", json={"topic": topic})
    assert started.status_code == 200, started.text

    (held,) = [h for h in feedback(me)["hints"] if h["action"]["kind"] == "topic_block"]
    allowed = clock.now() + timedelta(days=mechanics.topic_block_interval_days)
    assert held["topic"]["code"] == topic
    assert held["action"]["available"] is False
    assert datetime.fromisoformat(held["action"]["available_at"]) == allowed


def test_candidate_without_category_gets_only_fsp_hint(signed_in: SignIn) -> None:
    body = feedback(signed_in(Role.candidate))

    assert (body["enough"], body["placement"]) == (False, None)
    assert [h["action"]["kind"] for h in body["hints"]] == ["link_fsp"]


def test_below_k_companies_no_placement_at_k_there_is(
    me: TestClient, signed_in: SignIn, mechanics: Mechanics
) -> None:
    k = mechanics.feedback_min_companies
    built = selections_by(signed_in, k - 1)

    below = feedback(me)

    assert below["enough"] is False
    assert below["placement"] is None
    assert all(h["gain"] is None for h in below["hints"])

    built += selections_by(signed_in, 1)
    at = feedback(me)

    assert at["enough"] is True
    assert at["period_days"] == mechanics.feedback_period_days
    assert at["placement"] == {"selections": k, "median_position": 1.0, "exact_share": 1.0}
    topic_hints = [h for h in at["hints"] if h["topic"] is not None]
    assert 0 < len(topic_hints) <= mechanics.feedback_hints_max
    for hint in topic_hints:
        assert hint["gain"] >= mechanics.feedback_min_gain
        assert hint["scenario"] in ("narrow", "raise")
        assert hint["action"] == {"kind": "topic_block", "available": True, "available_at": None}


def test_many_selections_of_one_company_do_not_reach_k(
    me: TestClient, signed_in: SignIn, mechanics: Mechanics
) -> None:
    employer = with_company(signed_in(Role.employer))
    for _ in range(mechanics.feedback_min_companies + 1):
        build(employer, create_need(employer))

    body = feedback(me)

    assert body["enough"] is False
    assert body["placement"] is None


def test_response_reveals_no_employer_need_selection_or_other_candidate(
    me: TestClient, signed_in: SignIn, db_engine: Engine, mechanics: Mechanics
) -> None:
    others = seed(db_engine, [Seed(levels={"qa.api": (1.5, 0.3)}), Seed(grade="senior")])
    built = selections_by(signed_in, mechanics.feedback_min_companies)

    body = feedback(me)
    text = json.dumps(body, ensure_ascii=False)

    assert body["enough"] is True
    assert set(body) == {"period_days", "enough", "placement", "hints"}
    assert set(body["placement"]) == {"selections", "median_position", "exact_share"}
    assert all(set(h) == {"topic", "action", "scenario", "gain", "places"} for h in body["hints"])
    for employer, selection in built:
        hidden = [
            user_id(employer),
            selection["id"],
            selection["need"]["title"],
            *(e["candidate_id"] for e in selection["entries"]),
        ]
        hidden.remove(user_id(me))
        assert not [value for value in hidden if value in text]
    assert not [o for o in others if o in text]
    assert "Компания" not in text


def test_regular_task_on_topic_becomes_the_action(
    me: TestClient, signed_in: SignIn, mechanics: Mechanics
) -> None:
    author = with_company(signed_in(Role.employer))
    topics = ["qa.theory", "qa.api", "qa.automation", "qa.databases", "qa.performance"]
    for chunk in (topics[:3], topics[3:]):
        response = author.post(
            "/api/employer/tasks",
            json={
                "specialization": "qa",
                "grade": "middle",
                "kind": "reference",
                "prompt": "Сколько строк вернёт SELECT count(*) FROM t?",
                "topics": chunk,
                "reference_answer": "1",
            },
        )
        assert response.status_code == 201, response.text
    selections_by(signed_in, mechanics.feedback_min_companies)

    body = feedback(me)

    topic_hints = [h for h in body["hints"] if h["topic"] is not None]
    assert topic_hints
    assert {h["action"]["kind"] for h in topic_hints} == {"regular_task"}
    assert all(h["action"]["available"] for h in topic_hints)
