"""ФСП ID и достижения ФСП через HTTP API (mechanics.md, §11): вход и привязка, отвязка, снимок
реестра, вклад в профиль навыков и подборку, видимость. ФСП ID и реестр — в памяти."""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.exc import IntegrityError

from app.adapter.fsp_id import MemoryFspId, OidcFspId
from app.adapter.fsp_registry import MemoryFspRegistry
from app.domain.account import Role
from app.domain.candidate import (
    NO_ACCESS,
    Access,
    AnonymizedCard,
    Candidate,
    DisclosedCard,
    EmployerViewer,
    disclosure,
)
from app.domain.catalog import CatalogRef
from app.domain.errors import FspIdUnavailable
from app.domain.fsp import (
    AnonymizedAchievement,
    ConfirmedAchievement,
    FspAchievement,
    FspAuthorization,
    FspHistory,
    FspIdentity,
    FspIntent,
    FspResult,
)
from app.repository.orm import User
from tests.candidate_path import answer_items, nothing, pass_test, start, take_survey, with_company
from tests.conftest import PASSWORD, Seeds, transaction
from tests.test_invitations import answer, invite
from tests.test_selections import build, create_need, entry_of

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]
FSP = "/api/candidate/fsp"
AUTHORIZE = "/api/auth/fsp/authorize"
CALLBACK = "/api/auth/fsp/callback"
FRONT = "http://front.test"

WINNER = FspAchievement(
    event="Чемпионат России по продуктовому программированию",
    date=date(2025, 4, 12),
    discipline="product",
    place=1,
    result=FspResult.winner,
    team_role="qa",
)
QUALIFIER = FspAchievement(
    event="Кубок ФСП по алгоритмическому программированию",
    date=date(2024, 3, 2),
    discipline="algorithmic",
    place=None,
    result=FspResult.participant,
    team_role=None,
)
# Темы QA, о которых говорит продуктовое программирование.
PRODUCT_QA = {"qa.theory", "qa.api", "qa.automation"}


def identity(email: str | None = None, *, verified: bool = True) -> FspIdentity:
    sub = str(uuid.uuid4())
    return FspIdentity(sub, email or f"{sub[:8]}@fsp-id.example", verified)


def via_fsp_id(
    c: TestClient, fsp_id: MemoryFspId, who: FspIdentity, intent: str = "login"
) -> tuple[str, dict[str, list[str]]]:
    """Полный круг через ФСП ID: начать, «войти» участником, вернуться в callback. Отдаёт
    страницу фронта, куда ведёт возврат, и её параметры."""
    started = c.post(AUTHORIZE, json={"intent": intent})
    assert started.status_code == 200, started.text
    state = parse_qs(urlsplit(started.json()["authorization_url"]).query)["state"][0]
    back = c.get(
        CALLBACK,
        params={"state": state, "code": fsp_id.issue(who, state)},
        follow_redirects=False,
    )
    assert back.status_code == 303, back.text
    location = urlsplit(back.headers["location"])
    assert f"{location.scheme}://{location.netloc}" == FRONT
    return location.path, parse_qs(location.query)


def status(c: TestClient) -> Json:
    response = c.get(FSP)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def topics(path: Json) -> dict[str, Json]:
    return {t["topic"]["code"]: t for t in path["profile"]["topics"]}


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


def linked(c: TestClient, fsp_id: MemoryFspId, who: FspIdentity | None = None) -> FspIdentity:
    who = who or identity()
    page, query = via_fsp_id(c, fsp_id, who, intent="link")
    assert (page, query) == ("/candidate/profile", {"fsp": ["linked"]})
    return who


def test_fsp_id_login_from_scratch_creates_candidate_and_returns_to_it(
    client: TestClient, new_client: Callable[[], TestClient], fsp_id: MemoryFspId
) -> None:
    who = identity()

    page, query = via_fsp_id(client, fsp_id, who)

    assert (page, query) == ("/", {})
    me = client.get("/api/auth/me").json()
    assert me["role"] == "candidate"
    assert me["email"] == who.email
    assert me["email_verified"]
    found = status(client)
    assert (found["linked"], found["fsp_id"], found["can_unlink"]) == (True, who.sub, False)

    again = new_client()
    via_fsp_id(again, fsp_id, who)
    assert again.get("/api/auth/me").json()["id"] == me["id"]


def test_fsp_created_account_has_no_password_login(client: TestClient, fsp_id: MemoryFspId) -> None:
    who = identity()
    via_fsp_id(client, fsp_id, who)

    response = client.post("/api/auth/login", json={"email": who.email, "password": PASSWORD})

    assert response.json()["code"] == "invalid_credentials"


def test_fsp_id_login_with_email_of_existing_account_is_refused(
    candidate: TestClient,
    new_client: Callable[[], TestClient],
    fsp_id: MemoryFspId,
    db_engine: Engine,
) -> None:
    email = candidate.get("/api/auth/me").json()["email"]
    with transaction(db_engine) as db:
        before = db.scalar(select(func.count()).select_from(User))

    page, query = via_fsp_id(new_client(), fsp_id, identity(email.upper()))

    assert (page, query) == ("/login", {"fsp_error": ["fsp_email_taken"]})
    with transaction(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == before
        assert db.scalar(select(User.fsp_id).where(User.email == email)) is None


def test_fsp_id_login_without_verified_email_is_refused(
    client: TestClient, fsp_id: MemoryFspId
) -> None:
    page, query = via_fsp_id(client, fsp_id, identity(verified=False))

    assert (page, query) == ("/login", {"fsp_error": ["fsp_email_unverified"]})
    assert client.get("/api/auth/me").status_code == 401


def test_return_with_foreign_state_is_refused(client: TestClient, fsp_id: MemoryFspId) -> None:
    client.post(AUTHORIZE, json={"intent": "login"})

    back = client.get(
        CALLBACK,
        params={"state": "чужой", "code": fsp_id.issue(identity(), "чужой")},
        follow_redirects=False,
    )

    assert back.headers["location"] == f"{FRONT}/login?fsp_error=fsp_authorization_invalid"
    assert client.get("/api/auth/me").status_code == 401


def test_unavailable_fsp_id_is_a_clear_error_and_email_login_still_works(
    signed_in: SignIn, client: TestClient, fsp_id: MemoryFspId
) -> None:
    fsp_id.available = False

    response = client.post(AUTHORIZE, json={"intent": "login"})

    assert response.status_code == 503
    assert response.json()["code"] == "fsp_id_unavailable"
    assert signed_in(Role.candidate).get("/api/auth/me").status_code == 200


def test_link_needs_signed_in_candidate(
    client: TestClient, signed_in: SignIn, fsp_id: MemoryFspId
) -> None:
    anonymous = client.post(AUTHORIZE, json={"intent": "link"})
    employer = signed_in(Role.employer).post(AUTHORIZE, json={"intent": "link"})

    assert anonymous.json()["code"] == "not_authenticated"
    assert employer.json()["code"] == "wrong_role"


def test_link_attaches_fsp_id_and_its_achievements(
    candidate: TestClient, fsp_id: MemoryFspId, fsp_registry: MemoryFspRegistry
) -> None:
    who = identity()
    fsp_registry.records[who.sub] = [QUALIFIER, WINNER]

    linked(candidate, fsp_id, who)

    found = status(candidate)
    assert found["linked"] and found["fsp_id"] == who.sub and found["can_unlink"]
    assert found["fetched_at"] is not None
    assert found["achievements"][1] == {
        "event": WINNER.event,
        "date": "2025-04-12",
        "discipline": {"code": "product", "name": "Продуктовое программирование"},
        "place": 1,
        "result": "winner",
        "team_role": {"code": "qa", "name": "QA"},
    }
    assert found["achievements"][0]["result"] == "participant"


def test_one_fsp_id_cannot_be_linked_to_two_candidates(
    signed_in: SignIn, fsp_id: MemoryFspId
) -> None:
    first, second = signed_in(Role.candidate), signed_in(Role.candidate)
    who = linked(first, fsp_id)

    page, query = via_fsp_id(second, fsp_id, who, intent="link")

    assert (page, query) == ("/candidate/profile", {"fsp_error": ["fsp_id_taken"]})
    assert not status(second)["linked"]


def test_database_keeps_fsp_id_unique(
    signed_in: SignIn, fsp_id: MemoryFspId, db_engine: Engine
) -> None:
    first, second = signed_in(Role.candidate), signed_in(Role.candidate)
    who = linked(first, fsp_id)
    other = uuid.UUID(second.get("/api/auth/me").json()["id"])

    with pytest.raises(IntegrityError), transaction(db_engine) as db:
        db.execute(update(User).where(User.id == other).values(fsp_id=who.sub))


def test_second_fsp_id_needs_unlinking_the_first(
    candidate: TestClient, fsp_id: MemoryFspId
) -> None:
    first = linked(candidate, fsp_id)

    _, query = via_fsp_id(candidate, fsp_id, identity(), intent="link")

    assert query == {"fsp_error": ["fsp_already_linked"]}
    assert status(candidate)["fsp_id"] == first.sub


def test_unlink_is_refused_for_account_without_password(
    client: TestClient, fsp_id: MemoryFspId
) -> None:
    via_fsp_id(client, fsp_id, identity())

    response = client.delete(FSP)

    assert response.status_code == 409
    assert response.json()["code"] == "fsp_unlink_forbidden"
    assert status(client)["linked"]


def test_unlink_removes_snapshot_and_fsp_observations(
    candidate: TestClient, seeds: Seeds, fsp_id: MemoryFspId, fsp_registry: MemoryFspRegistry
) -> None:
    path = pass_test(candidate, seeds)
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    linked(candidate, fsp_id, who)

    response = candidate.delete(FSP)

    assert response.status_code == 200, response.text
    assert response.json() | {"can_unlink": True} == {
        "linked": False,
        "fsp_id": None,
        "can_unlink": True,
        "fetched_at": None,
        "achievements": [],
        "divergences": [],
    }
    after = candidate.get("/api/candidate/path").json()
    assert after["profile"]["topics"] == path["profile"]["topics"]
    # ID свободен: его можно привязать снова.
    linked(candidate, fsp_id, who)


def test_link_narrows_mapped_topics_and_selection_says_confirmed_by_fsp(
    candidate: TestClient,
    signed_in: SignIn,
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    before = topics(pass_test(candidate, seeds))
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]

    linked(candidate, fsp_id, who)

    after = topics(candidate.get("/api/candidate/path").json())
    for code, row in after.items():
        if code in PRODUCT_QA:
            assert row["level"]["theta_sd"] < before[code]["level"]["theta_sd"]
            assert row["sources"] == ["fsp", "test"]
        else:
            assert "fsp" not in row["sources"]
    employer = signed_in(Role.employer)
    selection = build(employer, create_need(employer))
    me = candidate.get("/api/auth/me").json()["id"]
    confirmed = {
        t["topic"]["code"] for t in entry_of(selection, me)["topics"] if t["fsp_confirmed"]
    }
    assert confirmed == PRODUCT_QA


def test_fsp_does_not_change_category_or_test_result(
    candidate: TestClient, seeds: Seeds, fsp_id: MemoryFspId, fsp_registry: MemoryFspRegistry
) -> None:
    path = pass_test(candidate, seeds, grade="junior")
    who = identity()
    fsp_registry.records[who.sub] = [WINNER, WINNER, WINNER]

    linked(candidate, fsp_id, who)

    after = candidate.get("/api/candidate/path").json()
    assert after["category"] == path["category"]
    assert after["result"] == path["result"]


def test_candidate_without_fsp_keeps_the_same_score_when_others_link(
    signed_in: SignIn, seeds: Seeds, fsp_id: MemoryFspId, fsp_registry: MemoryFspRegistry
) -> None:
    plain, other = signed_in(Role.candidate), signed_in(Role.candidate)
    pass_test(plain, seeds)
    pass_test(other, seeds)
    employer = signed_in(Role.employer)
    need = create_need(employer)
    plain_id = plain.get("/api/auth/me").json()["id"]
    before = entry_of(build(employer, need), plain_id)

    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    linked(other, fsp_id, who)

    after = entry_of(build(employer, need), plain_id)
    assert after["match_score"] == before["match_score"]
    assert after["topics"] == before["topics"]
    assert status(plain)["linked"] is False


def test_divergence_is_seen_by_candidate_only_and_does_not_lower_profile(
    candidate: TestClient,
    signed_in: SignIn,
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    take_survey(candidate)
    start(candidate, "intern")
    path = answer_items(candidate, seeds, nothing)
    before = topics(path)
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]

    linked(candidate, fsp_id, who)

    divergences = status(candidate)["divergences"]
    assert {d["topic"]["code"] for d in divergences} == PRODUCT_QA
    for d in divergences:
        assert d["result"] == "winner"
        assert d["result_level"] - d["test_level"] > 1.0
    after = topics(candidate.get("/api/candidate/path").json())
    for code in before:
        assert after[code]["level"]["theta"] >= before[code]["level"]["theta"]


def test_unavailable_registry_keeps_last_snapshot_for_profile_and_selection(
    candidate: TestClient,
    signed_in: SignIn,
    new_client: Callable[[], TestClient],
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    pass_test(candidate, seeds)
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    linked(candidate, fsp_id, who)
    snapshot = status(candidate)
    fsp_registry.available = False

    refreshed = candidate.post(f"{FSP}/refresh")

    assert refreshed.status_code == 503
    assert refreshed.json()["code"] == "fsp_registry_unavailable"
    assert status(candidate) == snapshot
    assert snapshot["fetched_at"] is not None
    employer = signed_in(Role.employer)
    me = candidate.get("/api/auth/me").json()["id"]
    entry = entry_of(build(employer, create_need(employer)), me)
    assert {t["topic"]["code"] for t in entry["topics"] if t["fsp_confirmed"]} == PRODUCT_QA


def test_fsp_login_while_registry_is_down_keeps_account_and_last_snapshot(
    client: TestClient,
    new_client: Callable[[], TestClient],
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    via_fsp_id(client, fsp_id, who)
    fsp_registry.available = False

    again = new_client()
    page, _ = via_fsp_id(again, fsp_id, who)

    assert page == "/"
    assert status(again)["achievements"] == status(client)["achievements"] != []


def test_refresh_takes_new_snapshot(
    candidate: TestClient, fsp_id: MemoryFspId, fsp_registry: MemoryFspRegistry
) -> None:
    who = linked(candidate, fsp_id)
    assert status(candidate)["achievements"] == []
    fsp_registry.records[who.sub] = [WINNER]

    refreshed = candidate.post(f"{FSP}/refresh")

    assert refreshed.status_code == 200, refreshed.text
    assert [a["result"] for a in refreshed.json()["achievements"]] == ["winner"]


def test_employer_card_shows_only_result_discipline_and_year(
    candidate: TestClient,
    signed_in: SignIn,
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    pass_test(candidate, seeds)
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    linked(candidate, fsp_id, who)
    me = candidate.get("/api/auth/me").json()["id"]

    card = signed_in(Role.employer).get(f"/api/employer/candidates/{me}").json()

    assert card["fsp_achievements"] == [
        {
            "result": "winner",
            "discipline": {"code": "product", "name": "Продуктовое программирование"},
            "year": 2025,
        }
    ]
    assert "divergences" not in card
    assert WINNER.event not in str(card)


def test_fsp_endpoints_are_for_candidates_only(signed_in: SignIn) -> None:
    employer = signed_in(Role.employer)

    assert employer.get(FSP).status_code == 403
    assert employer.post(f"{FSP}/refresh").status_code == 403
    assert employer.delete(FSP).status_code == 403


def test_candidate_without_fsp_sees_neutral_status(candidate: TestClient) -> None:
    assert status(candidate) == {
        "linked": False,
        "fsp_id": None,
        "can_unlink": True,
        "fetched_at": None,
        "achievements": [],
        "divergences": [],
    }
    assert candidate.post(f"{FSP}/refresh").json()["code"] == "fsp_not_linked"


def test_disclosed_card_and_pdf_sheet_carry_full_achievements() -> None:
    """После принятия приглашения или отклика работодатель видит мероприятие, место и команду;
    обезличенная карточка — только тип результата, дисциплину и год."""
    confirmed = ConfirmedAchievement(
        event=WINNER.event,
        date=WINNER.date,
        discipline=CatalogRef("product", "Продуктовое программирование"),
        place=1,
        result=FspResult.winner,
        team_role=CatalogRef("qa", "QA"),
    )
    candidate = Candidate(uuid.uuid4(), None, None, None, None, fsp=FspHistory((confirmed,), None))
    employer = EmployerViewer(uuid.uuid4())

    hidden = disclosure(candidate, employer, NO_ACCESS)
    shown = disclosure(candidate, employer, Access(invitation_accepted=True))

    assert isinstance(hidden, AnonymizedCard)
    assert hidden.fsp_achievements == (
        AnonymizedAchievement(FspResult.winner, confirmed.discipline, 2025),
    )
    assert isinstance(shown, DisclosedCard)
    assert shown.fsp_achievements == (confirmed,)


def test_link_goes_only_to_the_candidate_who_started_it(
    signed_in: SignIn, fsp_id: MemoryFspId
) -> None:
    """Пока кандидат был в ФСП ID, в браузере вошёл другой: ID не привязывается ни к кому."""
    first, second = signed_in(Role.candidate), signed_in(Role.candidate)
    started = first.post(AUTHORIZE, json={"intent": "link"})
    state = parse_qs(urlsplit(started.json()["authorization_url"]).query)["state"][0]
    second.cookies.set("fsp_authorization", first.cookies["fsp_authorization"])

    back = second.get(
        CALLBACK,
        params={"state": state, "code": fsp_id.issue(identity(), state)},
        follow_redirects=False,
    )

    assert back.headers["location"] == (
        f"{FRONT}/candidate/profile?fsp_error=fsp_authorization_invalid"
    )
    assert not status(first)["linked"]
    assert not status(second)["linked"]


def test_unexpected_callback_parameters_still_return_to_the_front(client: TestClient) -> None:
    back = client.get(
        CALLBACK, params={"state": "x" * 5000, "code": "y" * 10000}, follow_redirects=False
    )

    assert back.status_code == 303
    assert back.headers["location"] == f"{FRONT}/login?fsp_error=fsp_authorization_invalid"


@pytest.mark.parametrize(
    "discovery",
    [httpx.Response(200, json=["не discovery"]), httpx.Response(200, json={"issuer": "x"})],
    ids=["not-an-object", "no-endpoints"],
)
def test_broken_discovery_is_unavailable_fsp_id(
    monkeypatch: pytest.MonkeyPatch, discovery: httpx.Response
) -> None:
    discovery.request = httpx.Request("GET", "http://fsp-id.test")
    monkeypatch.setattr(httpx, "get", lambda *_, **__: discovery)
    provider = OidcFspId(
        issuer="http://fsp-id.test", client_id="c", client_secret="s", redirect_uri="http://cb"
    )

    with pytest.raises(FspIdUnavailable):
        provider.authorization_url(FspAuthorization("s", "v", "n", FspIntent.login))


def test_card_shows_full_achievements_only_after_accepted_invitation(
    candidate: TestClient,
    signed_in: SignIn,
    seeds: Seeds,
    fsp_id: MemoryFspId,
    fsp_registry: MemoryFspRegistry,
) -> None:
    pass_test(candidate, seeds)
    who = identity()
    fsp_registry.records[who.sub] = [WINNER]
    linked(candidate, fsp_id, who)
    me = candidate.get("/api/auth/me").json()["id"]
    employer = with_company(signed_in(Role.employer))
    before = employer.get(f"/api/employer/candidates/{me}").json()

    invitation = invite(employer, me)
    answer(candidate, invitation["id"], "accept").raise_for_status()
    after = employer.get(f"/api/employer/candidates/{me}").json()

    assert before["fsp_details"] is None
    assert WINNER.event not in str(before)
    assert after["fsp_achievements"] == before["fsp_achievements"]
    assert [(a["event"], a["place"], a["team_role"]["code"]) for a in after["fsp_details"]] == [
        (WINNER.event, 1, "qa")
    ]
