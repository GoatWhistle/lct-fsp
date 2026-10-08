"""Приглашения через HTTP API (mechanics.md, §14): отправка с вилкой, ответ кандидата, статусы,
срок ответа, недельный бюджет компании и одно открытое приглашение на пару."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from settings import Mechanics, Settings
from tests.candidate_path import grant_category, with_company

EMPLOYER = "/api/employer/invitations"
CANDIDATE = "/api/candidate/invitations"
BUDGET = 3
TTL_DAYS = 3

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def mechanics(settings: Settings) -> Mechanics:
    """Бюджет поменьше — тест доходит до его края за несколько приглашений; срок короче недели —
    приглашение успевает истечь в той же неделе бюджета."""
    return Mechanics.from_yaml(settings.mechanics_file).model_copy(
        update={"invitation_weekly_budget": BUDGET, "invitation_ttl_days": TTL_DAYS}
    )


@pytest.fixture
def ttl(mechanics: Mechanics) -> timedelta:
    return timedelta(days=mechanics.invitation_ttl_days)


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return with_company(signed_in(Role.employer))


@pytest.fixture
def new_candidate(signed_in: SignIn, db_engine: Engine) -> Callable[[], tuple[TestClient, str]]:
    """Кандидат с категорией QA · Middle — его можно пригласить."""

    def make() -> tuple[TestClient, str]:
        c = signed_in(Role.candidate)
        candidate_id: str = c.get("/api/auth/me").json()["id"]
        grant_category(db_engine, candidate_id)
        return c, candidate_id

    return make


@pytest.fixture
def candidate(new_candidate: Callable[[], tuple[TestClient, str]]) -> tuple[TestClient, str]:
    return new_candidate()


def terms(candidate_id: str, **changes: Any) -> Json:
    body: Json = {
        "candidate_id": candidate_id,
        "description": "Бэкенд платёжного шлюза: Python, PostgreSQL, очереди",
        "salary_from": 250_000,
        "salary_to": 320_000,
        "contact": "Telegram @pay_hr",
    }
    return body | changes


def invite(employer: TestClient, candidate_id: str, **changes: Any) -> Json:
    response = employer.post(EMPLOYER, json=terms(candidate_id, **changes))
    assert response.status_code == 201, response.text
    body: Json = response.json()
    return body


def inbox(c: TestClient) -> list[Json]:
    response = c.get(CANDIDATE)
    assert response.status_code == 200, response.text
    body: list[Json] = response.json()
    return body


def sent(employer: TestClient) -> Json:
    response = employer.get(EMPLOYER)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def answer(c: TestClient, invitation_id: str, action: str) -> Any:
    return c.post(f"{CANDIDATE}/{invitation_id}/{action}")


# Отправка и вилка.


def test_employer_invites_candidate(
    employer: TestClient, candidate: tuple[TestClient, str], clock: FrozenClock, ttl: timedelta
) -> None:
    c, candidate_id = candidate

    invitation = invite(employer, candidate_id)

    assert invitation["status"] == "sent"
    assert invitation["candidate_id"] == candidate_id
    assert invitation["company_name"] == "Платёжные решения"
    assert (invitation["salary_from"], invitation["salary_to"]) == (250_000, 320_000)
    assert invitation["salary_basis"] == "gross"
    assert invitation["contact"] == "Telegram @pay_hr"
    sent_at = datetime.fromisoformat(invitation["sent_at"])
    assert sent_at == clock.now()
    assert datetime.fromisoformat(invitation["expires_at"]) == sent_at + ttl
    assert inbox(c) == [invitation]
    assert sent(employer)["invitations"] == [invitation]


@pytest.mark.parametrize("missing", ["salary_from", "salary_to"])
def test_invitation_without_salary_is_rejected(
    employer: TestClient, candidate: tuple[TestClient, str], missing: str
) -> None:
    body = terms(candidate[1])
    del body[missing]

    response = employer.post(EMPLOYER, json=body)

    assert response.status_code == 422
    assert inbox(candidate[0]) == []


@pytest.mark.parametrize(
    ("salary_from", "salary_to"), [(0, 100_000), (-1, 100_000), (300_000, 200_000)]
)
def test_invitation_with_wrong_salary_range_is_rejected(
    employer: TestClient, candidate: tuple[TestClient, str], salary_from: int, salary_to: int
) -> None:
    response = employer.post(
        EMPLOYER, json=terms(candidate[1], salary_from=salary_from, salary_to=salary_to)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_salary_range"


def test_candidate_without_category_cannot_be_invited(
    employer: TestClient, signed_in: SignIn
) -> None:
    c = signed_in(Role.candidate)

    response = employer.post(EMPLOYER, json=terms(c.get("/api/auth/me").json()["id"]))

    assert response.status_code == 404
    assert response.json()["code"] == "candidate_not_found"


def test_employer_without_company_profile_cannot_invite(
    signed_in: SignIn, candidate: tuple[TestClient, str]
) -> None:
    response = signed_in(Role.employer).post(EMPLOYER, json=terms(candidate[1]))

    assert response.status_code == 409
    assert response.json()["code"] == "company_profile_required"


# Ответ кандидата и статусы.


def test_opening_marks_viewed_once(
    employer: TestClient, candidate: tuple[TestClient, str], clock: FrozenClock
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)
    clock.shift(timedelta(hours=1))

    first = c.post(f"{CANDIDATE}/{invitation['id']}/view")
    clock.shift(timedelta(hours=1))
    again = c.post(f"{CANDIDATE}/{invitation['id']}/view")

    assert first.status_code == again.status_code == 200
    assert first.json()["status"] == "viewed"
    assert datetime.fromisoformat(first.json()["viewed_at"]) == clock.now() - timedelta(hours=1)
    assert again.json() == first.json()
    assert sent(employer)["invitations"][0]["status"] == "viewed"


@pytest.mark.parametrize(("action", "status"), [("accept", "accepted"), ("decline", "declined")])
@pytest.mark.parametrize("opened", [False, True])
def test_candidate_answers(
    employer: TestClient,
    candidate: tuple[TestClient, str],
    clock: FrozenClock,
    action: str,
    status: str,
    opened: bool,
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)
    if opened:
        c.post(f"{CANDIDATE}/{invitation['id']}/view").raise_for_status()
    clock.shift(timedelta(days=1))

    response = answer(c, invitation["id"], action)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    assert datetime.fromisoformat(response.json()["answered_at"]) == clock.now()
    assert sent(employer)["invitations"][0]["status"] == status


@pytest.mark.parametrize("first", ["accept", "decline"])
@pytest.mark.parametrize("second", ["accept", "decline"])
def test_second_answer_is_conflict(
    employer: TestClient, candidate: tuple[TestClient, str], first: str, second: str
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)
    answer(c, invitation["id"], first).raise_for_status()

    response = answer(c, invitation["id"], second)

    assert response.status_code == 409
    assert response.json()["code"] == "invitation_transition_not_allowed"


def test_unanswered_invitation_expires(
    employer: TestClient, candidate: tuple[TestClient, str], clock: FrozenClock, ttl: timedelta
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)

    clock.shift(ttl - timedelta(seconds=1))
    assert inbox(c)[0]["status"] == "sent"
    clock.shift(timedelta(seconds=1))

    assert inbox(c)[0]["status"] == "expired"
    assert sent(employer)["invitations"][0]["status"] == "expired"
    for action in ("accept", "decline"):
        response = answer(c, invitation["id"], action)
        assert response.status_code == 409
        assert response.json()["code"] == "invitation_expired"
    # Открытие истёкшего ничего не меняет.
    viewed = c.post(f"{CANDIDATE}/{invitation['id']}/view")
    assert viewed.status_code == 200
    assert viewed.json()["status"] == "expired"


def test_viewed_invitation_expires_too(
    employer: TestClient, candidate: tuple[TestClient, str], clock: FrozenClock, ttl: timedelta
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)
    c.post(f"{CANDIDATE}/{invitation['id']}/view").raise_for_status()

    clock.shift(ttl)

    assert answer(c, invitation["id"], "accept").status_code == 409
    assert inbox(c)[0]["status"] == "expired"


def test_answered_invitation_does_not_expire(
    employer: TestClient, candidate: tuple[TestClient, str], clock: FrozenClock, ttl: timedelta
) -> None:
    c, candidate_id = candidate
    invitation = invite(employer, candidate_id)
    answer(c, invitation["id"], "accept").raise_for_status()

    clock.shift(ttl * 2)

    assert inbox(c)[0]["status"] == "accepted"


# Одно открытое приглашение на пару «компания — кандидат».


def test_second_invitation_while_open_is_conflict(
    employer: TestClient, candidate: tuple[TestClient, str]
) -> None:
    c, candidate_id = candidate
    first = invite(employer, candidate_id)
    c.post(f"{CANDIDATE}/{first['id']}/view").raise_for_status()

    response = employer.post(EMPLOYER, json=terms(candidate_id))

    assert response.status_code == 409
    assert response.json()["code"] == "invitation_already_open"
    assert len(inbox(c)) == 1


@pytest.mark.parametrize("close", ["accept", "decline", "expire"])
def test_new_invitation_after_previous_closed(
    employer: TestClient,
    candidate: tuple[TestClient, str],
    clock: FrozenClock,
    ttl: timedelta,
    close: str,
) -> None:
    c, candidate_id = candidate
    first = invite(employer, candidate_id)
    if close == "expire":
        clock.shift(ttl)
    else:
        answer(c, first["id"], close).raise_for_status()
        clock.shift(timedelta(minutes=1))

    second = invite(employer, candidate_id, description="Вторая попытка")

    assert [i["id"] for i in inbox(c)] == [second["id"], first["id"]]


def test_other_company_may_invite_while_one_is_open(
    employer: TestClient, signed_in: SignIn, candidate: tuple[TestClient, str]
) -> None:
    c, candidate_id = candidate
    invite(employer, candidate_id)

    invite(with_company(signed_in(Role.employer), "Другая компания"), candidate_id)

    assert {i["company_name"] for i in inbox(c)} == {"Платёжные решения", "Другая компания"}


# Недельный бюджет.


def test_budget_is_shown_and_spent(
    employer: TestClient, new_candidate: Callable[[], tuple[TestClient, str]], clock: FrozenClock
) -> None:
    # Среда 23 сентября 2026, 15:00 МСК; неделя обновится в понедельник 28 сентября, 00:00 МСК.
    clock.set(datetime(2026, 9, 23, 12, 0, tzinfo=UTC))
    monday = datetime(2026, 9, 27, 21, 0, tzinfo=UTC)
    assert sent(employer)["budget"] == {
        "limit": BUDGET,
        "used": 0,
        "remaining": BUDGET,
        "resets_at": "2026-09-27T21:00:00Z",
    }

    invite(employer, new_candidate()[1])

    budget = sent(employer)["budget"]
    assert (budget["used"], budget["remaining"]) == (1, BUDGET - 1)
    assert datetime.fromisoformat(budget["resets_at"]) == monday


def test_invitation_over_budget_is_conflict_and_closed_ones_do_not_return_it(
    employer: TestClient,
    new_candidate: Callable[[], tuple[TestClient, str]],
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 9, 23, 12, 0, tzinfo=UTC))
    invited = [new_candidate() for _ in range(BUDGET)]
    ids = [invite(employer, candidate_id)["id"] for _, candidate_id in invited]
    extra = new_candidate()[1]

    assert employer.post(EMPLOYER, json=terms(extra)).json()["code"] == (
        "invitation_budget_exhausted"
    )
    # Отклонённое бюджет не возвращает.
    answer(invited[0][0], ids[0], "decline").raise_for_status()
    response = employer.post(EMPLOYER, json=terms(extra))
    assert response.status_code == 409
    assert response.json()["code"] == "invitation_budget_exhausted"
    assert sent(employer)["budget"]["remaining"] == 0


def test_expired_invitations_do_not_return_budget(
    employer: TestClient,
    new_candidate: Callable[[], tuple[TestClient, str]],
    clock: FrozenClock,
) -> None:
    # Понедельник 00:00 МСК: приглашения истекают ещё в этой неделе бюджета.
    clock.set(datetime(2026, 9, 27, 21, 0, tzinfo=UTC))
    for _ in range(BUDGET):
        invite(employer, new_candidate()[1])

    clock.shift(timedelta(days=TTL_DAYS + 1))

    assert {i["status"] for i in sent(employer)["invitations"]} == {"expired"}
    response = employer.post(EMPLOYER, json=terms(new_candidate()[1]))
    assert response.status_code == 409
    assert response.json()["code"] == "invitation_budget_exhausted"


def test_budget_is_full_again_from_monday_midnight_moscow(
    employer: TestClient,
    new_candidate: Callable[[], tuple[TestClient, str]],
    clock: FrozenClock,
) -> None:
    monday = datetime(2026, 9, 27, 21, 0, tzinfo=UTC)
    clock.set(monday - timedelta(hours=2))
    for _ in range(BUDGET):
        invite(employer, new_candidate()[1])
    extra = new_candidate()[1]

    clock.set(monday - timedelta(seconds=1))
    assert employer.post(EMPLOYER, json=terms(extra)).status_code == 409

    clock.set(monday)
    assert sent(employer)["budget"]["remaining"] == BUDGET
    invite(employer, extra)


def test_budget_is_per_company(
    employer: TestClient,
    signed_in: SignIn,
    new_candidate: Callable[[], tuple[TestClient, str]],
) -> None:
    for _ in range(BUDGET):
        invite(employer, new_candidate()[1])

    other = with_company(signed_in(Role.employer), "Другая компания")

    assert sent(other)["budget"]["remaining"] == BUDGET
    invite(other, new_candidate()[1])


# Кто что видит.


def test_candidate_sees_only_own_invitations(
    employer: TestClient, new_candidate: Callable[[], tuple[TestClient, str]]
) -> None:
    (mine, mine_id), (other, _) = new_candidate(), new_candidate()
    invitation = invite(employer, mine_id)

    assert inbox(other) == []
    for action in ("view", "accept", "decline"):
        response = other.post(f"{CANDIDATE}/{invitation['id']}/{action}")
        assert response.status_code == 404, action
        assert response.json()["code"] == "invitation_not_found"
    assert inbox(mine)[0]["status"] == "sent"


def test_employer_sees_only_own_company_invitations(
    employer: TestClient, signed_in: SignIn, candidate: tuple[TestClient, str]
) -> None:
    invitation = invite(employer, candidate[1])
    other = with_company(signed_in(Role.employer), "Другая компания")

    assert sent(other)["invitations"] == []
    response = other.get(f"{EMPLOYER}/{invitation['id']}")
    assert response.status_code == 404
    assert response.json()["code"] == "invitation_not_found"
    assert employer.get(f"{EMPLOYER}/{invitation['id']}").json() == invitation


def test_unknown_invitation_is_not_found(candidate: tuple[TestClient, str]) -> None:
    response = candidate[0].post(f"{CANDIDATE}/00000000-0000-0000-0000-000000000000/accept")

    assert response.status_code == 404


def test_roles_are_checked(employer: TestClient, candidate: tuple[TestClient, str]) -> None:
    c, candidate_id = candidate

    assert c.post(EMPLOYER, json=terms(candidate_id)).status_code == 403
    assert employer.get(CANDIDATE).status_code == 403
