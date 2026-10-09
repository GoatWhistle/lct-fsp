"""Видимость данных кандидата (mechanics.md, §14): каждый эндпоинт, который их отдаёт, × каждый
зритель. Для каждой пары — ожидаемый код и что из раскрываемого видно: ФИО, контакты, свободный
текст и ожидаемая зарплата приходят только тем, кому их отдаёт правило раскрытия.
"""

import io
import json
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
from tests.candidate_path import grant_category, publish_vacancy, with_company

Json = dict[str, Any]

PROFILE = {
    "full_name": "Ёлкина Юлия Сергеевна",
    "contact_email": "yulia.yolkina@example.ru",
    "contact_phone": "+7 999 123-45-67",
    "telegram": "yolkina_qa",
    "about": "Пишу автотесты, люблю разбирать флаки",
    # Selenium в потребности нет: в объяснении подборки его не будет, совпавший pytest — будет.
    "stack": ["pytest", "selenium"],
    "job_roles": ["тимлид"],
    "experience_years": 4,
    "soft_skills": ["Наставничество"],
    "work_formats": ["remote"],
    "city": "Казань",
    "relocation": True,
    "industries": ["healthcare"],
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
        Endpoint("обратная связь", "GET", lambda w: "/api/candidate/feedback"),
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
        Endpoint("отклики работодателя", "GET", lambda w: "/api/employer/applications"),
        Endpoint("отклики кандидата", "GET", lambda w: "/api/candidate/applications"),
    ]
}

# Эндпоинты, которые отдают работодателю данные кандидата или что-то о нём.
EMPLOYER_ENDPOINTS = (
    "карточка",
    "подборка: построение",
    "подборка: страница",
    "подборка: сохранённая",
    "приглашения работодателя",
    "отклики работодателя",
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
    ("обратная связь", Viewer.me, 200, NONE),
    ("обратная связь", Viewer.other, 200, NONE),
    ("обратная связь", Viewer.employer, 403, NONE),
    ("обратная связь", Viewer.anonymous, 401, NONE),
    ("отклики кандидата", Viewer.me, 200, NONE),
    ("отклики кандидата", Viewer.other, 200, NONE),
    ("отклики кандидата", Viewer.employer, 403, NONE),
    ("отклики кандидата", Viewer.anonymous, 401, NONE),
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


# Раскрытие работодателю по приглашениям и откликам (§14): каждый эндпоинт работодателя ×
# состояние приглашений и откликов этого кандидата. Раскрывает только принятое приглашение этой же
# компании или отклик на её вакансию в любом статусе, пока доступ не отозван, и ожидаемой зарплаты
# нет и тогда; раскрытое отдаёт одна карточка. Отзыв по приглашению или по отклику закрывает
# компании и то и другое; после отзыва раскрывает только новое принятое приглашение или новый
# отклик.
INVITATION_STATES = (
    "нет приглашения",
    "отправлено",
    "просмотрено",
    "отклонено",
    "истекло",
    "принято другой компанией",
    "принято",
    "принято и отозвано",
    "отозвано, принято новое",
    "откликнулся на вакансию",
    "откликнулся, отклик отклонён",
    "откликнулся на вакансию другой компании",
    "откликнулся и отозвал доступ",
    "откликнулся, доступ отозван по приглашению",
    "принято, доступ отозван по отклику",
    "отозвал доступ, откликнулся снова",
)
DISCLOSING = (
    "принято",
    "отозвано, принято новое",
    "откликнулся на вакансию",
    "откликнулся, отклик отклонён",
    "отозвал доступ, откликнулся снова",
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

    def apply(to: TestClient) -> str:
        vacancy = publish_vacancy(to)
        response = me.post(f"/api/candidate/vacancies/{vacancy['id']}/apply")
        assert response.status_code == 201, response.text
        application_id: str = response.json()["id"]
        return application_id

    def revoke_application(application_id: str) -> None:
        me.post(f"/api/candidate/applications/{application_id}/revoke").raise_for_status()

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
        case "принято и отозвано":
            invitation_id = invite(employer)
            act(invitation_id, "accept")
            act(invitation_id, "revoke")
        case "отозвано, принято новое":
            invitation_id = invite(employer)
            act(invitation_id, "accept")
            act(invitation_id, "revoke")
            act(invite(employer), "accept")
        case "откликнулся на вакансию":
            apply(employer)
        case "откликнулся, отклик отклонён":
            application_id = apply(employer)
            employer.post(f"/api/employer/applications/{application_id}/decline").raise_for_status()
        case "откликнулся на вакансию другой компании":
            apply(other_employer)
        case "откликнулся и отозвал доступ":
            revoke_application(apply(employer))
        case "откликнулся, доступ отозван по приглашению":
            apply(employer)
            invitation_id = invite(employer)
            act(invitation_id, "accept")
            act(invitation_id, "revoke")
        case "принято, доступ отозван по отклику":
            act(invite(employer), "accept")
            revoke_application(apply(employer))
        case "отозвал доступ, откликнулся снова":
            revoke_application(apply(employer))
            apply(employer)
        case _:
            raise AssertionError(state)


@pytest.mark.parametrize("state", INVITATION_STATES)
@pytest.mark.parametrize("endpoint", EMPLOYER_ENDPOINTS)
def test_employer_sees_candidate_disclosed_only_after_own_invitation_or_application(
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
    expected = DISCLOSED_TO_EMPLOYER if endpoint == "карточка" and state in DISCLOSING else NONE
    assert visible == expected


# Видимость полей самоописания (§14): кандидат скрывает их из обезличенной карточки. Как искать
# поле в ответе: строковые — по значению, которого нет ни в потребности, ни в объяснении
# подборки; стаж и переезд — по объекту самоописания в JSON или по словам в PDF.
HIDEABLE = ("stack", "experience_years", "city", "relocation", "industries")
MARKERS = {"stack": "Selenium", "city": "Казань", "industries": "Медицина"}
PDF_WORDS = MARKERS | {"experience_years": "Стаж в ИТ", "relocation": "готов к переезду"}


def self_reported_objects(node: object) -> list[Json]:
    """Объекты самоописания в JSON — у них и только у них есть стаж."""
    if isinstance(node, list):
        return [o for item in node for o in self_reported_objects(item)]
    if not isinstance(node, dict):
        return []
    found = [node] if "experience_years" in node else []
    return found + [o for value in node.values() for o in self_reported_objects(value)]


def parsed(text: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        return None


def shown(field: str, text: str, *, pdf: bool = False) -> bool:
    if pdf:
        return PDF_WORDS[field] in text
    if field in MARKERS:
        return MARKERS[field] in text
    return any(o[field] is not None for o in self_reported_objects(parsed(text)))


def hide(world: World, *fields: str) -> Json:
    response = world.clients[Viewer.me].put(
        "/api/candidate/profile", json=PROFILE | {"hidden": list(fields)}
    )
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def card_text(world: World) -> str:
    response = world.clients[Viewer.employer].get(f"/api/employer/candidates/{world.candidate_id}")
    assert response.status_code == 200, response.text
    return response.text


def test_nothing_is_hidden_by_default(world: World) -> None:
    own = world.clients[Viewer.me].get("/api/candidate/profile").json()
    text = card_text(world)

    assert own["hidden"] == []
    assert json.loads(text)["self_reported"]["hidden"] == []
    assert all(shown(field, text) for field in HIDEABLE)


@pytest.mark.parametrize("endpoint", EMPLOYER_ENDPOINTS)
@pytest.mark.parametrize("field", HIDEABLE)
def test_hidden_field_does_not_reach_employer_before_disclosure(
    world: World, field: str, endpoint: str
) -> None:
    hide(world, field)

    code, text = ENDPOINTS[endpoint].call(world, Viewer.employer)

    assert code < 300, text
    assert not shown(field, text)
    if endpoint == "карточка":
        assert json.loads(text)["self_reported"]["hidden"] == [field]
        assert all(shown(other, text) for other in HIDEABLE if other != field)


@pytest.mark.parametrize("field", HIDEABLE)
def test_hidden_field_is_disclosed_after_accepted_invitation(
    world: World,
    signed_in: Callable[[Role], TestClient],
    clock: FrozenClock,
    mechanics: Mechanics,
    field: str,
) -> None:
    hide(world, *HIDEABLE)
    other_employer = with_company(signed_in(Role.employer), "Другая компания")
    bring_to("принято", world, other_employer, clock, timedelta(days=mechanics.invitation_ttl_days))

    text = card_text(world)

    assert shown(field, text)
    assert json.loads(text)["self_reported"]["hidden"] == []


@pytest.mark.parametrize("field", HIDEABLE)
def test_candidate_sees_own_hidden_field_in_profile_and_pdf(world: World, field: str) -> None:
    saved = hide(world, field)

    assert saved["hidden"] == [field]
    for endpoint in ("профиль", "PDF"):
        e = ENDPOINTS[endpoint]
        code, text = e.call(world, Viewer.me)
        assert code == 200, text
        assert shown(field, text, pdf=e.pdf), endpoint


def test_hidden_fields_come_back_in_form_order_without_repeats(world: World) -> None:
    saved = hide(world, "industries", "stack", "industries")

    assert saved["hidden"] == ["stack", "industries"]


@pytest.mark.parametrize("hidden", [["salary_from"], ["work_formats"], ["about"], ["nope"]])
def test_unknown_hideable_field_is_rejected(world: World, hidden: list[str]) -> None:
    response = world.clients[Viewer.me].put(
        "/api/candidate/profile", json=PROFILE | {"hidden": hidden}
    )

    assert response.status_code == 422, response.text


def test_selection_score_and_order_do_not_depend_on_visibility(
    world: World, signed_in: Callable[[Role], TestClient], db_engine: Engine
) -> None:
    second = signed_in(Role.candidate)
    second.put(
        "/api/candidate/profile",
        json=PROFILE | {"full_name": "Второй Кандидат", "stack": ["selenium"]},
    ).raise_for_status()
    grant_category(db_engine, second.get("/api/auth/me").json()["id"])
    employer = world.clients[Viewer.employer]

    def build() -> list[tuple[str, float, float]]:
        response = employer.post(f"/api/employer/needs/{world.need_id}/selections")
        assert response.status_code == 201, response.text
        return [
            (e["candidate_id"], e["match_score"], e["mutual_score"])
            for e in response.json()["entries"]
        ]

    visible = build()
    hide(world, *HIDEABLE)
    hidden = build()

    assert len(visible) == 2
    assert hidden == visible


def test_card_of_applicant_without_category_opens_only_to_company_of_vacancy(
    signed_in: Callable[[Role], TestClient],
) -> None:
    candidate = signed_in(Role.candidate)
    candidate.put("/api/candidate/profile", json=PROFILE).raise_for_status()
    candidate_id: str = candidate.get("/api/auth/me").json()["id"]
    ours = with_company(signed_in(Role.employer))
    theirs = with_company(signed_in(Role.employer), "Другая компания")
    card = f"/api/employer/candidates/{candidate_id}"
    assert ours.get(card).status_code == 404

    vacancy = publish_vacancy(ours)
    candidate.post(f"/api/candidate/vacancies/{vacancy['id']}/apply").raise_for_status()

    response = ours.get(card)
    assert response.status_code == 200, response.text
    assert response.json()["category"] is None
    assert {name for name, marker in SECRETS.items() if marker in response.text} == (
        DISCLOSED_TO_EMPLOYER
    )
    assert theirs.get(card).status_code == 404
