"""Регулярные задания через HTTP API (mechanics.md, §11): кабинет работодателя, каталог
кандидата, проверка эталона и оценка автора, профиль навыков и свежесть."""

import math
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from settings import Mechanics
from tests.candidate_path import PATH, pass_test
from tests.conftest import PASSWORD, Seeds
from tests.test_company import company_body
from tests.test_visibility import PROFILE, SECRETS

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]

TASKS = "/api/employer/tasks"
CATALOG = "/api/candidate/tasks"
YEAR = timedelta(days=365.25)


def task_body(**changes: Any) -> Json:
    body: Json = {
        "specialization": "qa",
        "grade": "middle",
        "kind": "reference",
        "prompt": "Сколько строк вернёт SELECT count(*) FROM t, если в t 42 строки?",
        "topics": ["qa.databases"],
        "reference_answer": "1",
    }
    return body | changes


def open_body(**changes: Any) -> Json:
    return (
        task_body(
            kind="open",
            prompt="Как бы вы проверили идемпотентность POST /payments?",
            topics=["qa.api"],
            reference_answer=None,
        )
        | changes
    )


def create(c: TestClient, body: Json | None = None) -> Json:
    response = c.post(TASKS, json=body or task_body())
    assert response.status_code == 201, response.text
    created: Json = response.json()
    return created


def answer(c: TestClient, task_id: str, response: str) -> Json:
    answered = c.post(f"{CATALOG}/{task_id}/answer", json={"response": response})
    assert answered.status_code == 200, answered.text
    body: Json = answered.json()
    return body


def later(clock: FrozenClock, delta: timedelta, *clients: TestClient) -> None:
    """Сдвиг часов: сессия за это время истекает — клиенты входят заново."""
    emails = [c.get("/api/auth/me").json()["email"] for c in clients]
    clock.shift(delta)
    for c, email in zip(clients, emails, strict=True):
        c.post("/api/auth/login", json={"email": email, "password": PASSWORD}).raise_for_status()


def profile(c: TestClient) -> dict[str, Json]:
    """Профиль навыков кандидата на «сейчас»: общий уровень и темы."""
    body = c.get(PATH).json()["profile"]
    return {"overall": body["overall"]} | {t["topic"]["code"]: t["level"] for t in body["topics"]}


@pytest.fixture
def author(signed_in: SignIn) -> TestClient:
    c = signed_in(Role.employer)
    c.put("/api/employer/company", json=company_body()).raise_for_status()
    return c


@pytest.fixture
def stranger(signed_in: SignIn) -> TestClient:
    c = signed_in(Role.employer)
    c.put("/api/employer/company", json=company_body(name="Другая")).raise_for_status()
    return c


@pytest.fixture
def candidate(signed_in: SignIn, seeds: Seeds) -> TestClient:
    """Кандидат QA с категорией по тесту и заполненным профилем."""
    c = signed_in(Role.candidate)
    c.put("/api/candidate/profile", json=PROFILE).raise_for_status()
    pass_test(c, seeds)
    return c


# Задание: форма и жизненный цикл.


def test_employer_without_company_cannot_publish(signed_in: SignIn) -> None:
    c = signed_in(Role.employer)

    response = c.post(TASKS, json=task_body())

    assert response.status_code == 409
    assert response.json()["code"] == "company_required"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"topics": []}, "task_topics_count"),
        (
            {"topics": ["qa.theory", "qa.api", "qa.automation", "qa.databases"]},
            "task_topics_count",
        ),
        ({"topics": ["qa.api", "devops.linux"]}, "task_topic_not_in_specialization"),
        ({"reference_answer": None}, "reference_answer_mismatch"),
        ({"kind": "open"}, "reference_answer_mismatch"),
        ({"grade": "архимаг"}, "unknown_grade"),
    ],
)
def test_task_form_rules(author: TestClient, changes: Json, code: str) -> None:
    response = author.post(TASKS, json=task_body(**changes))

    assert response.status_code == 422, response.text
    assert response.json()["code"] == code


def test_author_lists_and_edits_own_task_until_first_answer(
    author: TestClient, stranger: TestClient, candidate: TestClient
) -> None:
    task = create(author)
    assert task["editable"] is True
    assert task["reference_answer"] == "1"

    edited = author.put(f"{TASKS}/{task['id']}", json=task_body(topics=["qa.api", "qa.theory"]))
    assert edited.status_code == 200, edited.text
    assert [t["code"] for t in edited.json()["topics"]] == ["qa.api", "qa.theory"]
    assert stranger.put(f"{TASKS}/{task['id']}", json=task_body()).status_code == 404
    assert [t["id"] for t in author.get(TASKS).json()] == [task["id"]]
    assert stranger.get(TASKS).json() == []

    answer(candidate, task["id"], "1")

    locked = author.put(f"{TASKS}/{task['id']}", json=task_body())
    assert locked.status_code == 409
    assert locked.json()["code"] == "task_locked"
    (listed,) = author.get(TASKS).json()
    assert (listed["answers"], listed["editable"]) == (1, False)


# Каталог кандидата.


def test_catalog_only_for_candidate_with_category(
    author: TestClient, signed_in: SignIn, candidate: TestClient
) -> None:
    junior = create(author, task_body(grade="junior"))
    senior = create(author, task_body(grade="senior"))
    create(author, task_body(specialization="devops", topics=["devops.linux"]))
    newcomer = signed_in(Role.candidate)

    refused = newcomer.get(CATALOG)
    catalog = candidate.get(CATALOG)

    assert refused.status_code == 409
    assert refused.json()["code"] == "category_required"
    assert catalog.status_code == 200
    assert {t["id"] for t in catalog.json()} == {junior["id"], senior["id"]}
    assert all("reference_answer" not in t for t in catalog.json())


def test_catalog_filters_and_order(
    author: TestClient, candidate: TestClient, clock: FrozenClock, signed_in: SignIn, seeds: Seeds
) -> None:
    first = create(author, task_body(grade="junior"))
    clock.shift(timedelta(minutes=1))
    second = create(author, task_body(topics=["qa.api"]))
    clock.shift(timedelta(minutes=1))
    third = create(author, task_body(grade="junior", topics=["qa.api", "qa.theory"]))
    other = signed_in(Role.candidate)
    pass_test(other, seeds)
    answer(other, third["id"], "1")

    def ids(query: str = "") -> list[str]:
        return [t["id"] for t in candidate.get(f"{CATALOG}{query}").json()]

    # Меньше ответов — выше, при равенстве — новые выше.
    assert ids() == [second["id"], first["id"], third["id"]]
    assert ids("?grade=junior") == [first["id"], third["id"]]
    assert ids("?topic=qa.api") == [second["id"], third["id"]]
    assert ids("?grade=junior&topic=qa.theory") == [third["id"]]


def test_one_answer_per_task(author: TestClient, candidate: TestClient) -> None:
    task = create(author)
    answer(candidate, task["id"], "1")

    again = candidate.post(f"{CATALOG}/{task['id']}/answer", json={"response": "1"})

    assert again.status_code == 409
    assert again.json()["code"] == "task_already_answered"
    listed = {t["id"]: t["answered"] for t in candidate.get(CATALOG).json()}
    assert listed == {task["id"]: True}


def test_withdrawn_task_leaves_catalog_but_keeps_profile(
    author: TestClient, candidate: TestClient
) -> None:
    task = create(author)
    answer(candidate, task["id"], "1")
    answered = profile(candidate)

    withdrawn = author.post(f"{TASKS}/{task['id']}/withdraw")

    assert withdrawn.status_code == 200
    assert withdrawn.json()["withdrawn_at"] is not None
    assert candidate.get(CATALOG).json() == []
    gone = candidate.post(f"{CATALOG}/{task['id']}/answer", json={"response": "1"})
    assert gone.status_code == 404
    assert profile(candidate) == answered
    assert [a["task"]["id"] for a in candidate.get(f"{CATALOG}/answers").json()] == [task["id"]]


# Проверка и оценка.


def test_reference_answer_narrows_task_topic_without_verdict(
    author: TestClient, candidate: TestClient
) -> None:
    task = create(author)
    before = profile(candidate)

    body = answer(candidate, task["id"], " 1 ")

    after = profile(candidate)
    assert body["status"] == "accepted"
    assert "correct" not in body and "rubric" not in body
    assert after["qa.databases"]["theta_sd"] < before["qa.databases"]["theta_sd"]
    assert after["qa.databases"]["theta"] > before["qa.databases"]["theta"]
    own = candidate.get(f"{CATALOG}/answers").json()
    assert [a["status"] for a in own] == ["accepted"]
    assert "correct" not in own[0]


def test_open_answer_counts_only_after_author_grade(
    author: TestClient, stranger: TestClient, candidate: TestClient
) -> None:
    task = create(author, open_body())
    before = profile(candidate)

    body = answer(candidate, task["id"], "Повторю запрос с тем же ключом и сверю списания")

    assert body["status"] == "awaiting_review"
    assert profile(candidate) == before
    (pending,) = author.get(f"{TASKS}/{task['id']}/answers").json()
    grade_path = f"{TASKS}/{task['id']}/answers/{pending['id']}/grade"
    assert stranger.post(grade_path, json={"rubric": 3}).status_code == 404
    assert author.post(grade_path, json={"rubric": 4}).status_code == 422

    graded = author.post(grade_path, json={"rubric": 3})

    assert graded.status_code == 200, graded.text
    assert graded.json()["rubric"] == 3
    after = profile(candidate)
    gains = {
        topic: before[topic]["theta_sd"] - after[topic]["theta_sd"]
        for topic in before
        if topic != "overall"
    }
    assert max(gains, key=lambda t: gains[t]) == "qa.api"
    assert after["qa.api"]["theta"] > before["qa.api"]["theta"]
    again = author.post(grade_path, json={"rubric": 1})
    assert again.status_code == 409
    assert again.json()["code"] == "answer_already_graded"
    assert [a["status"] for a in candidate.get(f"{CATALOG}/answers").json()] == ["reviewed"]


def test_reference_answer_is_not_graded_by_author(
    author: TestClient, candidate: TestClient
) -> None:
    task = create(author)
    answer(candidate, task["id"], "2")
    (checked,) = author.get(f"{TASKS}/{task['id']}/answers").json()

    response = author.post(
        f"{TASKS}/{task['id']}/answers/{checked['id']}/grade", json={"rubric": 3}
    )

    assert checked["correct"] is False
    assert response.status_code == 409
    assert response.json()["code"] == "task_not_gradable"


def test_author_sees_answer_anonymized_and_others_see_nothing(
    author: TestClient, stranger: TestClient, candidate: TestClient
) -> None:
    task = create(author, open_body())
    answer(candidate, task["id"], "Повторю запрос с тем же ключом")

    seen = author.get(f"{TASKS}/{task['id']}/answers")
    hidden = stranger.get(f"{TASKS}/{task['id']}/answers")

    assert seen.status_code == 200
    (item,) = seen.json()
    assert item["candidate"].startswith("Кандидат ")
    assert item["response"] == "Повторю запрос с тем же ключом"
    assert {name for name, marker in SECRETS.items() if marker in seen.text} == set()
    candidate_id = candidate.get("/api/auth/me").json()["id"]
    assert candidate_id not in seen.text
    assert hidden.status_code == 404
    assert "Повторю" not in hidden.text
    assert candidate.get(f"{TASKS}").status_code == 403


def test_answers_do_not_change_category(author: TestClient, candidate: TestClient) -> None:
    before = candidate.get(PATH).json()
    for grade in ("junior", "middle", "senior"):
        answer(candidate, create(author, task_body(grade=grade))["id"], "2")

    after = candidate.get(PATH).json()

    assert after["category"] == before["category"]
    assert after["result"] == before["result"]


# Свежесть.


def test_uncertainty_grows_without_signals_and_test_estimate_stays(
    candidate: TestClient, clock: FrozenClock, mechanics: Mechanics
) -> None:
    now = candidate.get(PATH).json()
    before = profile(candidate)

    later(clock, 2 * YEAR, candidate)
    shifted = candidate.get(PATH).json()
    after = profile(candidate)
    later(clock, 100 * YEAR, candidate)
    much_later = profile(candidate)

    decay = 2 * mechanics.profile_decay_sd_per_year**2
    prior_topic = mechanics.level_sd_inflation * math.hypot(
        mechanics.theta_prior_sd, mechanics.topic_deviation_sd
    )
    for topic in before:
        assert after[topic]["theta"] == pytest.approx(before[topic]["theta"])
        assert after[topic]["theta_sd"] ** 2 == pytest.approx(
            before[topic]["theta_sd"] ** 2 + decay
        )
        if topic != "overall":
            assert much_later[topic]["theta_sd"] <= prior_topic + 1e-9
    assert shifted["result"] == now["result"]
    assert shifted["category"] == now["category"]


def test_stale_mark_in_selection_and_its_removal_by_task(
    author: TestClient, candidate: TestClient, clock: FrozenClock, mechanics: Mechanics
) -> None:
    need = author.post(
        "/api/employer/needs",
        json={
            "title": "QA",
            "specialization": "qa",
            "grade": "middle",
            "stack": [],
            "work_format": "remote",
        },
    )
    need.raise_for_status()
    selections = f"/api/employer/needs/{need.json()['id']}/selections"
    task = create(author)

    def entry() -> Json:
        response = author.post(selections)
        assert response.status_code == 201, response.text
        (only,) = response.json()["entries"]
        return dict(only)

    assert entry()["stale"] is False
    later(clock, timedelta(days=mechanics.profile_stale_days + 1), author, candidate)
    stale = entry()
    answer(candidate, task["id"], "1")
    fresh = entry()

    assert stale["stale"] is True
    assert fresh["stale"] is False
    topics = {t["topic"]["code"]: t for t in fresh["topics"]}
    assert topics["qa.databases"]["regular_task"] is True
    assert {code for code, t in topics.items() if t["regular_task"]} == {"qa.databases"}
