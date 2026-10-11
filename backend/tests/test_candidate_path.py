"""Путь кандидата к категории через HTTP API: опрос → грейд → тест → категория (§4)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.adapter.calibration import EloCalibration
from app.adapter.catalog_file import load_catalog
from app.adapter.clock import FrozenClock
from app.adapter.irt import estimate
from app.adapter.password import Argon2Passwords
from app.domain.account import Role
from app.domain.bank import Family, families_for_topics, get_family
from app.domain.skill import Normal, Observation
from app.repository.calibration import SqlCalibrationRepository
from app.repository.orm import FamilyCalibration
from app.usecase.skill_profile import specialization_prior
from main import create_app
from settings import CATALOG_FILE, Mechanics, Settings
from tests.candidate_path import (
    ITEM,
    PATH,
    RUNNER,
    WRONG,
    answer_items,
    everything,
    nothing,
    presented,
    start,
    take_survey,
)
from tests.conftest import PASSWORD, Outbox, Seeds, transaction

QA_TOPICS = [
    t.code for s in load_catalog(CATALOG_FILE).specializations if s.code == "qa" for t in s.topics
]

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


def answered_count(db_engine: Engine) -> int:
    with db_engine.connect() as conn:
        count: int = conn.execute(
            text("SELECT count(*) FROM presentations WHERE correct IS NOT NULL")
        ).scalar_one()
        return count


def test_new_candidate_starts_with_survey_and_has_no_category(
    candidate: TestClient, db_engine: Engine
) -> None:
    path = candidate.get(PATH).json()

    assert path["stage"] == "survey"
    assert path["category"] is None
    assert category_rows(db_engine) == []


def test_full_path_to_category(seeds: Seeds, candidate: TestClient, db_engine: Engine) -> None:
    survey = take_survey(candidate)
    assert survey["stage"] == "grade"
    assert survey["survey"]["specialization"] == {"code": "qa", "name": "QA"}
    assert "industry" not in survey["survey"]

    started = start(candidate, "middle")
    assert started["stage"] == "test"
    assert started["attempt"] == {
        "grade": "middle",
        "answered": 0,
        "max_items": 30,
        "express": False,
    }

    path = answer_items(candidate, seeds, everything)

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


def test_item_carries_no_answer(candidate: TestClient, seeds: Seeds) -> None:
    take_survey(candidate, "backend")
    start(candidate, "junior")

    item = candidate.get(ITEM).json()

    assert set(item) == {
        "id",
        "number",
        "max_items",
        "topic_block",
        "verification",
        "vacancy_test",
        "deadline",
        "focus_consent",
        "topic",
        "prompt",
        "code",
        "answer_format",
        "options",
    }
    assert item["number"] == 1 and item["max_items"] == 30 and item["topic_block"] is False
    family, seed = presented(seeds, item)
    instance = family.instance(seed, RUNNER)
    assert item["prompt"] == instance.prompt
    assert item["code"] == instance.code

    answered = candidate.post(
        f"{ITEM}/answer", json={"presentation_id": item["id"], "response": instance.answer}
    )
    assert "correct" not in answered.text
    assert answered.json()["attempt"]["answered"] == 1


def test_presentation_is_recorded_with_server_response_time(
    seeds: Seeds, candidate: TestClient, db_engine: Engine, mechanics: Mechanics, clock: FrozenClock
) -> None:
    take_survey(candidate)
    start(candidate, "junior")

    item = candidate.get(ITEM).json()
    family, seed = presented(seeds, item)
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
    # Проверка ответа идёт по сохранённому seed — он тот же, по которому построено задание.
    assert (row["family_code"], row["seed"]) == (family.code, seed)
    assert row["params"]
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
    seeds: Seeds, candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")

    offer = answer_items(candidate, seeds, nothing)

    assert offer["stage"] == "offer"
    assert offer["offer_grade"] == "junior"
    assert offer["result"]["grade"] == "middle"
    assert category_rows(db_engine) == []
    wrong_grade = candidate.post(f"{PATH}/attempts", json={"grade": "middle"})
    assert wrong_grade.status_code == 409
    assert wrong_grade.json()["code"] == "grade_not_offered"

    first = shown_families(db_engine)
    dotest = start(candidate, "junior")

    assert dotest["attempt"] == {
        "grade": "junior",
        "answered": 0,
        "max_items": 30,
        "express": False,
    }
    # Невиданные семейства в банке есть — дотест не повторяет показанные в попытке на middle.
    item = candidate.get(ITEM).json()
    assert presented(seeds, item)[0].code not in first


def test_path_order_does_not_depend_on_server_clock(
    candidate: TestClient, seeds: Seeds, clock: FrozenClock
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, seeds, nothing)

    # Синхронизация отвела часы назад: дотест начат «раньше» первой попытки.
    clock.shift(timedelta(seconds=-30))
    dotest = start(candidate, "junior")

    assert dotest["stage"] == "test"
    assert candidate.get(PATH).json()["attempt"]["grade"] == "junior"


def test_skill_profile_is_updated_at_the_moment_of_the_scenario(
    seeds: Seeds, candidate: TestClient, db_engine: Engine, clock: FrozenClock
) -> None:
    def updated_at() -> datetime:
        with db_engine.connect() as conn:
            moment: datetime = conn.scalar(text("SELECT updated_at FROM skill_profiles"))
        return moment

    # Вход живёт неделю — моменты в её пределах.
    first = clock.now() + timedelta(hours=1, minutes=17)
    clock.set(first)
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, seeds, nothing)
    assert updated_at() == first

    clock.shift(timedelta(days=2, hours=3))
    start(candidate, "junior")
    answer_items(candidate, seeds, nothing)
    assert updated_at() == first + timedelta(days=2, hours=3)


def test_dotest_below_is_skipped_when_confidence_is_already_there(
    seeds: Seeds, candidate: TestClient, db_engine: Engine
) -> None:
    take_survey(candidate)
    start(candidate, "middle")

    # Решает всё до junior включительно: уровень у порога middle, junior — уверенно.
    path = answer_items(candidate, seeds, lambda family: family.grade in ("intern", "junior"))

    assert path["stage"] == "category"
    assert path["category"]["grade"]["code"] == "junior"
    assert path["result"]["grade"] == "middle"
    assert path["result"]["grade_up_hint"] is None
    assert category_rows(db_engine) == [("qa", "junior")]


def test_failed_cascade_leaves_no_category_until_retest_date(
    seeds: Seeds, candidate: TestClient, db_engine: Engine, clock: FrozenClock
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, seeds, nothing)
    start(candidate, "junior")
    offer = answer_items(candidate, seeds, nothing)
    # Каскад доходит до стажёра: дотесту всегда есть что спросить.
    assert offer["stage"] == "offer" and offer["offer_grade"] == "intern"
    start(candidate, "intern")

    path = answer_items(candidate, seeds, nothing)

    assert path["stage"] == "no_category"
    assert path["category"] is None
    assert category_rows(db_engine) == []
    retest_after = datetime.fromisoformat(path["retest_after"])
    assert retest_after - clock.now() == timedelta(days=30)
    for blocked in (
        candidate.post(f"{PATH}/attempts", json={"grade": "intern"}),
        candidate.post(f"{PATH}/survey", json={"specialization": "qa"}),
    ):
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "path_step_unavailable"

    email = candidate.get("/api/auth/me").json()["email"]
    clock.shift(timedelta(minutes=-1))
    assert candidate.get(PATH).json()["stage"] == "no_category", "минутой раньше — ещё рано"

    clock.set(retest_after + timedelta(minutes=1))
    # Вход за это время истёк — входим заново.
    candidate.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert candidate.get(PATH).json()["stage"] == "grade"


def test_failed_intern_leaves_no_category(candidate: TestClient, seeds: Seeds) -> None:
    take_survey(candidate)
    start(candidate, "intern")

    path = answer_items(candidate, seeds, nothing)

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
        response = candidate.post(f"{PATH}/survey", json={"specialization": "gamedev"})
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM topics WHERE specialization_code = 'gamedev'"))
            conn.execute(text("DELETE FROM specializations WHERE code = 'gamedev'"))

    assert response.status_code == 422
    assert response.json()["code"] == "specialization_without_test"


def test_survey_rejects_unknown_specialization(candidate: TestClient) -> None:
    response = candidate.post(f"{PATH}/survey", json={"specialization": "astrology"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_specialization"


def test_survey_asks_direction_only(candidate: TestClient) -> None:
    """«Отрасль» из ТЗ — IT-направление, то есть специализация. Сфера бизнеса в опросе не
    нужна: прежнее поле игнорируется, а не требуется."""
    path = candidate.post(f"{PATH}/survey", json={"specialization": "qa", "industry": "alchemy"})

    assert path.status_code == 200, path.text
    assert path.json()["survey"]["specialization"]["code"] == "qa"


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


def test_candidates_get_their_own_sets_and_instances(
    seeds: Seeds, signed_in: SignIn, db_engine: Engine
) -> None:
    """Кандидаты с одинаковыми ответами получают разные наборы семейств и свои экземпляры (§6)."""
    for _ in range(3):
        c = signed_in(Role.candidate)
        take_survey(c)
        start(c, "middle")
        answer_items(c, seeds, near_junior)

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
    stored = [seed for _, _, seed in rows]
    assert len(set(stored)) == len(stored)


def shown_instances(db_engine: Engine) -> list[tuple[str, str]]:
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT family_code, params::text FROM presentations ORDER BY position")
        )
        return [(code, params) for code, params in rows]


def test_same_run_seed_gives_the_same_items(
    seeds: Seeds, signed_in: SignIn, db_engine: Engine
) -> None:
    """Один и тот же seed прогона и те же ответы — те же семейства в том же порядке и те же
    экземпляры. Банк и калибровка перед повтором — как перед первым прогоном."""

    def run() -> list[tuple[str, str]]:
        seeds.reset(17)
        c = signed_in(Role.candidate)
        take_survey(c)
        start(c, "middle")
        answer_items(c, seeds, near_junior)
        shown = shown_instances(db_engine)
        with db_engine.begin() as conn:
            conn.execute(text("TRUNCATE users, family_calibrations, scale_links CASCADE"))
        return shown

    first = run()

    assert len(first) > 1
    assert run() == first


def answer_current(c: TestClient, seeds: Seeds) -> Json:
    item = c.get(ITEM).json()
    family, seed = presented(seeds, item)
    response = family.instance(seed, RUNNER).answer if near_junior(family) else "ответа нет"
    answered = c.post(f"{ITEM}/answer", json={"presentation_id": item["id"], "response": response})
    assert answered.status_code == 200, answered.text
    body: Json = answered.json()
    return body


def test_interrupted_attempt_resumes_after_backend_restart(
    seeds: Seeds,
    candidate: TestClient,
    db_engine: Engine,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    clock: FrozenClock,
    passwords: Argon2Passwords,
) -> None:
    """Состояние попытки — список предъявлений, оценка — чистая функция от него (§6): после
    перезапуска бэкенда тест продолжается с того же задания и той же оценки."""
    take_survey(candidate)
    start(candidate, "middle")
    for _ in range(3):
        answer_current(candidate, seeds)
    pending = candidate.get(ITEM).json()

    restarted = create_app(
        settings, mechanics, outbox, clock=clock, seeds=seeds, passwords=passwords
    )
    try:
        with TestClient(restarted, cookies=candidate.cookies) as again:
            path = again.get(PATH).json()
            assert path["stage"] == "test"
            assert path["attempt"]["answered"] == 3
            assert again.get(ITEM).json() == pending

            answer_current(again, seeds)
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
    seeds: Seeds, candidate: TestClient, db_engine: Engine, mechanics: Mechanics
) -> None:
    """После ответа — шаг Эло по семейству, после остановки — связка шкалы специализации (§7).
    Параметры якорных семейств заморожены, растёт только счётчик ответов."""
    take_survey(candidate)
    start(candidate, "middle")
    answer_items(candidate, seeds, near_junior)

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
    shown = shown_families(db_engine)
    # Остановка берёт строки не только показанных семейств, но и якорей специализации: пересчёт
    # связки может вывести якорь из выдачи (lock в adapter/calibration). Непоказанный якорь
    # остаётся с нулём ответов и стартовыми параметрами.
    assert {code for code, *_ in rows} >= shown
    assert all(get_family(code).anchor for code, *_ in rows if code not in shown)
    for code, discrimination, difficulty, responses in rows:
        family = get_family(code)
        start_difficulty = mechanics.expert_difficulty_by_grade[family.grade]
        assert responses == (1 if code in shown else 0)
        assert discrimination == mechanics.expert_discrimination
        assert (difficulty == start_difficulty) is family.anchor, code
    # Ответов на якоря одной попытки мало для связки — она тождественная.
    assert tuple(link) == (0.0, 1.0, 1.0)


def test_family_is_refitted_once_it_has_enough_answers(
    seeds: Seeds,
    settings: Settings,
    mechanics: Mechanics,
    outbox: Outbox,
    db_engine: Engine,
    clock: FrozenClock,
    passwords: Argon2Passwords,
) -> None:
    """Набравшее ответов семейство переоценивается пакетно: результат — текущие и опорные
    параметры (§7). Порог здесь — один ответ, чтобы хватило одной попытки."""
    eager = mechanics.model_copy(update={"calibration_refit_min_responses": 1})
    app = create_app(settings, eager, outbox, clock=clock, seeds=seeds, passwords=passwords)
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
            answer_items(c, seeds, near_junior)
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


def calibration_of(db: Session, mechanics: Mechanics) -> EloCalibration:
    """Реализация порта калибровки — с теми же параметрами конфига, что передаёт сборка."""
    return EloCalibration(
        SqlCalibrationRepository(db),
        expert_discrimination=mechanics.expert_discrimination,
        expert_difficulty_by_grade=mechanics.expert_difficulty_by_grade,
        elo_k_initial=mechanics.elo_k_initial,
        elo_k_half_responses=mechanics.elo_k_half_responses,
        elo_k_min=mechanics.elo_k_min,
        calibration_refit_min_responses=mechanics.calibration_refit_min_responses,
        calibration_expert_gap_review=mechanics.calibration_expert_gap_review,
        calibration_refit_difficulty_prior_sd=mechanics.calibration_refit_difficulty_prior_sd,
        calibration_refit_log_discrimination_prior_sd=(
            mechanics.calibration_refit_log_discrimination_prior_sd
        ),
        calibration_link_window_attempts=mechanics.calibration_link_window_attempts,
        item_fit_groups=mechanics.item_fit_groups,
        item_fit_rmsd_max=mechanics.item_fit_rmsd_max,
        item_fit_discrimination_min=mechanics.item_fit_discrimination_min,
        item_fit_ceiling_gain_max=mechanics.item_fit_ceiling_gain_max,
        item_fit_ceiling_min=mechanics.item_fit_ceiling_min,
        item_fit_ceiling_step=mechanics.item_fit_ceiling_step,
    )


def test_elo_moves_difficulty_only_until_refit(db_engine: Engine, mechanics: Mechanics) -> None:
    """Эло сдвигает сложность семейства после ответа, пока нет пакетной переоценки; после неё
    текущие параметры остаются опорными, растёт только счётчик ответов (§7)."""
    family = next(f for f in families_for_topics(QA_TOPICS) if not f.anchor)
    level_before = Normal(0.0, 0.5)

    with transaction(db_engine) as db:
        calibration_of(db, mechanics).learn("qa", family.code, level_before, True)
        row = db.get_one(FamilyCalibration, family.code)
        assert row.difficulty < mechanics.expert_difficulty_by_grade[family.grade]
        row.reference_discrimination, row.reference_difficulty = row.discrimination, row.difficulty
        row.refitted_at = datetime.now(UTC)
        reference = (row.discrimination, row.difficulty)

    with transaction(db_engine) as db:
        calibration_of(db, mechanics).learn("qa", family.code, level_before, False)

    with Session(db_engine) as db:
        row = db.get_one(FamilyCalibration, family.code)
        assert (row.discrimination, row.difficulty) == reference
        assert row.responses == 2


CALIBRATION_TABLES = ("family_calibrations", "scale_links")


def calibration(db_engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    with db_engine.connect() as conn:
        return {
            table: [tuple(row) for row in conn.execute(text(f"SELECT * FROM {table} ORDER BY 1"))]
            for table in CALIBRATION_TABLES
        }


@pytest.mark.parametrize("failing", ["learn", "refit_due"])
def test_failed_calibration_keeps_the_answer(
    failing: str,
    seeds: Seeds,
    candidate: TestClient,
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Калибровка идёт после фиксации ответа своим сценарием (§7): сбой шага Эло после каждого
    ответа или переоценки после остановки ответ и итог попытки не отменяет, клиент получает
    успех, а записанное той же калибровкой откатывается."""

    def fails(*_: Any, **__: Any) -> None:
        raise RuntimeError("калибровка упала")

    monkeypatch.setattr(EloCalibration, failing, fails)
    take_survey(candidate)
    start(candidate, "middle")

    path: Json = {"stage": "test"}
    while path["stage"] == "test":
        item = candidate.get(ITEM).json()
        family, seed = presented(seeds, item)
        body = {"presentation_id": item["id"], "response": family.instance(seed, RUNNER).answer}
        before = calibration(db_engine)
        answered = candidate.post(f"{ITEM}/answer", json=body)
        assert answered.status_code == 200, answered.text
        assert answered_count(db_engine) == item["number"]
        path = answered.json()

    assert path["stage"] == "category"
    assert category_rows(db_engine) == [("qa", "middle")]
    assert calibration(db_engine) == before
    assert "Калибровка после ответа" in caplog.text


def test_grade_change_through_api(
    seeds: Seeds, candidate: TestClient, db_engine: Engine, clock: FrozenClock, mechanics: Mechanics
) -> None:
    """Смена грейда в кабинете (§4): прошедший заявленный грейд сразу видит попытку вверх;
    переход вниз — сразу, без заданий; после него попытка вверх отклоняется с датой, когда можно,
    а история показывает попытку и переход."""
    take_survey(candidate)
    start(candidate, "middle")
    path = answer_items(candidate, seeds, everything)
    assert path["grade_up"] == {"grade": "senior", "available_at": None}
    assert path["grade_down"] == "junior"

    answered = answered_count(db_engine)
    down = candidate.post(f"{PATH}/step-down")
    assert down.status_code == 200, down.text
    path = down.json()
    assert path["category"]["grade"]["code"] == "junior"
    assert category_rows(db_engine) == [("qa", "junior")]
    assert answered_count(db_engine) == answered
    assert [(h["event"], h["grade"]) for h in path["history"]] == [
        ("attempt", "middle"),
        ("step_down", "junior"),
    ]
    attempt = path["history"][0]
    assert attempt["purpose"] == "determination" and attempt["outcome"] == "assigned"
    assert attempt["overall"]["theta_sd"] > 0

    allowed = clock.now() + timedelta(days=mechanics.grade_change_interval_days)
    assert datetime.fromisoformat(path["grade_up"]["available_at"]) == allowed
    early = candidate.post(f"{PATH}/attempts", json={"grade": "middle"})
    assert early.status_code == 409
    assert early.json()["code"] == "grade_change_too_early"
    assert datetime.fromisoformat(early.json()["available_at"]) == allowed

    # Сессия за срок ожидания истекает — вход заново.
    email = candidate.get("/api/auth/me").json()["email"]
    clock.set(allowed)
    login = {"email": email, "password": PASSWORD}
    candidate.post("/api/auth/login", json=login).raise_for_status()
    up = start(candidate, "middle")
    assert up["stage"] == "test" and up["category"]["grade"]["code"] == "junior"
    path = answer_items(candidate, seeds, everything)
    assert path["category"]["grade"]["code"] == "middle"
    assert path["history"][-1]["purpose"] == "grade_up"
    with db_engine.connect() as conn:
        kinds = conn.execute(text("SELECT kind FROM category_changes ORDER BY number")).scalars()
        assert list(kinds) == ["determined", "down", "up"]


def test_step_down_needs_a_category(candidate: TestClient) -> None:
    take_survey(candidate)
    response = candidate.post(f"{PATH}/step-down")
    assert response.status_code == 409
    assert response.json() == {
        "code": "path_step_unavailable",
        "message": "Этот шаг сейчас недоступен — обновите страницу",
    }


def answer_block(c: TestClient, seeds: Seeds, correct: Callable[[Family], bool]) -> Json:
    """Отвечает на задания блока по теме до его конца."""
    path: Json = c.get(PATH).json()
    while path["topic_block"] is not None:
        item = c.get(ITEM).json()
        assert item["topic_block"] is True, item
        family, seed = presented(seeds, item)
        response = family.instance(seed, RUNNER).answer if correct(family) else WRONG
        answered = c.post(
            f"{ITEM}/answer", json={"presentation_id": item["id"], "response": response}
        )
        assert answered.status_code == 200, answered.text
        path = answered.json()
    return path


def test_topic_block_through_api(
    seeds: Seeds, candidate: TestClient, db_engine: Engine, clock: FrozenClock, mechanics: Mechanics
) -> None:
    """Блок по теме (§6): ровно `topic_block_items` заданий темы, профиль по теме меняется,
    категория и история — нет; повтор раньше интервала — 409 с датой, когда можно."""
    early = candidate.post(f"{PATH}/topic-block", json={"topic": "qa.api"})
    assert early.status_code == 409 and early.json()["code"] == "category_required"
    take_survey(candidate)
    start(candidate, "junior")
    before = answer_items(candidate, seeds, everything)
    level = {t["topic"]["code"]: t["level"] for t in before["profile"]["topics"]}["qa.api"]
    wrong = candidate.post(f"{PATH}/topic-block", json={"topic": "backend.api"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "topic_not_in_category"

    started = candidate.post(f"{PATH}/topic-block", json={"topic": "qa.api"})
    assert started.status_code == 200, started.text
    block = started.json()["topic_block"]
    assert block == {
        "topic": {"code": "qa.api", "name": "Тестирование API"},
        "answered": 0,
        "items": mechanics.topic_block_items,
    }
    up = candidate.post(f"{PATH}/attempts", json={"grade": "middle"})
    assert up.status_code == 409 and up.json()["code"] == "attempt_in_progress"
    item = candidate.get(ITEM).json()
    assert (item["max_items"], item["topic"]["code"]) == (mechanics.topic_block_items, "qa.api")

    path = answer_block(candidate, seeds, nothing)
    after = {t["topic"]["code"]: t["level"] for t in path["profile"]["topics"]}["qa.api"]
    assert after != level
    assert (path["stage"], path["category"], path["history"]) == (
        before["stage"],
        before["category"],
        before["history"],
    )
    assert category_rows(db_engine) == [("qa", "junior")]
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT p.topic_code FROM presentations p JOIN test_attempts a "
                "ON a.id = p.attempt_id WHERE a.purpose = 'topic_block'"
            )
        ).scalars()
        assert list(rows) == ["qa.api"] * mechanics.topic_block_items

    again = candidate.post(f"{PATH}/topic-block", json={"topic": "qa.api"})
    assert again.status_code == 409 and again.json()["code"] == "topic_block_too_early"
    allowed = clock.now() + timedelta(days=mechanics.topic_block_interval_days)
    assert datetime.fromisoformat(again.json()["available_at"]) == allowed
