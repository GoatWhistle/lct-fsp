"""Поиск по банку кандидатов и уточнение подборки фильтрами через HTTP API (mechanics.md, §12):
семь фильтров в обоих путях, сброс, шортлист, приватность и права."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.domain.account import Role
from tests.test_selections import SELECTIONS, Seed, SignIn, build, create_need, open_selection, seed

SEARCH = "/api/employer/candidates/search"
Json = dict[str, Any]

# Карточке до раскрытия нельзя нести ни одно из этих полей (§14, §17).
PERSONAL = {
    "full_name",
    "contact_email",
    "contact_phone",
    "telegram",
    "about",
    "photo",
    "age",
    "birth_date",
    "university",
    "disclosed",
}


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return signed_in(Role.employer)


@pytest.fixture
def people(db_engine: Engine) -> dict[str, str]:
    """Потребность — middle QA. В подборке: A и B — точные, C — близкий, D — нижний блок; E —
    другой специализации, его находит только поиск."""
    a, b, c, d = seed(
        db_engine,
        [
            Seed(stack=["pytest"], fsp=True, overall_sd=0.3),
            Seed(stack=["python"], overall_sd=0.9),
            Seed(grade="junior", stack=["playwright"]),
            Seed(stack=["pytest"], confirmed=False),
        ],
    )
    (e,) = seed(db_engine, [Seed()], specialization="backend")
    return {"A": a, "B": b, "C": c, "D": d, "E": e}


def refine(c: TestClient, selection_id: str, filters: Json, **params: Any) -> Json:
    response = c.put(f"{SELECTIONS}/{selection_id}/filters", json=filters, params=params)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def search(c: TestClient, filters: Json, **params: Any) -> Json:
    response = c.post(SEARCH, json=filters, params=params)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def names(people: dict[str, str], ids: list[str]) -> set[str]:
    by_id = {v: k for k, v in people.items()}
    return {by_id[i] for i in ids}


SEVEN = [
    ({"specialization": "backend"}, set(), {"E"}),
    ({"grade": "junior"}, {"C"}, {"C"}),
    ({"category": {"specialization": "qa", "grade": "middle"}}, {"A", "B"}, {"A", "B"}),
    ({"stack": ["pytest"]}, {"A", "D"}, {"A", "D"}),
    ({"fsp_confirmed": True}, {"A"}, {"A"}),
    ({"confident": True}, {"A", "C"}, {"A", "C", "E"}),
    ({"grade_status": ["unconfirmed"]}, {"D"}, {"D"}),
]


@pytest.mark.parametrize(
    ("filters", "in_selection", "in_search"),
    SEVEN,
    ids=["specialization", "grade", "category", "stack", "fsp", "confident", "grade_status"],
)
def test_each_filter_narrows_selection_and_search(
    employer: TestClient,
    people: dict[str, str],
    filters: Json,
    in_selection: set[str],
    in_search: set[str],
) -> None:
    built = build(employer, create_need(employer))
    assert names(people, [e["candidate_id"] for e in built["entries"]]) == {"A", "B", "C", "D"}
    assert names(people, [e["candidate_id"] for e in search(employer, {})["entries"]]) == {
        "A",
        "B",
        "C",
        "D",
        "E",
    }

    refined = refine(employer, built["id"], filters)
    found = search(employer, filters)

    assert names(people, [e["candidate_id"] for e in refined["entries"]]) == in_selection
    assert names(people, [e["candidate_id"] for e in found["entries"]]) == in_search
    assert refined["filters"] == found["filters"]


def test_combination_is_intersection(employer: TestClient, people: dict[str, str]) -> None:
    built = build(employer, create_need(employer))
    filters = {"stack": ["pytest", "playwright"], "confident": True}

    refined = refine(employer, built["id"], filters)

    assert names(people, [e["candidate_id"] for e in refined["entries"]]) == {"A", "C"}
    assert names(people, [e["candidate_id"] for e in search(employer, filters)["entries"]]) == {
        "A",
        "C",
    }


def test_stack_filter_does_not_see_stack_hidden_from_card(
    employer: TestClient, db_engine: Engine
) -> None:
    """Иначе фильтр по одной технологии восстановил бы скрытый стек."""
    shown, hidden = seed(
        db_engine, [Seed(stack=["pytest"]), Seed(stack=["pytest"], hidden_stack=True)]
    )
    built = build(employer, create_need(employer))
    assert {e["candidate_id"] for e in built["entries"]} == {shown, hidden}

    filters = {"stack": ["pytest"]}

    assert [e["candidate_id"] for e in search(employer, filters)["entries"]] == [shown]
    assert [e["candidate_id"] for e in refine(employer, built["id"], filters)["entries"]] == [shown]


def test_refine_keeps_order_and_reset_restores_selection_byte_for_byte(
    employer: TestClient, people: dict[str, str]
) -> None:
    built = build(employer, create_need(employer))
    before = employer.get(f"{SELECTIONS}/{built['id']}").content

    refined = refine(employer, built["id"], {"stack": ["pytest", "playwright"]})

    original = [e for e in built["entries"] if e in refined["entries"]]
    assert refined["entries"] == original
    assert [e["position"] for e in refined["entries"]] == sorted(
        e["position"] for e in refined["entries"]
    )
    assert (refined["exact_total"], refined["nearby_total"], refined["unconfirmed_total"]) == (
        2,
        1,
        1,
    )
    assert (
        refined["filtered_exact_total"],
        refined["filtered_nearby_total"],
        refined["filtered_unconfirmed_total"],
    ) == (1, 1, 1)

    refine(employer, built["id"], {})
    assert employer.get(f"{SELECTIONS}/{built['id']}").content == before


def test_reopen_returns_last_filters_and_filtered_page(
    employer: TestClient, people: dict[str, str]
) -> None:
    built = build(employer, create_need(employer))
    filters = {"grade_status": ["unconfirmed"]}
    refine(employer, built["id"], filters)

    reopened = open_selection(employer, built["id"])

    assert reopened["filters"]["grade_status"] == ["unconfirmed"]
    assert [e["candidate_id"] for e in reopened["entries"]] == [people["D"]]


def test_search_never_puts_unconfirmed_above_confirmed(
    employer: TestClient, people: dict[str, str]
) -> None:
    found = search(employer, {})

    kinds = [e["grade_status"]["kind"] for e in found["entries"]]
    first_unconfirmed = kinds.index("unconfirmed")
    assert "unconfirmed" not in kinds[:first_unconfirmed]
    assert all(k == "unconfirmed" for k in kinds[first_unconfirmed:])
    assert (found["total"], found["unconfirmed_total"]) == (5, 1)
    assert [e["position"] for e in found["entries"]] == [1, 2, 3, 4, 5]
    bottom = found["entries"][-1]
    assert (bottom["theta"], bottom["grade_probability"]) == (None, None)
    assert search(employer, {}, offset=1, limit=2)["entries"] == found["entries"][1:3]


def test_shortlist_add_remove_reopen(employer: TestClient, people: dict[str, str]) -> None:
    built = build(employer, create_need(employer))
    shortlist = f"{SELECTIONS}/{built['id']}/shortlist"

    for who in ("C", "A", "B"):
        assert employer.put(f"{shortlist}/{people[who]}").status_code == 200
    removed = employer.delete(f"{shortlist}/{people['B']}")
    assert removed.status_code == 200
    refine(employer, built["id"], {"fsp_confirmed": True})

    listed = employer.get(shortlist).json()
    # В порядке выдачи: A — точный, C — близкий; фильтр C из шортлиста не убирает.
    assert [e["candidate_id"] for e in listed["entries"]] == [people["A"], people["C"]]
    assert open_selection(employer, built["id"])["shortlist"] == [people["A"], people["C"]]


def test_shortlist_rejects_candidate_outside_selection(
    employer: TestClient, people: dict[str, str]
) -> None:
    built = build(employer, create_need(employer))

    response = employer.put(f"{SELECTIONS}/{built['id']}/shortlist/{people['E']}")

    assert response.status_code == 404
    assert response.json()["code"] == "not_in_selection"


def test_foreign_selection_is_refused(
    signed_in: SignIn, employer: TestClient, people: dict[str, str]
) -> None:
    built = build(employer, create_need(employer))
    other = signed_in(Role.employer)

    for response in (
        other.put(f"{SELECTIONS}/{built['id']}/filters", json={}),
        other.get(f"{SELECTIONS}/{built['id']}/shortlist"),
        other.put(f"{SELECTIONS}/{built['id']}/shortlist/{people['A']}"),
        other.delete(f"{SELECTIONS}/{built['id']}/shortlist/{people['A']}"),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "selection_not_found"


def test_search_and_refine_answers_carry_no_personal_data(
    employer: TestClient, people: dict[str, str]
) -> None:
    """Сид кандидата заполнил ФИО и контакты — ни ответ, ни схема их не несут."""
    built = build(employer, create_need(employer))
    answers = [
        search(employer, {}),
        refine(employer, built["id"], {"stack": ["pytest"]}),
        employer.put(f"{SELECTIONS}/{built['id']}/shortlist/{people['A']}").json(),
    ]
    for answer in answers:
        assert "Сидов" not in str(answer)
        assert "seed@example.com" not in str(answer)
        assert not PERSONAL & set(_keys(answer))

    schemas = employer.get("/api/openapi.json").json()["components"]["schemas"]
    for name in ("SearchOut", "SearchHitOut", "SelectionOut", "ShortlistOut", "SelectionEntryOut"):
        assert not PERSONAL & set(schemas[name]["properties"]), name


def _keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [*value, *(k for v in value.values() for k in _keys(v))]
    if isinstance(value, list):
        return [k for v in value for k in _keys(v)]
    return []


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", SEARCH), ("put", f"{SELECTIONS}/00000000-0000-0000-0000-000000000000/filters")],
)
def test_candidate_gets_403_on_search_and_refine(signed_in: SignIn, method: str, path: str) -> None:
    candidate = signed_in(Role.candidate)

    assert getattr(candidate, method)(path, json={}).status_code == 403
