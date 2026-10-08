"""Карточка опыта через HTTP API (mechanics.md, §11): кандидат сохраняет и читает записи, годы по
технологиям считаются из них, а на подбор, уровень, категорию и подсказку грейда карточка не
влияет. Кому она видна — в `test_visibility.py` вместе с остальным раскрываемым."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from app.domain.experience import Month
from settings import Mechanics
from tests.candidate_path import grant_category, with_company

PROFILE = "/api/candidate/profile"
Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


def profile_body(**changes: Any) -> Json:
    body: Json = {
        "full_name": "Ёлкина Юлия Сергеевна",
        "contact_email": "yulia@example.ru",
        "stack": ["pytest"],
        "experience_years": 4,
        "work_formats": ["remote"],
        "salary_from": 250_000,
    }
    return body | changes


def entry(**changes: Any) -> Json:
    body: Json = {
        "place": "  ООО «Ромашка»  ",
        "role": "QA-инженер",
        "start": "2019-01",
        "end": "2020-12",
        "stack": ["python", "pytest"],
        "summary": "Автотесты платёжного шлюза",
    }
    return body | changes


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


def save(c: TestClient, *entries: Json) -> Json:
    response = c.put(PROFILE, json=profile_body(experience=list(entries)))
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def test_candidate_saves_and_reads_experience_with_years_by_technology(
    candidate: TestClient, clock: FrozenClock
) -> None:
    saved = save(
        candidate,
        entry(),
        # С середины 2020 — полгода пересечения по Python с первой записью: не дважды.
        entry(
            place="Подработка",
            role="",
            start="2020-07",
            end=None,
            stack=["python", "go"],
            summary="",
        ),
    )

    assert saved == candidate.get(PROFILE).json()
    first, second = saved["experience"]
    assert first == {
        "place": "ООО «Ромашка»",
        "role": "QA-инженер",
        "start": "2019-01",
        "end": "2020-12",
        "stack": [{"code": "python", "name": "Python"}, {"code": "pytest", "name": "pytest"}],
        "summary": "Автотесты платёжного шлюза",
    }
    assert (second["end"], second["role"]) == (None, "")
    # Открытая запись — по текущий месяц часов: с 2020-07 включительно.
    open_months = Month.of(clock.now().date()).index - Month(2020, 7).index + 1
    python_months = 18 + open_months
    years = {y["technology"]["code"]: y["years"] for y in saved["technology_years"]}
    assert years == {
        "python": python_months // 6 / 2,
        "go": open_months // 6 / 2,
        "pytest": 2.0,
    }
    assert [y["technology"]["code"] for y in saved["technology_years"]][-1] == "pytest"


def test_profile_without_experience_has_empty_card(candidate: TestClient) -> None:
    saved = candidate.put(PROFILE, json=profile_body()).json()

    assert (saved["experience"], saved["technology_years"]) == ([], [])


def test_saving_profile_replaces_the_card(candidate: TestClient) -> None:
    save(candidate, entry(), entry(place="Подработка"))

    saved = save(candidate, entry(place="Другая компания"))

    assert [e["place"] for e in saved["experience"]] == ["Другая компания"]


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        (entry(start="2021-01", end="2020-12"), "experience_period_invalid"),
        (entry(start="2099-01", end=None), "experience_start_in_future"),
        (entry(stack=["cobol"]), "unknown_technology"),
        (entry(place="Я" * 201), "experience_too_long"),
        (entry(summary="Я" * 2001), "experience_too_long"),
        (entry(stack=[f"x{i}" for i in range(31)]), "experience_too_long"),
    ],
    ids=[
        "начало позже конца",
        "начало в будущем",
        "не из справочника",
        "место",
        "что делал",
        "стек",
    ],
)
def test_invalid_entry_is_a_clear_422(candidate: TestClient, bad: Json, code: str) -> None:
    response = candidate.put(PROFILE, json=profile_body(experience=[bad]))

    assert response.status_code == 422, response.text
    assert response.json()["code"] == code


def test_too_many_entries_is_a_clear_422(candidate: TestClient, mechanics: Mechanics) -> None:
    entries = [entry()] * (mechanics.experience_entries_max + 1)

    response = candidate.put(PROFILE, json=profile_body(experience=entries))

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "experience_too_long"


@pytest.mark.parametrize(
    "bad",
    [
        entry(start="2021-13"),
        entry(start="03.2021"),
        entry(end="2021"),
        entry(place="   "),
        entry(start="0001-01"),
    ],
    ids=["месяц 13", "не ГГГГ-ММ", "конец без месяца", "без места", "год до 1900"],
)
def test_malformed_entry_is_rejected_by_the_schema(candidate: TestClient, bad: Json) -> None:
    response = candidate.put(PROFILE, json=profile_body(experience=[bad]))

    assert response.status_code == 422, response.text


def test_invalid_card_does_not_change_the_saved_profile(candidate: TestClient) -> None:
    before = save(candidate, entry())

    candidate.put(PROFILE, json=profile_body(experience=[entry(stack=["cobol"])]))

    assert candidate.get(PROFILE).json() == before


# Нейтральность: карточка — показ без веса.


def candidate_with_category(signed_in: SignIn, db_engine: Engine, *entries: Json) -> str:
    c = signed_in(Role.candidate)
    save(c, *entries)
    user_id: str = c.get("/api/auth/me").json()["id"]
    grant_category(db_engine, user_id)
    return user_id


def test_card_does_not_change_score_or_place_in_selection(
    signed_in: SignIn, db_engine: Engine, clock: FrozenClock
) -> None:
    """Два кандидата при прочих равных — с богатой карточкой и без: один скор и никого между
    ними. Карточка набита тем, что ищет потребность: технологии, роль, годы."""
    rich = entry(
        role="Ведущий QA-инженер",
        start="2005-01",
        end=None,
        stack=["pytest", "selenium", "playwright", "python"],
    )
    with_card = candidate_with_category(signed_in, db_engine, rich, rich | {"place": "Яндекс"})
    without = candidate_with_category(signed_in, db_engine)
    employer = with_company(signed_in(Role.employer))
    need = employer.post(
        "/api/employer/needs",
        json={
            "title": "QA-инженер",
            "specialization": "qa",
            "grade": "middle",
            "stack": ["pytest", "selenium", "playwright"],
            "work_format": "remote",
        },
    )
    need.raise_for_status()

    selection = employer.post(f"/api/employer/needs/{need.json()['id']}/selections")

    assert selection.status_code == 201, selection.text
    entries = selection.json()["entries"]
    scores = {e["candidate_id"]: e["match_score"] for e in entries}
    order = [e["candidate_id"] for e in entries]
    assert scores[with_card] == scores[without]
    assert abs(order.index(with_card) - order.index(without)) == 1


def test_card_does_not_change_level_category_or_grade_hint(
    candidate: TestClient, signed_in: SignIn, db_engine: Engine
) -> None:
    user_id: str = candidate.get("/api/auth/me").json()["id"]
    candidate.put(PROFILE, json=profile_body()).raise_for_status()
    grant_category(db_engine, user_id)
    employer = signed_in(Role.employer)

    def state() -> tuple[Json, Json]:
        card = employer.get(f"/api/employer/candidates/{user_id}").json()
        hint = candidate.get(f"{PROFILE}/grade-hint").json()
        return {k: card[k] for k in ("category", "grade_status", "skill_profile")}, hint

    before = state()
    save(
        candidate,
        entry(role="Тимлид", start="2000-01", end=None, stack=["pytest", "selenium"]),
    )

    assert state() == before
