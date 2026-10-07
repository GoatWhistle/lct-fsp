"""Видимость данных кандидата (mechanics.md, §14): каждый эндпоинт, который их отдаёт, × каждый
зритель. Для каждой пары — ожидаемый код и что из раскрываемого видно: ФИО, контакты, свободный
текст и ожидаемая зарплата приходят только тем, кому их отдаёт правило раскрытия.
"""

import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import Engine, insert, select

from app.assessment.models import CandidateCategory, Survey, TestAttempt, Topic
from app.identity.models import Role
from app.skills.models import SkillProfile, SkillProfileTopic
from tests.conftest import transaction

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
    ]
}

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
for endpoint in ("карточка", "подборка: построение", "подборка: страница", "подборка: сохранённая"):
    TABLE += [
        (endpoint, Viewer.me, 403, NONE),
        (endpoint, Viewer.other, 403, NONE),
        (endpoint, Viewer.employer, 201 if endpoint == "подборка: построение" else 200, NONE),
        (endpoint, Viewer.anonymous, 401, NONE),
    ]


def grant_category(db_engine: Engine, user_id: str) -> None:
    """Категория QA · Middle и профиль навыков — прямо в базу, без прохождения теста."""
    uid, survey, attempt, profile = uuid.UUID(user_id), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    with transaction(db_engine) as db:
        topics = db.scalars(select(Topic.code).where(Topic.specialization_code == "qa")).all()
        db.execute(
            insert(Survey),
            [
                {
                    "id": survey,
                    "user_id": uid,
                    "number": 1,
                    "specialization_code": "qa",
                    "created_at": now,
                }
            ],
        )
        db.execute(
            insert(TestAttempt),
            [
                {
                    "id": attempt,
                    "user_id": uid,
                    "number": 1,
                    "survey_id": survey,
                    "specialization_code": "qa",
                    "grade_code": "middle",
                    "started_at": now,
                }
            ],
        )
        db.execute(
            insert(CandidateCategory),
            [
                {
                    "user_id": uid,
                    "specialization_code": "qa",
                    "grade_code": "middle",
                    "attempt_id": attempt,
                    "assigned_at": now,
                }
            ],
        )
        db.execute(
            insert(SkillProfile),
            [
                {
                    "id": profile,
                    "user_id": uid,
                    "specialization_code": "qa",
                    "overall_theta": 0.5,
                    "overall_theta_sd": 0.4,
                    "observations": 20,
                    "last_signal_at": now,
                    "updated_at": now,
                }
            ],
        )
        db.execute(
            insert(SkillProfileTopic),
            [
                {"profile_id": profile, "topic_code": t, "theta": 0.5, "theta_sd": 0.4}
                for t in topics
            ],
        )


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
