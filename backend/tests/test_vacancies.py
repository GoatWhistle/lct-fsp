"""Вакансии и отклики через HTTP API (mechanics.md, §14): вилка вакансии, правка и снятие только
своей, общий список, один отклик кандидата на вакансию, статусы отклика с ходом у работодателя,
срок ответа, видимость откликов сторонам и независимость от бюджета приглашений."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from settings import Mechanics
from tests.candidate_path import (
    VACANCY,
    fill_profile,
    grant_category,
    publish_vacancy,
    with_company,
)

EMPLOYER = "/api/employer/vacancies"
INCOMING = "/api/employer/applications"
PUBLISHED = "/api/candidate/vacancies"
MINE = "/api/candidate/applications"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def ttl(mechanics: Mechanics) -> timedelta:
    return timedelta(days=mechanics.invitation_ttl_days)


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return with_company(signed_in(Role.employer))


@pytest.fixture
def other_employer(signed_in: SignIn) -> TestClient:
    return with_company(signed_in(Role.employer), "Другая компания")


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    """Кандидат с анкетой, без категории: откликнуться можно и так."""
    return fill_profile(signed_in(Role.candidate))


def json_list(response: Any) -> list[Json]:
    assert response.status_code == 200, response.text
    body: list[Json] = response.json()
    return body


def apply(c: TestClient, vacancy_id: str) -> Any:
    return c.post(f"{PUBLISHED}/{vacancy_id}/apply")


def applied(c: TestClient, vacancy_id: str) -> Json:
    response = apply(c, vacancy_id)
    assert response.status_code == 201, response.text
    body: Json = response.json()
    return body


def ids(items: list[Json]) -> list[str]:
    return [i["id"] for i in items]


# Вакансия: публикация, вилка, правка, снятие.


def test_employer_publishes_vacancy(employer: TestClient, clock: FrozenClock) -> None:
    vacancy = publish_vacancy(employer)

    assert vacancy["company_name"] == "Платёжные решения"
    assert vacancy["specialization"] == {"code": "qa", "name": vacancy["specialization"]["name"]}
    assert vacancy["grade"]["code"] == "middle"
    assert (vacancy["salary_from"], vacancy["salary_to"]) == (220_000, 280_000)
    assert vacancy["salary_basis"] == "gross"
    assert vacancy["work_formats"] == ["hybrid", "remote"]
    assert datetime.fromisoformat(vacancy["published_at"]) == clock.now()
    assert vacancy["archived_at"] is None
    assert json_list(employer.get(EMPLOYER)) == [vacancy]


@pytest.mark.parametrize("missing", ["salary_from", "salary_to"])
def test_vacancy_without_salary_is_not_published(employer: TestClient, missing: str) -> None:
    body = dict(VACANCY)
    del body[missing]

    response = employer.post(EMPLOYER, json=body)

    assert response.status_code == 422
    assert json_list(employer.get(EMPLOYER)) == []


@pytest.mark.parametrize(
    ("salary_from", "salary_to"), [(0, 100_000), (-1, 100_000), (300_000, 200_000)]
)
def test_vacancy_with_wrong_salary_range_is_rejected(
    employer: TestClient, salary_from: int, salary_to: int
) -> None:
    response = employer.post(
        EMPLOYER, json=VACANCY | {"salary_from": salary_from, "salary_to": salary_to}
    )

    assert response.status_code == 422
    assert json_list(employer.get(EMPLOYER)) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"specialization": "astrology"},
        {"grade": "guru"},
        {"work_formats": []},
        {"title": "  "},
    ],
)
def test_vacancy_form_is_checked(employer: TestClient, changes: Json) -> None:
    response = employer.post(EMPLOYER, json=VACANCY | changes)

    assert response.status_code == 422, response.text


def test_vacancy_needs_company_profile(signed_in: SignIn) -> None:
    response = signed_in(Role.employer).post(EMPLOYER, json=VACANCY)

    assert response.status_code == 409
    assert response.json()["code"] == "company_required"


def test_employer_edits_own_vacancy(employer: TestClient, clock: FrozenClock) -> None:
    vacancy = publish_vacancy(employer)
    clock.shift(timedelta(hours=1))

    response = employer.put(
        f"{EMPLOYER}/{vacancy['id']}",
        json=VACANCY | {"title": "Senior QA", "grade": "senior", "salary_to": 350_000},
    )

    assert response.status_code == 200, response.text
    edited = response.json()
    assert (edited["title"], edited["grade"]["code"], edited["salary_to"]) == (
        "Senior QA",
        "senior",
        350_000,
    )
    assert edited["published_at"] == vacancy["published_at"]
    assert datetime.fromisoformat(edited["updated_at"]) == clock.now()
    assert json_list(employer.get(EMPLOYER)) == [edited]


@pytest.mark.parametrize(
    "changes", [{"salary_from": 400_000}, {"salary_from": 0}, {"salary_to": None}]
)
def test_vacancy_cannot_be_edited_into_wrong_salary(employer: TestClient, changes: Json) -> None:
    vacancy = publish_vacancy(employer)

    response = employer.put(f"{EMPLOYER}/{vacancy['id']}", json=VACANCY | changes)

    assert response.status_code == 422
    assert json_list(employer.get(EMPLOYER)) == [vacancy]


def test_employer_cannot_edit_or_archive_another_company_vacancy(
    employer: TestClient, other_employer: TestClient
) -> None:
    vacancy = publish_vacancy(employer)

    edit = other_employer.put(f"{EMPLOYER}/{vacancy['id']}", json=VACANCY | {"title": "Чужое"})
    archive = other_employer.post(f"{EMPLOYER}/{vacancy['id']}/archive")

    assert (edit.status_code, archive.status_code) == (404, 404)
    assert edit.json()["code"] == archive.json()["code"] == "vacancy_not_found"
    assert json_list(employer.get(EMPLOYER)) == [vacancy]
    assert json_list(other_employer.get(EMPLOYER)) == []


def test_archived_vacancy_leaves_public_list_and_cannot_be_edited(
    employer: TestClient, candidate: TestClient, clock: FrozenClock
) -> None:
    vacancy = publish_vacancy(employer)

    response = employer.post(f"{EMPLOYER}/{vacancy['id']}/archive")

    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["archived_at"]) == clock.now()
    assert employer.post(f"{EMPLOYER}/{vacancy['id']}/archive").json() == response.json()
    assert json_list(candidate.get(PUBLISHED)) == []
    assert ids(json_list(employer.get(EMPLOYER))) == [vacancy["id"]]
    edit = employer.put(f"{EMPLOYER}/{vacancy['id']}", json=VACANCY)
    assert edit.status_code == 409
    assert edit.json()["code"] == "vacancy_archived"


# Общий список.


def test_candidate_sees_published_vacancies_of_all_companies_newest_first(
    employer: TestClient, other_employer: TestClient, candidate: TestClient, clock: FrozenClock
) -> None:
    first = publish_vacancy(employer)
    clock.shift(timedelta(minutes=1))
    second = publish_vacancy(other_employer, specialization="backend")

    assert ids(json_list(candidate.get(PUBLISHED))) == [second["id"], first["id"]]
    assert ids(json_list(candidate.get(PUBLISHED, params={"specialization": "qa"}))) == [
        first["id"]
    ]
    assert json_list(candidate.get(PUBLISHED))[0]["salary_basis"] == "gross"


def test_vacancy_sections_belong_to_their_roles(
    employer: TestClient, candidate: TestClient
) -> None:
    assert employer.get(PUBLISHED).status_code == 403
    assert candidate.get(EMPLOYER).status_code == 403
    assert candidate.post(EMPLOYER, json=VACANCY).status_code == 403
    assert candidate.get(INCOMING).status_code == 403
    assert employer.get(MINE).status_code == 403


# Отклик.


def test_candidate_without_category_applies(
    employer: TestClient, candidate: TestClient, clock: FrozenClock, ttl: timedelta
) -> None:
    vacancy = publish_vacancy(employer)

    application = applied(candidate, vacancy["id"])

    assert application["status"] == "sent"
    assert application["vacancy_id"] == vacancy["id"]
    assert application["vacancy_title"] == vacancy["title"]
    assert application["company_name"] == "Платёжные решения"
    assert application["salary_basis"] == "gross"
    applied_at = datetime.fromisoformat(application["applied_at"])
    assert applied_at == clock.now()
    assert datetime.fromisoformat(application["expires_at"]) == applied_at + ttl
    assert json_list(candidate.get(MINE)) == [application]
    assert json_list(employer.get(INCOMING)) == [application]


def test_repeated_application_is_conflict(employer: TestClient, candidate: TestClient) -> None:
    vacancy = publish_vacancy(employer)
    applied(candidate, vacancy["id"])

    response = apply(candidate, vacancy["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "already_applied"
    assert len(json_list(candidate.get(MINE))) == 1


def test_archived_vacancy_takes_no_applications_and_keeps_old_ones(
    employer: TestClient, candidate: TestClient, signed_in: SignIn
) -> None:
    vacancy = publish_vacancy(employer)
    application = applied(candidate, vacancy["id"])
    employer.post(f"{EMPLOYER}/{vacancy['id']}/archive").raise_for_status()

    response = apply(fill_profile(signed_in(Role.candidate)), vacancy["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "vacancy_archived"
    assert json_list(candidate.get(MINE)) == [application]
    assert json_list(employer.get(INCOMING)) == [application]


def test_application_to_unknown_vacancy_is_not_found(candidate: TestClient) -> None:
    response = apply(candidate, "00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["code"] == "vacancy_not_found"


# Кто что видит.


def test_each_side_sees_only_own_applications(
    employer: TestClient, other_employer: TestClient, candidate: TestClient, signed_in: SignIn
) -> None:
    ours, theirs = publish_vacancy(employer), publish_vacancy(other_employer)
    mine = applied(candidate, ours["id"])
    other_candidate = fill_profile(signed_in(Role.candidate))
    foreign = applied(other_candidate, theirs["id"])

    assert json_list(candidate.get(MINE)) == [mine]
    assert json_list(other_candidate.get(MINE)) == [foreign]
    assert json_list(employer.get(INCOMING)) == [mine]
    assert json_list(other_employer.get(INCOMING)) == [foreign]
    assert json_list(employer.get(INCOMING, params={"vacancy_id": ours["id"]})) == [mine]
    by_foreign_vacancy = employer.get(INCOMING, params={"vacancy_id": theirs["id"]})
    assert by_foreign_vacancy.status_code == 404
    for action in ("view", "accept", "decline"):
        response = employer.post(f"{INCOMING}/{foreign['id']}/{action}")
        assert response.status_code == 404, action
        assert response.json()["code"] == "application_not_found"
    revoke = candidate.post(f"{MINE}/{foreign['id']}/revoke")
    assert revoke.status_code == 404
    assert json_list(other_employer.get(INCOMING)) == [foreign]


# Статусы отклика: ход у работодателя, статус видят обе стороны.


def answer(employer: TestClient, application_id: str, action: str) -> Any:
    return employer.post(f"{INCOMING}/{application_id}/{action}")


def test_employer_opening_application_marks_it_viewed_for_both(
    employer: TestClient, candidate: TestClient, clock: FrozenClock
) -> None:
    application = applied(candidate, publish_vacancy(employer)["id"])
    clock.shift(timedelta(hours=2))

    opened = answer(employer, application["id"], "view")

    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "viewed"
    assert datetime.fromisoformat(opened.json()["viewed_at"]) == clock.now()
    assert answer(employer, application["id"], "view").json() == opened.json()
    assert json_list(candidate.get(MINE)) == [opened.json()]


@pytest.mark.parametrize(("action", "status"), [("accept", "accepted"), ("decline", "declined")])
@pytest.mark.parametrize("opened", [False, True])
def test_employer_answers_application_and_candidate_sees_status(
    employer: TestClient, candidate: TestClient, action: str, status: str, opened: bool
) -> None:
    application = applied(candidate, publish_vacancy(employer)["id"])
    if opened:
        answer(employer, application["id"], "view").raise_for_status()

    response = answer(employer, application["id"], action)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    assert json_list(candidate.get(MINE))[0]["status"] == status
    assert json_list(employer.get(INCOMING))[0]["status"] == status


@pytest.mark.parametrize("first", ["accept", "decline"])
@pytest.mark.parametrize("second", ["accept", "decline"])
def test_answered_application_cannot_be_answered_again(
    employer: TestClient, candidate: TestClient, first: str, second: str
) -> None:
    application = applied(candidate, publish_vacancy(employer)["id"])
    answer(employer, application["id"], first).raise_for_status()

    response = answer(employer, application["id"], second)

    assert response.status_code == 409
    assert response.json()["code"] == "application_transition_not_allowed"


def test_application_without_answer_expires(
    employer: TestClient, candidate: TestClient, clock: FrozenClock, ttl: timedelta
) -> None:
    # Отклик подан срок назад: часы вперёд не двигаем — сессии тоже истекли бы.
    clock.shift(-ttl)
    application = applied(candidate, publish_vacancy(employer)["id"])
    clock.shift(ttl)

    assert json_list(candidate.get(MINE))[0]["status"] == "expired"
    assert json_list(employer.get(INCOMING))[0]["status"] == "expired"
    assert answer(employer, application["id"], "view").json()["status"] == "expired"
    response = answer(employer, application["id"], "accept")
    assert response.status_code == 409
    assert response.json()["code"] == "application_transition_not_allowed"


# Бюджет приглашений отклики не трогают.


def test_applications_do_not_spend_invitation_budget(
    employer: TestClient, signed_in: SignIn, db_engine: Engine
) -> None:
    vacancy = publish_vacancy(employer)
    before = employer.get("/api/employer/invitations").json()["budget"]
    candidates = [fill_profile(signed_in(Role.candidate)) for _ in range(2)]
    applications = [applied(c, vacancy["id"]) for c in candidates]
    answer(employer, applications[0]["id"], "accept").raise_for_status()

    after = employer.get("/api/employer/invitations").json()["budget"]

    assert after == before
    # Отклик не мешает и пригласить того же кандидата: правило одного открытого приглашения
    # с откликами не пересекается.
    candidate_id = candidates[1].get("/api/auth/me").json()["id"]
    grant_category(db_engine, candidate_id)
    invitation = employer.post(
        "/api/employer/invitations",
        json={
            "candidate_id": candidate_id,
            "description": "Автотесты платёжного шлюза",
            "salary_from": 250_000,
            "salary_to": 300_000,
            "contact": "@pay_hr",
        },
    )
    assert invitation.status_code == 201, invitation.text


def test_application_needs_filled_profile(employer: TestClient, signed_in: SignIn) -> None:
    response = apply(signed_in(Role.candidate), publish_vacancy(employer)["id"])

    assert response.status_code == 404
    assert response.json()["code"] == "profile_not_found"


# Отзыв доступа: повторный ничего не меняет и не закрывает доступ, выданный позже.


def me_id(c: TestClient) -> str:
    candidate_id: str = c.get("/api/auth/me").json()["id"]
    return candidate_id


def card_disclosed(employer: TestClient, candidate_id: str) -> bool:
    response = employer.get(f"/api/employer/candidates/{candidate_id}")
    assert response.status_code == 200, response.text
    return response.json()["disclosed"] is not None


def test_repeated_application_revoke_keeps_access_given_later(
    employer: TestClient, candidate: TestClient
) -> None:
    first = applied(candidate, publish_vacancy(employer)["id"])
    candidate.post(f"{MINE}/{first['id']}/revoke").raise_for_status()
    applied(candidate, publish_vacancy(employer)["id"])
    assert card_disclosed(employer, me_id(candidate))

    again = candidate.post(f"{MINE}/{first['id']}/revoke")

    assert again.status_code == 200, again.text
    assert card_disclosed(employer, me_id(candidate))


def test_repeated_invitation_revoke_keeps_later_application(
    employer: TestClient, candidate: TestClient, db_engine: Engine
) -> None:
    candidate_id = me_id(candidate)
    grant_category(db_engine, candidate_id)
    invitation = employer.post(
        "/api/employer/invitations",
        json={
            "candidate_id": candidate_id,
            "description": "Автотесты платёжного шлюза",
            "salary_from": 250_000,
            "salary_to": 300_000,
            "contact": "@pay_hr",
        },
    ).json()
    for action in ("accept", "revoke"):
        candidate.post(f"/api/candidate/invitations/{invitation['id']}/{action}").raise_for_status()
    applied(candidate, publish_vacancy(employer)["id"])

    candidate.post(f"/api/candidate/invitations/{invitation['id']}/revoke").raise_for_status()

    assert card_disclosed(employer, candidate_id)
