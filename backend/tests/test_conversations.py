"""Переписка и отзыв доступа через HTTP API (mechanics.md, §14): пишут и читают только стороны
принятого приглашения, непрочитанное — счётчиком в кабинете и в списке приглашений, отзыв
снова обезличивает карточку, но переписку не закрывает."""

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
from tests.test_visibility import PROFILE

EMPLOYER = "/api/employer/invitations"
CANDIDATE = "/api/candidate/invitations"
NOT_ACCEPTED = ("отправлено", "просмотрено", "отклонено", "истекло")

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]
NewCandidate = Callable[[], tuple[TestClient, str]]


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return with_company(signed_in(Role.employer))


@pytest.fixture
def new_candidate(signed_in: SignIn, db_engine: Engine) -> NewCandidate:
    """Кандидат с анкетой и категорией QA · Middle — его можно пригласить."""

    def make() -> tuple[TestClient, str]:
        c = signed_in(Role.candidate)
        c.put("/api/candidate/profile", json=PROFILE).raise_for_status()
        candidate_id: str = c.get("/api/auth/me").json()["id"]
        grant_category(db_engine, candidate_id)
        return c, candidate_id

    return make


@pytest.fixture
def candidate(new_candidate: NewCandidate) -> tuple[TestClient, str]:
    return new_candidate()


def invite(employer: TestClient, candidate_id: str) -> str:
    response = employer.post(
        EMPLOYER,
        json={
            "candidate_id": candidate_id,
            "description": "Автотесты платёжного шлюза",
            "salary_from": 250_000,
            "salary_to": 300_000,
            "contact": "@pay_hr",
        },
    )
    assert response.status_code == 201, response.text
    invitation_id: str = response.json()["id"]
    return invitation_id


def act(c: TestClient, invitation_id: str, action: str) -> Json:
    response = c.post(f"{CANDIDATE}/{invitation_id}/{action}")
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


@pytest.fixture
def accepted(employer: TestClient, candidate: tuple[TestClient, str]) -> str:
    invitation_id = invite(employer, candidate[1])
    act(candidate[0], invitation_id, "accept")
    return invitation_id


def bring_to(
    state: str,
    employer: TestClient,
    candidate: tuple[TestClient, str],
    clock: FrozenClock,
    mechanics: Mechanics,
) -> str:
    """Приглашение компании кандидату в неприятом состоянии `state`."""
    c, candidate_id = candidate
    match state:
        case "отправлено":
            return invite(employer, candidate_id)
        case "просмотрено" | "отклонено":
            invitation_id = invite(employer, candidate_id)
            act(c, invitation_id, "view" if state == "просмотрено" else "decline")
            return invitation_id
        case "истекло":
            # Отправлено срок назад: часы вперёд не двигаем — сессии тоже истекли бы.
            ttl = timedelta(days=mechanics.invitation_ttl_days)
            clock.shift(-ttl)
            invitation_id = invite(employer, candidate_id)
            clock.shift(ttl)
            return invitation_id
    raise AssertionError(state)


def write(c: TestClient, base: str, invitation_id: str, text: str) -> Any:
    return c.post(f"{base}/{invitation_id}/messages", json={"text": text})


def read(c: TestClient, base: str, invitation_id: str) -> Any:
    return c.get(f"{base}/{invitation_id}/messages")


def texts(c: TestClient, base: str, invitation_id: str) -> list[str]:
    response = read(c, base, invitation_id)
    assert response.status_code == 200, response.text
    return [m["text"] for m in response.json()]


def cabinet_unread(c: TestClient, role: str) -> int:
    response = c.get(f"/api/{role}/cabinet")
    assert response.status_code == 200, response.text
    count: int = response.json()["unread_messages"]
    return count


def invitation_unread(c: TestClient, base: str, invitation_id: str) -> int:
    response = c.get(base)
    assert response.status_code == 200, response.text
    body = response.json()
    invitations = body if isinstance(body, list) else body["invitations"]
    (found,) = [i for i in invitations if i["id"] == invitation_id]
    count: int = found["unread_messages"]
    return count


# Кто пишет и читает.


def test_sides_of_accepted_invitation_talk(
    employer: TestClient, candidate: tuple[TestClient, str], accepted: str, clock: FrozenClock
) -> None:
    c = candidate[0]

    first = write(employer, EMPLOYER, accepted, "Здравствуйте! Удобно созвониться завтра?")
    clock.shift(timedelta(minutes=5))
    second = write(c, CANDIDATE, accepted, "  Да, после 15:00  ")

    assert first.status_code == second.status_code == 201
    assert second.json()["text"] == "Да, после 15:00"
    thread = read(c, CANDIDATE, accepted).json()
    assert [(m["author"], m["text"]) for m in thread] == [
        ("employer", "Здравствуйте! Удобно созвониться завтра?"),
        ("candidate", "Да, после 15:00"),
    ]
    assert datetime.fromisoformat(thread[1]["sent_at"]) == clock.now()
    assert texts(employer, EMPLOYER, accepted) == [m["text"] for m in thread]


def test_messages_of_one_moment_keep_their_order(employer: TestClient, accepted: str) -> None:
    for n in range(5):
        write(employer, EMPLOYER, accepted, f"Сообщение {n}")

    assert texts(employer, EMPLOYER, accepted) == [f"Сообщение {n}" for n in range(5)]


@pytest.mark.parametrize("action", ["read", "write"])
def test_outsiders_get_no_conversation(
    signed_in: SignIn,
    new_client: Callable[[], TestClient],
    new_candidate: NewCandidate,
    employer: TestClient,
    accepted: str,
    action: str,
) -> None:
    write(employer, EMPLOYER, accepted, "Только для кандидата")
    other_company = with_company(signed_in(Role.employer), "Другая компания")
    other_candidate = new_candidate()[0]
    anonymous = new_client()

    def call(c: TestClient, base: str) -> int:
        response = read(c, base, accepted) if action == "read" else write(c, base, accepted, "Hi")
        assert "Только для кандидата" not in response.text
        code: int = response.status_code
        return code

    assert call(other_company, EMPLOYER) == 404
    assert call(other_candidate, CANDIDATE) == 404
    assert call(anonymous, CANDIDATE) == 401
    assert call(anonymous, EMPLOYER) == 401
    # Компания по роутеру кандидата — отказ по роли.
    assert call(employer, CANDIDATE) == 403
    assert texts(employer, EMPLOYER, accepted) == ["Только для кандидата"]


@pytest.mark.parametrize("state", NOT_ACCEPTED)
def test_no_conversation_in_not_accepted_invitation(
    employer: TestClient,
    candidate: tuple[TestClient, str],
    clock: FrozenClock,
    mechanics: Mechanics,
    state: str,
) -> None:
    invitation_id = bring_to(state, employer, candidate, clock, mechanics)

    for client, base in [(employer, EMPLOYER), (candidate[0], CANDIDATE)]:
        response = write(client, base, invitation_id, "Здравствуйте")
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "invitation_not_accepted"
        assert read(client, base, invitation_id).status_code == 409


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_message_is_rejected(
    candidate: tuple[TestClient, str], accepted: str, text: str
) -> None:
    response = write(candidate[0], CANDIDATE, accepted, text)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_message_text"


def test_message_over_max_length_is_rejected(
    employer: TestClient, accepted: str, mechanics: Mechanics
) -> None:
    limit = mechanics.message_max_length

    assert write(employer, EMPLOYER, accepted, "а" * limit).status_code == 201
    response = write(employer, EMPLOYER, accepted, "а" * (limit + 1))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_message_text"
    assert len(texts(employer, EMPLOYER, accepted)) == 1


# Непрочитанное.


def test_unread_grows_on_other_side_message_and_resets_on_open(
    employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c = candidate[0]

    write(employer, EMPLOYER, accepted, "Первое")
    write(employer, EMPLOYER, accepted, "Второе")

    assert cabinet_unread(c, "candidate") == 2
    assert invitation_unread(c, CANDIDATE, accepted) == 2
    # Своё сообщение счётчик своей стороны не растит.
    assert cabinet_unread(employer, "employer") == 0
    assert invitation_unread(employer, EMPLOYER, accepted) == 0

    thread = read(c, CANDIDATE, accepted).json()

    assert all(m["read_at"] is not None for m in thread)
    assert cabinet_unread(c, "candidate") == 0
    assert invitation_unread(c, CANDIDATE, accepted) == 0

    # Часы стоят: сообщение в тот же момент после открытия — снова непрочитанное.
    write(employer, EMPLOYER, accepted, "Третье")
    write(c, CANDIDATE, accepted, "Ответ")

    assert cabinet_unread(c, "candidate") == 1
    assert cabinet_unread(employer, "employer") == 1
    assert invitation_unread(employer, EMPLOYER, accepted) == 1


def test_cabinet_sums_unread_over_invitations(
    signed_in: SignIn, employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c, candidate_id = candidate
    other = with_company(signed_in(Role.employer), "Другая компания")
    second = invite(other, candidate_id)
    act(c, second, "accept")

    write(employer, EMPLOYER, accepted, "От первой")
    write(other, EMPLOYER, second, "От второй")
    write(other, EMPLOYER, second, "Ещё от второй")

    assert cabinet_unread(c, "candidate") == 3
    assert invitation_unread(c, CANDIDATE, second) == 2
    # Чужая переписка компании не считается.
    assert cabinet_unread(employer, "employer") == 0


# Отзыв доступа.


def card(employer: TestClient, candidate_id: str) -> str:
    response = employer.get(f"/api/employer/candidates/{candidate_id}")
    assert response.status_code == 200, response.text
    return response.text


def test_revoke_hides_card_and_keeps_conversation(
    employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c, candidate_id = candidate
    assert "Ёлкина" in card(employer, candidate_id)

    revoked = act(c, accepted, "revoke")

    assert revoked["status"] == "accepted"
    assert revoked["revoked_at"] is not None
    assert "Ёлкина" not in card(employer, candidate_id)
    assert "yulia.yolkina" not in card(employer, candidate_id)
    assert employer.get(f"{EMPLOYER}/{accepted}").json()["revoked_at"] == revoked["revoked_at"]
    assert write(employer, EMPLOYER, accepted, "Жаль, но давайте продолжим").status_code == 201
    assert write(c, CANDIDATE, accepted, "Давайте").status_code == 201
    assert texts(employer, EMPLOYER, accepted) == ["Жаль, но давайте продолжим", "Давайте"]


def test_revoke_twice_changes_nothing(
    candidate: tuple[TestClient, str], accepted: str, clock: FrozenClock
) -> None:
    c = candidate[0]
    first = act(c, accepted, "revoke")
    clock.shift(timedelta(hours=1))

    again = act(c, accepted, "revoke")

    assert again["revoked_at"] == first["revoked_at"]


@pytest.mark.parametrize("state", NOT_ACCEPTED)
def test_cannot_revoke_not_accepted(
    employer: TestClient,
    candidate: tuple[TestClient, str],
    clock: FrozenClock,
    mechanics: Mechanics,
    state: str,
) -> None:
    invitation_id = bring_to(state, employer, candidate, clock, mechanics)

    response = candidate[0].post(f"{CANDIDATE}/{invitation_id}/revoke")

    assert response.status_code == 409
    assert response.json()["code"] == "invitation_not_accepted"


def test_cannot_revoke_someone_elses(new_candidate: NewCandidate, accepted: str) -> None:
    response = new_candidate()[0].post(f"{CANDIDATE}/{accepted}/revoke")

    assert response.status_code == 404
    assert response.json()["code"] == "invitation_not_found"


def test_new_accepted_invitation_after_revoke_discloses_again(
    employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c, candidate_id = candidate
    act(c, accepted, "revoke")

    again = invite(employer, candidate_id)
    assert "Ёлкина" not in card(employer, candidate_id)
    act(c, again, "accept")

    assert "Ёлкина" in card(employer, candidate_id)


def test_revoke_closes_every_accepted_invitation_of_the_company(
    employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c, candidate_id = candidate
    second = invite(employer, candidate_id)
    act(c, second, "accept")

    act(c, accepted, "revoke")

    assert "Ёлкина" not in card(employer, candidate_id)
    assert employer.get(f"{EMPLOYER}/{second}").json()["revoked_at"] is not None


def test_revoke_keeps_access_of_other_companies(
    signed_in: SignIn, employer: TestClient, candidate: tuple[TestClient, str], accepted: str
) -> None:
    c, candidate_id = candidate
    other = with_company(signed_in(Role.employer), "Другая компания")
    act(c, invite(other, candidate_id), "accept")

    act(c, accepted, "revoke")

    assert "Ёлкина" in card(other, candidate_id)
