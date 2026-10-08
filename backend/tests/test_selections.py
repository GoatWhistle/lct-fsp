"""Подборка по потребности через HTTP API (mechanics.md, §12): кто попадает, объяснение, потолок
самоописания, монотонность, сохранённая выдача, права и скорость."""

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, insert, select, update

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from app.repository.orm import (
    CandidateCategory,
    CandidateProfile,
    Grade,
    SkillProfile,
    SkillProfileTopic,
    Survey,
    TestAttempt,
    Topic,
    User,
    candidate_technologies,
)
from settings import Mechanics
from tests.candidate_path import answer_items, nothing, pass_test, start, take_survey
from tests.conftest import Seeds, transaction

NEEDS = "/api/employer/needs"
SELECTIONS = "/api/employer/selections"
PROFILE = "/api/candidate/profile"
NEED_STACK = ["playwright", "postgresql", "pytest"]

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return signed_in(Role.employer)


def need_body(**changes: Any) -> Json:
    body: Json = {
        "title": "QA-инженер в команду платежей",
        "specialization": "qa",
        "grade": "middle",
        "stack": NEED_STACK,
        "work_format": "remote",
    }
    return body | changes


def create_need(c: TestClient, **changes: Any) -> str:
    response = c.post(NEEDS, json=need_body(**changes))
    assert response.status_code == 201, response.text
    need_id: str = response.json()["id"]
    return need_id


def build(c: TestClient, need_id: str, **params: Any) -> Json:
    response = c.post(f"{NEEDS}/{need_id}/selections", params=params)
    assert response.status_code == 201, response.text
    body: Json = response.json()
    return body


def open_selection(c: TestClient, selection_id: str, **params: Any) -> Json:
    response = c.get(f"{SELECTIONS}/{selection_id}", params=params)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def user_id(c: TestClient) -> str:
    me: str = c.get("/api/auth/me").json()["id"]
    return me


def entry_of(selection: Json, candidate: str) -> Json:
    entries: list[Json] = [e for e in selection["entries"] if e["candidate_id"] == candidate]
    assert len(entries) == 1, selection["entries"]
    return entries[0]


def profile_body(stack: Sequence[str]) -> Json:
    return {
        "full_name": "Ёлкина Юлия Сергеевна",
        "contact_email": "yulia@example.ru",
        "about": "Пишу автотесты, люблю разбирать флаки",
        "stack": list(stack),
        "job_roles": ["тимлид"],
        "experience_years": 4,
        "work_formats": ["remote"],
        "salary_from": 287_500,
    }


@dataclass
class Seed:
    """Кандидат с категорией и профилем навыков — прямо в базу, без прохождения теста."""

    grade: str = "middle"
    # Тема → (уровень, погрешность); темы без записи — средний уровень с типичной погрешностью.
    levels: dict[str, tuple[float, float]] = field(default_factory=dict)
    stack: list[str] = field(default_factory=list)
    last_signal_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def seed(db_engine: Engine, seeds: Sequence[Seed], specialization: str = "qa") -> list[str]:
    with transaction(db_engine) as db:
        topics = db.scalars(
            select(Topic.code).where(Topic.specialization_code == specialization)
        ).all()
        rows: dict[Any, list[Json]] = {
            model: []
            for model in (
                User,
                Survey,
                TestAttempt,
                CandidateCategory,
                SkillProfile,
                SkillProfileTopic,
                CandidateProfile,
                candidate_technologies,
            )
        }
        ids = []
        for s in seeds:
            uid, survey, attempt, profile = (uuid.uuid4() for _ in range(4))
            ids.append(str(uid))
            now = s.last_signal_at
            rows[User].append(
                {
                    "id": uid,
                    "email": f"seed-{uid.hex}@example.com",
                    "password_hash": "-",
                    "role": Role.candidate,
                    "email_verified_at": now,
                    "created_at": now,
                }
            )
            rows[Survey].append(
                {
                    "id": survey,
                    "user_id": uid,
                    "number": 1,
                    "specialization_code": specialization,
                    "created_at": now,
                }
            )
            rows[TestAttempt].append(
                {
                    "id": attempt,
                    "user_id": uid,
                    "number": 1,
                    "survey_id": survey,
                    "specialization_code": specialization,
                    "grade_code": s.grade,
                    "started_at": now,
                }
            )
            rows[CandidateCategory].append(
                {
                    "user_id": uid,
                    "specialization_code": specialization,
                    "grade_code": s.grade,
                    "attempt_id": attempt,
                    "assigned_at": now,
                }
            )
            rows[SkillProfile].append(
                {
                    "id": profile,
                    "user_id": uid,
                    "specialization_code": specialization,
                    "overall_theta": 0.5,
                    "overall_theta_sd": 0.4,
                    "observations": 20,
                    "last_signal_at": now,
                    "updated_at": now,
                }
            )
            for topic in topics:
                theta, theta_sd = s.levels.get(topic, (0.5, 0.5))
                rows[SkillProfileTopic].append(
                    {
                        "profile_id": profile,
                        "topic_code": topic,
                        "theta": theta,
                        "theta_sd": theta_sd,
                    }
                )
            if s.stack:
                rows[CandidateProfile].append(
                    {
                        "user_id": uid,
                        "full_name": "Сидов Сид",
                        "contact_email": "seed@example.com",
                        "about": "",
                        "job_roles": [],
                        "soft_skills": [],
                        "experience_years": 3,
                        "work_formats": ["remote"],
                        "relocation": False,
                        "salary_from": 200_000,
                        "updated_at": now,
                    }
                )
                rows[candidate_technologies].extend(
                    {"user_id": uid, "technology_code": t} for t in s.stack
                )

        # По порядку ключей — родительские таблицы раньше дочерних.
        for table, values in rows.items():
            if values:
                db.execute(insert(table), values)
    return ids


def set_level(db_engine: Engine, candidate: str, topic: str, theta: float) -> None:
    with transaction(db_engine) as db:
        profile = select(SkillProfile.id).where(SkillProfile.user_id == uuid.UUID(candidate))
        db.execute(
            update(SkillProfileTopic)
            .where(SkillProfileTopic.profile_id == profile.scalar_subquery())
            .where(SkillProfileTopic.topic_code == topic)
            .values(theta=theta)
        )


def test_selection_has_only_candidates_with_category_by_test(
    signed_in: SignIn, employer: TestClient, seeds: Seeds
) -> None:
    middle = signed_in(Role.candidate)
    pass_test(middle, seeds, "middle")
    junior = signed_in(Role.candidate)
    pass_test(junior, seeds, "junior")
    intern = signed_in(Role.candidate)
    pass_test(intern, seeds, "intern")
    # Тест провален — категории нет, предложен дотест ниже.
    failed = signed_in(Role.candidate)
    take_survey(failed)
    start(failed, "middle")
    assert answer_items(failed, seeds, nothing)["stage"] == "offer"
    # Профиль заполнен, стек — весь стек потребности, но теста нет.
    self_described = signed_in(Role.candidate)
    self_described.put(PROFILE, json=profile_body(NEED_STACK)).raise_for_status()

    selection = build(employer, create_need(employer))

    assert (selection["exact_total"], selection["nearby_total"]) == (1, 1)
    exact, nearby = selection["entries"]
    assert (exact["candidate_id"], exact["block"], exact["rank"], exact["position"]) == (
        user_id(middle),
        "exact",
        1,
        1,
    )
    assert exact["grade"] == {"code": "middle", "name": "Middle"}
    # Соседний грейд — «близкие»; стажёр в двух грейдах от middle не попадает.
    assert (nearby["candidate_id"], nearby["block"], nearby["rank"], nearby["position"]) == (
        user_id(junior),
        "nearby",
        1,
        2,
    )


def test_other_specialization_is_not_in_selection(employer: TestClient, db_engine: Engine) -> None:
    seed(db_engine, [Seed()], specialization="backend")

    selection = build(employer, create_need(employer))

    assert selection["exact_total"] == selection["nearby_total"] == 0
    assert selection["entries"] == []


def test_explanation_contributions_sum_to_score(
    signed_in: SignIn, employer: TestClient, seeds: Seeds, mechanics: Mechanics
) -> None:
    candidate = signed_in(Role.candidate)
    pass_test(candidate, seeds)
    candidate.put(PROFILE, json=profile_body(["pytest", "python"])).raise_for_status()

    selection = build(employer, create_need(employer))
    entry = entry_of(selection, user_id(candidate))

    cap = mechanics.self_reported_stack_cap
    assert selection["stack_cap"] == cap
    contributions = [t["contribution"] for t in entry["topics"]] + [entry["stack"]["contribution"]]
    assert sum(contributions) == pytest.approx(entry["match_score"], abs=1e-9)
    # Модели принятия нет — множитель 1.
    assert entry["acceptance_probability"] is None
    assert entry["mutual_score"] == entry["match_score"]

    need_topics = selection["need"]["topics"]
    assert [t["topic"]["code"] for t in entry["topics"]] == [
        t["topic"]["code"] for t in need_topics
    ]
    assert sum(t["weight"] for t in need_topics) == pytest.approx(1)
    threshold = mechanics.grade_thresholds["middle"]
    for topic in entry["topics"]:
        assert topic["requirement"] == threshold
        assert topic["contribution"] == pytest.approx(
            (1 - cap) * topic["weight"] * topic["probability"]
        )
        assert topic["verdict"] in {"confidently_above", "likely_above", "likely_below", "below"}
    assert entry["stack"] == {
        "matched": [{"code": "pytest", "name": "pytest"}],
        "total": 3,
        "overlap": pytest.approx(1 / 3),
        "contribution": pytest.approx(cap / 3),
    }


def test_verdicts_and_low_data_follow_confidence_language(
    employer: TestClient, db_engine: Engine
) -> None:
    (candidate,) = seed(
        db_engine,
        [
            Seed(
                levels={
                    "qa.theory": (1.5, 0.3),
                    "qa.api": (0.7, 0.4),
                    "qa.automation": (0.3, 0.4),
                    "qa.databases": (-1.0, 0.4),
                    "qa.performance": (0.5, 1.0),
                }
            )
        ],
    )

    entry = entry_of(build(employer, create_need(employer)), candidate)

    words = {t["topic"]["code"]: (t["verdict"], t["low_data"]) for t in entry["topics"]}
    assert words == {
        "qa.theory": ("confidently_above", False),
        "qa.api": ("likely_above", False),
        "qa.automation": ("likely_below", False),
        "qa.databases": ("below", False),
        "qa.performance": ("likely_above", True),
    }


def test_self_described_full_stack_lifts_score_no_more_than_cap(
    signed_in: SignIn, employer: TestClient, seeds: Seeds, mechanics: Mechanics
) -> None:
    candidate = signed_in(Role.candidate)
    pass_test(candidate, seeds)
    need = create_need(employer)
    honest = entry_of(build(employer, need), user_id(candidate))

    # Дописал в профиль весь стек потребности и ещё сверху — ничем не подтверждено.
    stack = [*NEED_STACK, "python", "java", "kafka"]
    candidate.put(PROFILE, json=profile_body(stack)).raise_for_status()
    padded = entry_of(build(employer, need), user_id(candidate))

    cap = mechanics.self_reported_stack_cap
    assert padded["stack"]["overlap"] == 1
    assert padded["stack"]["contribution"] == pytest.approx(cap)
    assert padded["match_score"] - honest["match_score"] == pytest.approx(cap)
    assert [t["contribution"] for t in padded["topics"]] == [
        t["contribution"] for t in honest["topics"]
    ]


def test_padded_stack_does_not_lift_weak_candidate_above_strong_one(
    employer: TestClient, db_engine: Engine
) -> None:
    topics = ["qa.theory", "qa.api", "qa.automation", "qa.databases", "qa.performance"]
    strong, padded = seed(
        db_engine,
        [
            Seed(levels=dict.fromkeys(topics, (1.0, 0.4))),
            Seed(levels=dict.fromkeys(topics, (0.2, 0.4)), stack=NEED_STACK),
        ],
    )

    selection = build(employer, create_need(employer))

    assert [e["candidate_id"] for e in selection["entries"]] == [strong, padded]
    assert entry_of(selection, padded)["stack"]["overlap"] == 1


def test_raising_topic_level_does_not_move_candidate_down(
    employer: TestClient, db_engine: Engine
) -> None:
    ids = seed(
        db_engine,
        [Seed(levels={"qa.automation": (0.1 * i - 0.5, 0.4)}) for i in range(10)],
    )
    need = create_need(employer)
    before = [e["candidate_id"] for e in build(employer, need, limit=100)["entries"]]
    who = before[-1]

    for theta in (0.0, 0.6, 1.2, 3.0):
        set_level(db_engine, who, "qa.automation", theta)
        after = [e["candidate_id"] for e in build(employer, need, limit=100)["entries"]]
        assert after.index(who) <= before.index(who)
        before = after
    assert before.index(who) == 0
    assert set(before) == set(ids)


def test_topic_missing_from_profile_counts_as_prior_with_low_data(
    employer: TestClient, db_engine: Engine, mechanics: Mechanics
) -> None:
    # Тему добавили в справочник, а профиль кандидата пересчитается только со следующим сигналом.
    (candidate,) = seed(db_engine, [Seed(levels={"qa.api": (1.5, 0.3)})])
    with transaction(db_engine) as db:
        absent = SkillProfileTopic.topic_code == "qa.performance"
        db.execute(delete(SkillProfileTopic).where(absent))

    entry = entry_of(build(employer, create_need(employer)), candidate)

    topics = {t["topic"]["code"]: t for t in entry["topics"]}
    missing = topics["qa.performance"]
    assert missing["theta"] == 0
    assert missing["theta_sd"] == pytest.approx(
        mechanics.level_sd_inflation
        * (mechanics.theta_prior_sd**2 + mechanics.topic_deviation_sd**2) ** 0.5
    )
    assert missing["low_data"] is True
    assert topics["qa.api"]["verdict"] == "confidently_above"


def test_deleted_candidate_leaves_selection_consistent(
    employer: TestClient, db_engine: Engine
) -> None:
    gone, *_ = seed(db_engine, [Seed(levels={"qa.api": (3.0, 0.2)}), Seed(), Seed(grade="senior")])
    built = build(employer, create_need(employer))
    assert built["entries"][0]["candidate_id"] == gone

    with transaction(db_engine) as db:
        db.execute(delete(User).where(User.id == uuid.UUID(gone)))

    reopened = open_selection(employer, built["id"])
    assert (reopened["exact_total"], reopened["nearby_total"]) == (1, 1)
    assert [e["candidate_id"] for e in reopened["entries"]] == [
        e["candidate_id"] for e in built["entries"][1:]
    ]
    listed = employer.get(SELECTIONS).json()
    assert (listed[0]["exact_total"], listed[0]["nearby_total"]) == (1, 1)


def test_entry_grade_name_is_frozen_with_the_selection(
    employer: TestClient, db_engine: Engine
) -> None:
    seed(db_engine, [Seed(grade="senior")])
    built = build(employer, create_need(employer))

    with transaction(db_engine) as db:
        db.execute(update(Grade).where(Grade.code == "senior").values(name="Сеньор"))
    try:
        reopened = open_selection(employer, built["id"])
    finally:
        with transaction(db_engine) as db:
            db.execute(update(Grade).where(Grade.code == "senior").values(name="Senior"))

    assert reopened["entries"][0]["grade"] == {"code": "senior", "name": "Senior"}


def test_saved_selection_reopens_with_the_same_output(
    seeds: Seeds, signed_in: SignIn, employer: TestClient, db_engine: Engine, clock: FrozenClock
) -> None:
    seed(db_engine, [Seed(levels={"qa.api": (0.1 * i, 0.4)}) for i in range(5)])
    candidate = signed_in(Role.candidate)
    pass_test(candidate, seeds)
    need = create_need(employer)
    built = build(employer, need)

    # После построения меняется всё, из чего подборка строилась.
    candidate.put(PROFILE, json=profile_body(NEED_STACK)).raise_for_status()
    seed(db_engine, [Seed(levels={"qa.api": (3.0, 0.2)})])
    employer.put(f"{NEEDS}/{need}", json=need_body(grade="senior", stack=["java"]))

    assert open_selection(employer, built["id"]) == built
    assert built["need"]["grade"]["code"] == "middle"
    assert [s["code"] for s in built["need"]["stack"]] == NEED_STACK

    clock.shift(timedelta(minutes=5))
    rebuilt = build(employer, need)
    assert rebuilt["id"] != built["id"]
    assert rebuilt["need"]["grade"]["code"] == "senior"
    listed = employer.get(SELECTIONS, params={"need_id": need}).json()
    assert [s["id"] for s in listed] == [rebuilt["id"], built["id"]]


def test_selection_outlives_deleted_need(employer: TestClient, db_engine: Engine) -> None:
    seed(db_engine, [Seed()])
    need = create_need(employer)
    built = build(employer, need)

    employer.delete(f"{NEEDS}/{need}").raise_for_status()

    reopened = open_selection(employer, built["id"])
    assert reopened["need_id"] is None
    assert reopened == built | {"need_id": None}
    assert [s["id"] for s in employer.get(SELECTIONS).json()] == [built["id"]]


def test_selection_pages_through_output(employer: TestClient, db_engine: Engine) -> None:
    seed(db_engine, [Seed() for _ in range(5)] + [Seed(grade="senior") for _ in range(3)])
    need = create_need(employer)
    first = build(employer, need, limit=3)

    whole = open_selection(employer, first["id"], limit=100)["entries"]
    assert [e["position"] for e in whole] == list(range(1, 9))
    assert [e["block"] for e in whole] == ["exact"] * 5 + ["nearby"] * 3
    assert [e["rank"] for e in whole] == [1, 2, 3, 4, 5, 1, 2, 3]
    assert first["entries"] == whole[:3]
    assert open_selection(employer, first["id"], offset=4, limit=3)["entries"] == whole[4:7]
    assert open_selection(employer, first["id"], offset=8)["entries"] == []


def test_same_seed_gives_the_same_selection_including_ties(
    employer: TestClient, db_engine: Engine, seeds: Seeds
) -> None:
    """Порядок ничьих — от соли из `SeedSource`: тот же seed на тех же входах — та же выдача,
    другой seed — другой порядок ничьих."""
    seed(db_engine, [Seed() for _ in range(6)] + [Seed(grade="senior") for _ in range(3)])
    need = create_need(employer)

    def output(run_seed: int) -> list[tuple[str, str, int, float]]:
        seeds.reset(run_seed)
        entries = build(employer, need, limit=100)["entries"]
        return [(e["candidate_id"], e["block"], e["rank"], e["mutual_score"]) for e in entries]

    first = output(5)

    assert len({score for _, block, _, score in first if block == "exact"}) == 1, "все — ничьи"
    assert output(5) == first
    # Шанс совпасть порядку ничьих при другой соли — 1/(6!·3!).
    assert output(6) != first


def test_stale_profile_is_marked(
    employer: TestClient, db_engine: Engine, mechanics: Mechanics
) -> None:
    long_ago = datetime.now(UTC) - timedelta(days=mechanics.profile_stale_days + 1)
    fresh, stale = seed(db_engine, [Seed(), Seed(last_signal_at=long_ago)])

    selection = build(employer, create_need(employer))

    assert entry_of(selection, fresh)["stale"] is False
    assert entry_of(selection, stale)["stale"] is True


def test_selection_hides_who_the_candidate_is(
    signed_in: SignIn, employer: TestClient, seeds: Seeds
) -> None:
    candidate = signed_in(Role.candidate)
    pass_test(candidate, seeds)
    candidate.put(PROFILE, json=profile_body(NEED_STACK)).raise_for_status()

    response = employer.post(f"{NEEDS}/{create_need(employer)}/selections")

    # Вилка в ответе есть — это вилка потребности; ожидаемой зарплаты кандидата нет.
    for hidden in ("Ёлкина", "yulia@", "флаки", "тимлид", "287500", "full_name", "contact"):
        assert hidden not in response.text, hidden


def test_employer_sees_only_own_selections(
    signed_in: SignIn, employer: TestClient, db_engine: Engine
) -> None:
    seed(db_engine, [Seed()])
    need = create_need(employer)
    built = build(employer, need)
    other = signed_in(Role.employer)

    response = other.get(f"{SELECTIONS}/{built['id']}")
    assert response.status_code == 404
    assert response.json()["code"] == "selection_not_found"
    response = other.post(f"{NEEDS}/{need}/selections")
    assert response.status_code == 404
    assert response.json()["code"] == "need_not_found"
    assert other.get(SELECTIONS).json() == []
    assert other.get(SELECTIONS, params={"need_id": need}).json() == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"{NEEDS}/{{need}}/selections"),
        ("GET", SELECTIONS),
        ("GET", f"{SELECTIONS}/{{selection}}"),
    ],
)
def test_candidate_gets_403_on_selections_api(
    signed_in: SignIn, employer: TestClient, method: str, path: str
) -> None:
    need = create_need(employer)
    selection = build(employer, need)
    candidate = signed_in(Role.candidate)

    response = candidate.request(method, path.format(need=need, selection=selection["id"]))

    assert response.status_code == 403


def test_selection_on_1000_candidates_builds_within_a_second(
    employer: TestClient, db_engine: Engine
) -> None:
    grades = ["junior", "middle", "middle", "senior"]
    seed(
        db_engine,
        [
            Seed(
                grade=grades[i % 4],
                levels={"qa.api": ((i % 37) / 10 - 1.5, 0.3 + (i % 7) / 10)},
                stack=NEED_STACK[: i % 4],
            )
            for i in range(1000)
        ],
    )
    need = create_need(employer)
    build(employer, need)  # прогрев: соединения и планы запросов

    timings = []
    for _ in range(3):
        started = time.perf_counter()
        selection = build(employer, need)
        timings.append(time.perf_counter() - started)
        assert selection["exact_total"] + selection["nearby_total"] == 1000

    # Медиана трёх построений: разовая задержка машины — не регресс.
    elapsed = sorted(timings)[1]
    assert elapsed < 1.0, f"подборка на 1000 кандидатах строилась {elapsed:.2f} с"
