"""Видимость данных кандидата (mechanics.md, §14): каждый эндпоинт, который их отдаёт, × каждый
зритель. Для каждой пары — ожидаемый код и что из раскрываемого видно: ФИО, контакты, свободный
текст и ожидаемая зарплата приходят только тем, кому их отдаёт правило раскрытия.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import Engine

from app.adapter.clock import FrozenClock
from app.domain.account import Role
from settings import Mechanics
from tests.candidate_path import grant_category, with_company

Json = dict[str, Any]

PROFILE = {
    "full_name": "Ёлкина Юлия Сергеевна",
    "contact_email": "yulia.yolkina@example.ru",
    "contact_phone": "+7 999 123-45-67",
    "telegram": "yolkina_qa",
    "about": "Пишу автотесты, люблю разбирать флаки",
    "stack": ["pytest"],
    "job_roles": ["тимлид"],
    "experience_years": 4,
    "soft_skills": ["Наставничество"],
    "work_formats": ["remote"],
    "salary_from": 287_500,
}

# Раскрываемое — и как его искать в ответе. Зарплату в JSON ищем числом целиком: «287» бывает
# в цифрах уровней.
SECRETS = {
    "ФИО": "Ёлкина",
    "email": "yulia.yolkina",
    "телефон": "123-45-67",
    "telegram": "yolkina_qa",
    "о себе": "флаки",
    "роли": "тимлид",
    "софт-скиллы": "Наставничество",
    "зарплата": "287500",
}
PDF_SECRETS = SECRETS | {"зарплата": "287"}
ALL = frozenset(SECRETS)
NONE: frozenset[str] = frozenset()


class Viewer:
    me = "сам кандидат"
    other = "другой кандидат"
    employer = "работодатель"
    anonymous = "аноним"


@dataclass
class World:
    clients: dict[str, TestClient]
    candidate_id: str
    need_id: str
    selection_id: str


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    path: Callable[[World], str]
    pdf: bool = False

    def call(self, world: World, viewer: str) -> tuple[int, str]:
        response = world.clients[viewer].request(self.method, self.path(world))
        if self.pdf and response.status_code == 200:
            reader = PdfReader(io.BytesIO(response.content))
            return response.status_code, "\n".join(p.extract_text() for p in reader.pages)
        return response.status_code, response.text


ENDPOINTS = {
    e.name: e
    for e in [
        Endpoint("профиль", "GET", lambda w: "/api/candidate/profile"),
        Endpoint("PDF", "GET", lambda w: "/api/candidate/profile/pdf", pdf=True),
        Endpoint("карточка", "GET", lambda w: f"/api/employer/candidates/{w.candidate_id}"),
        Endpoint(
            "подборка: построение", "POST", lambda w: f"/api/employer/needs/{w.need_id}/selections"
        ),
        Endpoint(
            "подборка: страница",
            "GET",
            lambda w: f"/api/employer/selections/{w.selection_id}?offset=0&limit=1",
        ),
        Endpoint(
            "подборка: сохранённая", "GET", lambda w: f"/api/employer/selections/{w.selection_id}"
        ),
        Endpoint("приглашения работодателя", "GET", lambda w: "/api/employer/invitations"),
    ]
}

# Эндпоинты, которые отдают работодателю данные кандидата или что-то о нём.
EMPLOYER_ENDPOINTS = (
    "карточка",
    "подборка: построение",
    "подборка: страница",
    "подборка: сохранённая",
    "приглашения работодателя",
)

# Эндпоинт × зритель → код и что из раскрываемого видно. Другой кандидат получает свой профиль
# — он не заполнен — и не может собрать чужой PDF. PDF — для самого кандидата, но без ожидаемой
# зарплаты: файл может оказаться у работодателя.
TABLE: list[tuple[str, str, int, frozenset[str]]] = [
    ("профиль", Viewer.me, 200, ALL),
    ("профиль", Viewer.other, 200, NONE),
    ("профиль", Viewer.employer, 403, NONE),
    ("профиль", Viewer.anonymous, 401, NONE),
    ("PDF", Viewer.me, 200, ALL - {"зарплата"}),
    ("PDF", Viewer.other, 404, NONE),
    ("PDF", Viewer.employer, 403, NONE),
    ("PDF", Viewer.anonymous, 401, NONE),
]
for endpoint in EMPLOYER_ENDPOINTS:
    TABLE += [
        (endpoint, Viewer.me, 403, NONE),
        (endpoint, Viewer.other, 403, NONE),
        (endpoint, Viewer.employer, 201 if endpoint == "подборка: построение" else 200, NONE),
        (endpoint, Viewer.anonymous, 401, NONE),
    ]


@pytest.fixture
def world(
    signed_in: Callable[[Role], TestClient],
    new_client: Callable[[], TestClient],
    db_engine: Engine,
) -> World:
    me, other, employer = (
        signed_in(Role.candidate),
        signed_in(Role.candidate),
        signed_in(Role.employer),
    )
    me.put("/api/candidate/profile", json=PROFILE).raise_for_status()
    with_company(employer)
    candidate_id: str = me.get("/api/auth/me").json()["id"]
    grant_category(db_engine, candidate_id)

    need = employer.post(
        "/api/employer/needs",
        json={
            "title": "QA-инженер",
            "specialization": "qa",
            "grade": "middle",
            "stack": ["pytest"],
            "work_format": "remote",
        },
    )
    need.raise_for_status()
    need_id: str = need.json()["id"]
    selection = employer.post(f"/api/employer/needs/{need_id}/selections")
    selection.raise_for_status()
    body: Json = selection.json()
    # Кандидат в подборке есть — значит, проверка ниже смотрит на выдачу, где он виден.
    assert [e["candidate_id"] for e in body["entries"]] == [candidate_id]

    clients = {
        Viewer.me: me,
        Viewer.other: other,
        Viewer.employer: employer,
        Viewer.anonymous: new_client(),
    }
    return World(clients, candidate_id, need_id, body["id"])


@pytest.mark.parametrize(
    ("endpoint", "viewer", "status", "shown"),
    [pytest.param(*row, id=f"{row[0]} × {row[1]}") for row in TABLE],
)
def test_candidate_data_visibility(
    world: World, endpoint: str, viewer: str, status: int, shown: frozenset[str]
) -> None:
    e = ENDPOINTS[endpoint]

    code, text = e.call(world, viewer)

    assert code == status, text
    markers = PDF_SECRETS if e.pdf else SECRETS
    visible = {name for name, marker in markers.items() if marker in text}
    assert visible == shown


def test_table_covers_every_endpoint_and_viewer() -> None:
    viewers = [Viewer.me, Viewer.other, Viewer.employer, Viewer.anonymous]

    assert sorted((e, v) for e, v, _, _ in TABLE) == sorted(
        (e, v) for e in ENDPOINTS for v in viewers
    )


# Раскрытие работодателю по приглашениям (§14): каждый эндпоинт работодателя × состояние
# приглашений этому кандидату. Раскрывает только принятое приглашение этой же компании, и
# ожидаемой зарплаты нет и тогда; раскрытое отдаёт одна карточка.
INVITATION_STATES = (
    "нет приглашения",
    "отправлено",
    "просмотрено",
    "отклонено",
    "истекло",
    "принято другой компанией",
    "принято",
)
DISCLOSED_TO_EMPLOYER = ALL - {"зарплата"}


def bring_to(
    state: str,
    world: World,
    other_employer: TestClient,
    clock: FrozenClock,
    ttl: timedelta,
) -> None:
    me, employer = world.clients[Viewer.me], world.clients[Viewer.employer]
    terms = {
        "candidate_id": world.candidate_id,
        "description": "Автотесты платёжного шлюза",
        "salary_from": 250_000,
        "salary_to": 300_000,
        "contact": "@pay_hr",
    }

    def invite(by: TestClient) -> str:
        response = by.post("/api/employer/invitations", json=terms)
        assert response.status_code == 201, response.text
        invitation_id: str = response.json()["id"]
        return invitation_id

    def act(invitation_id: str, action: str) -> None:
        me.post(f"/api/candidate/invitations/{invitation_id}/{action}").raise_for_status()

    match state:
        case "нет приглашения":
            pass
        case "отправлено":
            invite(employer)
        case "просмотрено":
            act(invite(employer), "view")
        case "отклонено":
            act(invite(employer), "decline")
        case "истекло":
            # Отправлено срок назад: часы вперёд не двигаем — сессии тоже истекли бы.
            clock.shift(-ttl)
            invite(employer)
            clock.shift(ttl)
        case "принято другой компанией":
            act(invite(other_employer), "accept")
        case "принято":
            act(invite(employer), "accept")
        case _:
            raise AssertionError(state)


@pytest.mark.parametrize("state", INVITATION_STATES)
@pytest.mark.parametrize("endpoint", EMPLOYER_ENDPOINTS)
def test_employer_sees_candidate_disclosed_only_after_own_accepted_invitation(
    world: World,
    signed_in: Callable[[Role], TestClient],
    clock: FrozenClock,
    mechanics: Mechanics,
    endpoint: str,
    state: str,
) -> None:
    other_employer = with_company(signed_in(Role.employer), "Другая компания")
    bring_to(state, world, other_employer, clock, timedelta(days=mechanics.invitation_ttl_days))

    code, text = ENDPOINTS[endpoint].call(world, Viewer.employer)

    assert code < 300, text
    visible = {name for name, marker in SECRETS.items() if marker in text}
    expected = DISCLOSED_TO_EMPLOYER if (endpoint, state) == ("карточка", "принято") else NONE
    assert visible == expected
