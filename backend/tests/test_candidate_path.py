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
from app.assessment.catalog import load_catalog
from app.config import Mechanics, Settings
from app.identity.models import Role
from app.main import create_app
from app.skills.irt import Observation, estimate
from app.skills.service import specialization_prior
from tests.candidate_path import (
    ITEM,
    PATH,
    answer_items,
    everything,
    nothing,
    presented,
    start,
    take_survey,
)
from tests.conftest import PASSWORD, Outbox

QA_TOPICS = [t.code for s in load_catalog().specializations if s.code == "qa" for t in s.topics]

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


def category_rows(db_engine: Engine) -> list[tuple[str, str]]:
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT specialization_code, grade_code FROM candidate_categories")
        )
        return [(s, g) for s, g in rows]


def shown_families(db_engine: Engine) -> set[str]:
    with db_engine.connect() as conn:
        return set(conn.scalars(text("SELECT family_code FROM presentations")))


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
    assert started["attempt"] == {"grade": "middle", "answered": 0, "max_items": 30}

    path = answer_items(candidate, db_engine, everything)

    assert path["stage"] == "category"
    assert path["category"]["specialization"]["code"] == "qa"
    assert path["category"]["grade"] == {"code": "middle", "name": "Middle"}
    result = path["result"]
    assert result["grade"] == "middle"
    probabilities = {p["grade"]: p["probability"] for p in result["grade_probabilities"]}
    assert list(probabilities) == ["intern", "junior", "middle", "senior"]
    assert probabilities["middle"] >= 0.8
    # Все ответы верны — P(уровень ≥ порог senior) выше порога подсказки.
    assert result["grade_up_hint"] == "senior"
    assert result["overall"]["theta_sd"] < 1.0
    assert category_rows(db_engine) == [("qa", "middle")]

    profile = path["profile"]
    assert len(profile["topics"]) == len(QA_TOPICS)
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

    assert set(item) == {"id", "number", "max_items", "topic", "prompt", "code", "options"}
    assert item["number"] == 1 and item["max_items"] == 30
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
    candidate: TestClient, db_engine: Engine, mechanics: Mechanics
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
    # Первый ответ на семейство — параметры ещё экспертные.
    grade = get_family(row["family_code"]).grade
    assert row["discrimination"] == mechanics.expert_discrimination
    assert row["difficulty"] == mechanics.expert_difficulty_by_grade[grade]
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

    first = shown_families(db_engine)
    dotest = start(candidate, "junior")

    assert dotest["attempt"] == {"grade": "junior", "answered": 0, "max_items": 30}
    # Невиданные семейства в банке есть — дотест не повторяет показанные в попытке на middle.
    item = candidate.get(ITEM).json()
    assert presented(db_engine, item["id"])[0].code not in first


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

    # Решает всё до junior включительно: уровень у порога middle, junior — уверенно.
    path = answer_items(candidate, db_engine, lambda family: family.grade in ("intern", "junior"))

    assert path["stage"] == "category"
    assert path["category"]["grade"]["code"] == "junior"
    assert path["result"]["grade"] == "middle"
    assert path["result"]["grade_up_hint"] is None
    assert category_rows(db_engine) == [("qa", "junior")]


def test_failed_cascade_leaves_no_category_until_retest_date(
    candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, db_engine, nothing)
    start(candidate, "junior")
    offer = answer_items(candidate, db_engine, nothing)
    # Каскад доходит до стажёра: дотесту всегда есть что спросить.
    assert offer["stage"] == "offer" and offer["offer_grade"] == "intern"
    start(candidate, "intern")

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


def test_specialization_without_bank_is_rejected(candidate: TestClient, db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO specializations (code, name, position) "
                "VALUES ('gamedev', 'Геймдев', 99);"
                "INSERT INTO topics (code, specialization_code, name, position) "
                "VALUES ('gamedev.engines', 'gamedev', 'Игровые движки', 0)"
            )
        )
    try:
        response = candidate.post(
            f"{PATH}/survey", json={"industry": "fintech", "specialization": "gamedev"}
        )
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM topics WHERE specialization_code = 'gamedev'"))
            conn.execute(text("DELETE FROM specializations WHERE code = 'gamedev'"))

    assert response.status_code == 422
    assert response.json()["code"] == "specialization_without_test"


@pytest.mark.parametrize(
    ("body", "code"),
    [
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


def near_junior(family: Family) -> bool:
    """Решает задания до junior включительно — тест останавливается за разумное число заданий."""
    return family.grade in ("intern", "junior")


def test_candidates_get_their_own_sets_and_instances(signed_in: SignIn, db_engine: Engine) -> None:
    """Кандидаты с одинаковыми ответами получают разные наборы семейств и свои экземпляры (§6)."""
    for _ in range(3):
        c = signed_in(Role.candidate)
        take_survey(c)
        start(c, "middle")
        answer_items(c, db_engine, near_junior)

    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.user_id, p.family_code, p.seed FROM presentations p "
                "JOIN test_attempts a ON a.id = p.attempt_id ORDER BY a.user_id, p.position"
            )
        ).all()
    sets: dict[uuid.UUID, list[str]] = {}
    for user_id, family_code, _ in rows:
        sets.setdefault(user_id, []).append(family_code)
    assert len({frozenset(codes) for codes in sets.values()}) == 3
    seeds = [seed for _, _, seed in rows]
    assert len(set(seeds)) == len(seeds)


def answer_current(c: TestClient, db_engine: Engine) -> Json:
    item = c.get(ITEM).json()
    family, seed = presented(db_engine, item["id"])
    response = family.instance(seed).answer if near_junior(family) else "ответа нет"
    answered = c.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": response})
    assert answered.status_code == 200, answered.text
    body: Json = answered.json()
    return body


def test_interrupted_attempt_resumes_after_backend_restart(
    candidate: TestClient,
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
) -> None:
    """Состояние попытки — список предъявлений, оценка — чистая функция от него (§6): после
    перезапуска бэкенда тест продолжается с того же задания и той же оценки."""
    take_survey(candidate)
    start(candidate, "middle")
    for _ in range(3):
        answer_current(candidate, db_engine)
    pending = candidate.get(ITEM).json()

    restarted = create_app(settings, mechanics, outbox)
    try:
        with TestClient(restarted, cookies=candidate.cookies) as again:
            path = again.get(PATH).json()
            assert path["stage"] == "test"
            assert path["attempt"]["answered"] == 3
            assert again.get(ITEM).json() == pending

            answer_current(again, db_engine)
            next_item = again.get(ITEM).json()
    finally:
        restarted.state.engine.dispose()

    assert next_item["number"] == 5
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT topic_code, correct, discrimination, difficulty, topic_theta_before, "
                "topic_theta_sd_before FROM presentations ORDER BY position"
            )
        ).all()
    observations = [Observation(t, c, a, b) for t, c, a, b, _, _ in rows[:4]]
    topic, *_, mean, sd = rows[4]
    expected = estimate(specialization_prior(QA_TOPICS, mechanics), observations).topic(topic)
    assert (mean, sd) == pytest.approx((expected.mean, expected.sd))


def test_finished_attempt_calibrates_shown_families(
    candidate: TestClient, db_engine: Engine, mechanics: Mechanics
) -> None:
    """После ответа — шаг Эло по семейству, после остановки — связка шкалы специализации (§7).
    Параметры якорных семейств заморожены, растёт только счётчик ответов."""
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, db_engine, near_junior)

    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT family_code, discrimination, difficulty, responses FROM family_calibrations"
            )
        ).all()
        link = conn.execute(
            text(
                "SELECT before_shift, before_scale, rest_scale FROM scale_links "
                "WHERE specialization_code = 'qa'"
            )
        ).one()
    assert {code for code, *_ in rows} == shown_families(db_engine)
    for code, discrimination, difficulty, responses in rows:
        family = get_family(code)
        start_difficulty = mechanics.expert_difficulty_by_grade[family.grade]
        assert responses == 1
        assert discrimination == mechanics.expert_discrimination
        assert (difficulty == start_difficulty) is family.anchor, code
    # Ответов на якоря одной попытки мало для связки — она тождественная.
    assert tuple(link) == (0.0, 1.0, 1.0)


def test_family_is_refitted_once_it_has_enough_answers(
    settings: Settings, mechanics: Mechanics, outbox: Outbox, db_engine: Engine
) -> None:
    """Набравшее ответов семейство переоценивается пакетно: результат — текущие и опорные
    параметры (§7). Порог здесь — один ответ, чтобы хватило одной попытки."""
    eager = mechanics.model_copy(update={"calibration_refit_min_responses": 1})
    app = create_app(settings, eager, outbox)
    try:
        with TestClient(app) as c:
            email = f"candidate-{uuid.uuid4().hex[:8]}@example.com"
            c.post(
                "/api/auth/register",
                json={"email": email, "password": PASSWORD, "role": "candidate"},
            )
            token = outbox.verification_token(email)
            c.post("/api/auth/verify-email", json={"token": token}).raise_for_status()
            c.post(
                "/api/auth/login", json={"email": email, "password": PASSWORD}
            ).raise_for_status()
            take_survey(c)
            start(c, "middle")
            answer_items(c, db_engine, near_junior)
    finally:
        app.state.engine.dispose()

    # Только семейства, предъявленные этому кандидату: строка калибровки, которой нет, — тоже
    # непереоценённое семейство.
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT p.family_code, c.discrimination, c.difficulty, "
                "c.reference_discrimination, c.reference_difficulty, c.refitted_at, c.status "
                "FROM presentations p "
                "JOIN test_attempts a ON a.id = p.attempt_id "
                "JOIN users u ON u.id = a.user_id "
                "LEFT JOIN family_calibrations c ON c.family_code = p.family_code "
                "WHERE u.email = :email"
            ),
            {"email": email},
        ).all()
    regular = [r for r in rows if not get_family(r[0]).anchor]
    assert regular
    for _, a, b, ref_a, ref_b, refitted_at, status in regular:
        assert refitted_at is not None
        assert (ref_a, ref_b) == (a, b)
        assert status in ("active", "review")
