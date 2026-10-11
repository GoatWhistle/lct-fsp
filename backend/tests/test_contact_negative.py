"""Негатив контактов (mechanics.md, §14, §17): до принятия приглашения или отклика работодатель не
получает ФИО, email, телефон, telegram и свободный текст кандидата ни от одной ручки, где
кандидат ему виден, — поиск, уточнение подборки, шортлист, подсказка по зарплате, приглашение с
перепиской, чат-поиск. Матрица `test_visibility` держит карточку, подборку, приглашения и
отклики; здесь — остальные ручки, прямые обращения по id и раскрытие после принятия. В анкете нет
фото, возраста и вуза, и в схемах ответов работодателя таких полей тоже нет."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.account import Role
from app.usecase.chat import SearchChat
from main import create_app
from tests.candidate_path import with_company
from tests.test_visibility import (  # noqa: F401
    DISCLOSED_TO_EMPLOYER,
    SECRETS,
    Viewer,
    World,
    world,
)

Json = dict[str, Any]
SELECTIONS = "/api/employer/selections"
INVITATIONS = "/api/employer/invitations"
PERSONAL_KEYS = {
    "full_name",
    "contact_email",
    "contact_phone",
    "telegram",
    "about",
    "photo",
    "avatar",
    "age",
    "birth_date",
    "university",
    "disclosed",
}
TERMS = {
    "description": "Автотесты платёжного шлюза",
    "salary_from": 250_000,
    "salary_to": 300_000,
    "contact": "@pay_hr",
}
CHAT_REPLY = json.dumps(
    {
        "need_text": "Ищем Middle QA-инженера. Стек: pytest. Удалённо.",
        "filters": {
            "stack": [],
            "fsp_confirmed": False,
            "confident": False,
            "grade": None,
            "specialization": None,
        },
        "summary": "Нашлись кандидаты.",
    }
)


def employer_of(world: World) -> TestClient:
    return world.clients[Viewer.employer]


def keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


def leaked(text: str) -> set[str]:
    return {name for name, marker in SECRETS.items() if marker in text} - {"зарплата"}


def invite(world: World) -> str:
    response = employer_of(world).post(
        INVITATIONS, json=TERMS | {"candidate_id": world.candidate_id}
    )
    assert response.status_code == 201, response.text
    invitation_id: str = response.json()["id"]
    return invitation_id


def accept(world: World, invitation_id: str) -> None:
    candidate = world.clients[Viewer.me]
    candidate.post(f"/api/candidate/invitations/{invitation_id}/accept").raise_for_status()


def with_scripted_chat(app: FastAPI) -> None:
    original = app.state.search_chat

    def scripted(uow: Any) -> SearchChat:
        chat: SearchChat = original(uow)
        chat._complete = lambda request: CHAT_REPLY
        return chat

    app.state.search_chat = scripted


def calls(world: World, invitation_id: str) -> dict[str, Callable[[], Any]]:
    c, selection = employer_of(world), f"{SELECTIONS}/{world.selection_id}"
    return {
        "поиск": lambda: c.post("/api/employer/candidates/search"),
        "поиск с фильтром": lambda: c.post(
            "/api/employer/candidates/search", json={"stack": ["pytest"]}
        ),
        "уточнение подборки": lambda: c.put(f"{selection}/filters", json={"stack": ["pytest"]}),
        "шортлист: добавить": lambda: c.put(f"{selection}/shortlist/{world.candidate_id}"),
        "шортлист: список": lambda: c.get(f"{selection}/shortlist"),
        "подсказка по зарплате": lambda: c.get(
            f"{selection}/candidates/{world.candidate_id}/salary-hint"
        ),
        "приглашение": lambda: c.get(f"{INVITATIONS}/{invitation_id}"),
        "переписка": lambda: c.get(f"{INVITATIONS}/{invitation_id}/messages"),
        "чат-поиск": lambda: c.post("/api/employer/chat", json={"message": "Нужен QA"}),
    }


ENDPOINTS = (
    "поиск",
    "поиск с фильтром",
    "уточнение подборки",
    "шортлист: добавить",
    "шортлист: список",
    "подсказка по зарплате",
    "приглашение",
    "переписка",
    "чат-поиск",
)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_no_endpoint_gives_employer_contacts_before_acceptance(
    world: World, app: FastAPI, endpoint: str
) -> None:
    with_scripted_chat(app)
    invitation_id = invite(world)

    response = calls(world, invitation_id)[endpoint]()

    assert response.status_code < 500, response.text
    assert leaked(response.text) == set(), endpoint
    assert not PERSONAL_KEYS & keys(response.json()), endpoint


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_lists_stay_anonymized_after_acceptance_and_only_the_card_discloses(
    world: World, app: FastAPI, endpoint: str
) -> None:
    with_scripted_chat(app)
    invitation_id = invite(world)
    accept(world, invitation_id)

    response = calls(world, invitation_id)[endpoint]()

    assert response.status_code < 500, response.text
    assert leaked(response.text) == set(), endpoint


def test_card_by_id_is_anonymized_until_accepted_and_disclosed_after(world: World) -> None:
    card = f"/api/employer/candidates/{world.candidate_id}"
    employer = employer_of(world)

    assert leaked(employer.get(card).text) == set()

    accept(world, invite(world))

    disclosed = employer.get(card)
    assert {n for n, m in SECRETS.items() if m in disclosed.text} == DISCLOSED_TO_EMPLOYER


def test_declined_and_unanswered_invitations_do_not_disclose(world: World) -> None:
    card = f"/api/employer/candidates/{world.candidate_id}"
    candidate = world.clients[Viewer.me]
    invitation_id = invite(world)
    assert leaked(employer_of(world).get(card).text) == set()

    candidate.post(f"/api/candidate/invitations/{invitation_id}/decline").raise_for_status()

    assert leaked(employer_of(world).get(card).text) == set()


def test_unknown_candidate_id_is_not_found_not_a_card(world: World) -> None:
    response = employer_of(world).get(
        "/api/employer/candidates/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


def test_other_company_cannot_read_invitation_or_conversation(
    world: World, signed_in: Callable[[Any], TestClient]
) -> None:
    invitation_id = invite(world)
    accept(world, invitation_id)
    stranger = with_company(signed_in(Role.employer), "Чужая компания")

    for path in (f"{INVITATIONS}/{invitation_id}", f"{INVITATIONS}/{invitation_id}/messages"):
        response = stranger.get(path)
        assert response.status_code == 404, path
        assert leaked(response.text) == set()
    card = stranger.get(f"/api/employer/candidates/{world.candidate_id}")
    assert leaked(card.text) == set(), "приглашение чужой компании не раскрывает карточку"


def test_employer_schemas_carry_no_personal_fields_except_the_card_itself() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    for name in (
        "SearchOut",
        "SearchHitOut",
        "SelectionOut",
        "SelectionEntryOut",
        "ShortlistOut",
        "ChatOut",
        "CardOut",
        "AnonymizedCardOut",
    ):
        if name in schemas:
            assert not PERSONAL_KEYS & set(schemas[name].get("properties", {})), name
