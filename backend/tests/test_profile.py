"""Профиль кандидата через HTTP API: форма, PDF-профиль и карточка для работодателя."""

import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from pypdf.generic import DictionaryObject
from sqlalchemy import Engine

from app.domain.account import Role
from app.repository.orm import Survey
from tests.candidate_path import (
    answer_items,
    everything,
    nothing,
    pass_test,
    start,
    take_survey,
)
from tests.conftest import Seeds, transaction

PROFILE = "/api/candidate/profile"
PDF = f"{PROFILE}/pdf"
CARD = "/api/employer/candidates/{}"

Json = dict[str, Any]
SignIn = Callable[[Role], TestClient]


@pytest.fixture
def candidate(signed_in: SignIn) -> TestClient:
    return signed_in(Role.candidate)


@pytest.fixture
def employer(signed_in: SignIn) -> TestClient:
    return signed_in(Role.employer)


def profile_body(**changes: Any) -> Json:
    body: Json = {
        "full_name": "  Ёлкина Юлия Сергеевна  ",
        "contact_email": "Yulia.Yolkina@Example.ru",
        "contact_phone": "+7 999 123-45-67",
        "telegram": "https://t.me/yolkina_qa",
        "about": "Пишу автотесты на pytest, люблю разбирать флаки",
        "stack": ["python", "postgresql"],
        "job_roles": ["QA-инженер", " тимлид ", "qa-инженер", ""],
        "experience_years": 4,
        "soft_skills": ["Наставничество", "Публичные выступления"],
        "work_formats": ["remote", "hybrid"],
        "city": "Казань",
        "relocation": True,
        "industries": ["it-products", "fintech"],
        "salary_from": 287_500,
    }
    return body | changes


def candidate_id(c: TestClient) -> str:
    user_id: str = c.get("/api/auth/me").json()["id"]
    return user_id


def pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)


def font_names(content: bytes) -> set[str]:
    """Шрифты, которыми набран текст PDF."""
    names = set()
    for page in PdfReader(io.BytesIO(content)).pages:
        fonts = cast(DictionaryObject, cast(DictionaryObject, page["/Resources"])["/Font"])
        for font in fonts.values():
            names.add(str(cast(DictionaryObject, font.get_object())["/BaseFont"]))
    return names


def test_profile_is_empty_until_filled(candidate: TestClient) -> None:
    response = candidate.get(PROFILE)

    assert response.status_code == 200
    assert response.json() is None


def test_candidate_fills_profile(candidate: TestClient) -> None:
    response = candidate.put(PROFILE, json=profile_body())

    assert response.status_code == 200, response.text
    profile = candidate.get(PROFILE).json()
    assert profile == response.json()
    assert profile["full_name"] == "Ёлкина Юлия Сергеевна"
    assert profile["contact_email"] == "yulia.yolkina@example.ru"
    assert profile["telegram"] == "yolkina_qa"
    assert profile["stack"] == [
        {"code": "postgresql", "name": "PostgreSQL"},
        {"code": "python", "name": "Python"},
    ]
    assert profile["job_roles"] == ["QA-инженер", "тимлид"]
    assert profile["work_formats"] == ["hybrid", "remote"]
    assert profile["experience_years"] == 4
    assert profile["salary_from"] == 287_500
    assert profile["salary_basis"] == "gross"
    assert (profile["city"], profile["relocation"]) == ("Казань", True)
    # Интересные сферы — в порядке справочника, а не ввода.
    assert profile["industries"] == [
        {"code": "fintech", "name": "Финтех и банки"},
        {"code": "it-products", "name": "ИТ-продукты и аутсорс"},
    ]


def test_interesting_industries_are_optional(candidate: TestClient) -> None:
    body = profile_body()
    del body["industries"]

    response = candidate.put(PROFILE, json=body)

    assert response.status_code == 200, response.text
    assert response.json()["industries"] == []


def test_interesting_industries_come_from_catalog(candidate: TestClient) -> None:
    response = candidate.put(PROFILE, json=profile_body(industries=["fintech", "alchemy"]))

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_industry"
    assert candidate.get(PROFILE).json() is None


def test_one_line_fields_collapse_line_breaks(candidate: TestClient) -> None:
    response = candidate.put(
        PROFILE,
        json=profile_body(
            full_name="Ёлкина\nЮлия\r\n\tСергеевна",
            job_roles=["QA-\n\n\nинженер", "\n\n"],
            soft_skills=["Наставни\nчество"],
            city="Нижний\n\nНовгород\n",
        ),
    )

    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["full_name"] == "Ёлкина Юлия Сергеевна"
    assert profile["job_roles"] == ["QA- инженер"]
    assert profile["soft_skills"] == ["Наставни чество"]
    assert profile["city"] == "Нижний Новгород"


def test_pdf_survives_line_breaks_in_one_line_fields(candidate: TestClient) -> None:
    # Без схлопывания переводы строк растягивают PDF на страницы, а строка таблицы выше
    # страницы роняет его с 500.
    candidate.put(
        PROFILE,
        json=profile_body(
            full_name="Ёлкина" + "\n" * 150 + "Юлия",
            job_roles=["\n" * 90 + "QA"],
            soft_skills=[f"навык {i}" + "\n" * 40 for i in range(15)],
            city="Казань" + "\n" * 90,
        ),
    ).raise_for_status()

    response = candidate.get(PDF)

    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.content)).pages) == 1


def test_candidate_edits_profile(candidate: TestClient) -> None:
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = candidate.put(
        PROFILE,
        json=profile_body(
            stack=["java"], contact_phone="", telegram="@yolkina_lead", soft_skills=[]
        ),
    )

    assert response.status_code == 200, response.text
    profile = candidate.get(PROFILE).json()
    assert profile["stack"] == [{"code": "java", "name": "Java"}]
    assert (profile["contact_phone"], profile["telegram"]) == (None, "yolkina_lead")
    assert profile["soft_skills"] == []


def test_stack_comes_from_catalog(candidate: TestClient) -> None:
    response = candidate.put(PROFILE, json=profile_body(stack=["python", "cobol-on-wheels"]))

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_technology"
    assert candidate.get(PROFILE).json() is None


def test_city_is_required_unless_only_remote(candidate: TestClient) -> None:
    office = candidate.put(PROFILE, json=profile_body(work_formats=["office"], city=" "))
    remote = candidate.put(PROFILE, json=profile_body(work_formats=["remote"], city=None))

    assert office.status_code == 422
    assert office.json()["code"] == "city_required"
    assert remote.status_code == 200, remote.text
    assert remote.json()["city"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": "   "},
        {"contact_email": "не почта"},
        {"telegram": "@abc"},
        {"telegram": "имя_по-русски"},
        {"experience_years": -1},
        {"experience_years": 2.5},
        {"salary_from": 0},
        {"salary_from": "сто тысяч"},
        {"work_formats": []},
        {"work_formats": ["office", "space"]},
        {"job_roles": [f"роль {i}" for i in range(11)]},
        {"soft_skills": ["очень длинный софт-скилл " * 3]},
    ],
)
def test_invalid_profile_is_rejected(candidate: TestClient, changes: Json) -> None:
    response = candidate.put(PROFILE, json=profile_body(**changes))

    assert response.status_code == 422
    assert candidate.get(PROFILE).json() is None


def test_candidate_sees_and_changes_only_own_profile(
    signed_in: SignIn, candidate: TestClient
) -> None:
    candidate.put(PROFILE, json=profile_body()).raise_for_status()
    other = signed_in(Role.candidate)

    assert other.get(PROFILE).json() is None
    assert other.get(PDF).status_code == 404
    other.put(PROFILE, json=profile_body(full_name="Другой Кандидат")).raise_for_status()
    assert candidate.get(PROFILE).json()["full_name"] == "Ёлкина Юлия Сергеевна"


def test_candidate_cannot_read_candidate_card(signed_in: SignIn, candidate: TestClient) -> None:
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = signed_in(Role.candidate).get(CARD.format(candidate_id(candidate)))

    assert response.status_code == 403
    assert response.json()["code"] == "wrong_role"


@pytest.mark.parametrize(("method", "path"), [("GET", PROFILE), ("PUT", PROFILE), ("GET", PDF)])
def test_employer_gets_403_on_candidate_profile_api(
    employer: TestClient, method: str, path: str
) -> None:
    response = employer.request(method, path, json=profile_body())

    assert response.status_code == 403
    assert response.json()["code"] == "wrong_role"


def test_pdf_needs_filled_profile(candidate: TestClient) -> None:
    response = candidate.get(PDF)

    assert response.status_code == 404
    assert response.json()["code"] == "profile_not_found"


def test_pdf_profile_before_test(candidate: TestClient) -> None:
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = candidate.get(PDF)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["cache-control"] == "no-store"
    text = pdf_text(response.content)
    assert "Ёлкина Юлия Сергеевна" in text
    assert "yulia.yolkina@example.ru" in text
    assert "@yolkina_qa" in text
    # Стек набран отдельными плашками, а не строкой через запятую.
    assert "PostgreSQL" in text and "Python" in text
    assert "4 года" in text
    assert "Финтех и банки" in text
    assert "Категория пока не присвоена" in text
    # Кириллица набрана встроенными шрифтами бренда, а не стандартным шрифтом без кириллицы.
    fonts = font_names(response.content)
    assert fonts and all(("Onest" in n) or ("JetBrainsMono" in n) for n in fonts), fonts
    # Ожидаемая зарплата в PDF не попадает: файл может оказаться у работодателя.
    assert "287" not in text


def test_pdf_profile_has_category_and_skill_profile(
    candidate: TestClient, seeds: Seeds, client: TestClient
) -> None:
    band = pass_test(candidate, seeds)["profile"]["overall"]["band"]
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = candidate.get(PDF)

    assert response.status_code == 200
    text = pdf_text(response.content)
    lines = text.splitlines()
    assert "QA" in lines and "Middle" in lines
    # Заголовок «Общий уровень» стоит дважды: плашка сводки и раздел теста; сводка — строкой ниже.
    overall = lines[len(lines) - 1 - lines[::-1].index("Общий уровень") + 1].lower()
    assert band["low"] in overall and band["high"] in overall
    qa = next(s for s in client.get("/api/catalog/specializations").json() if s["code"] == "qa")
    for topic in qa["topics"]:
        assert topic["name"] in text


def test_pdf_has_no_skill_profile_without_category(candidate: TestClient, seeds: Seeds) -> None:
    # Попытка на middle без верных ответов: профиль навыков посчитан, категории нет —
    # стажёру предложен дотест на junior.
    take_survey(candidate)
    start(candidate, "middle")
    assert answer_items(candidate, seeds, nothing)["stage"] == "offer"
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    text = pdf_text(candidate.get(PDF).content)

    assert "Категория пока не присвоена" in text
    # Раздел теста остаётся с пометкой «появится после теста», самого профиля нет.
    assert "Профиль навыков появится после адаптивного теста." in text
    assert "Шкала показывает уровень и погрешность" not in text
    assert "Общий уровень — " not in text


def test_employer_card_hides_contacts_free_text_and_expected_salary(
    candidate: TestClient, employer: TestClient, seeds: Seeds
) -> None:
    pass_test(candidate, seeds)
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = employer.get(CARD.format(candidate_id(candidate)))

    assert response.status_code == 200, response.text
    card = response.json()
    assert card["id"] == candidate_id(candidate)
    assert card["category"]["specialization"]["code"] == "qa"
    assert card["category"]["grade"]["code"] == "middle"
    assert len(card["skill_profile"]["topics"]) == 5
    assert card["self_reported"] == {
        "stack": [
            {"code": "postgresql", "name": "PostgreSQL"},
            {"code": "python", "name": "Python"},
        ],
        "experience_years": 4,
        "work_formats": ["hybrid", "remote"],
        "city": "Казань",
        "relocation": True,
        "industries": [
            {"code": "fintech", "name": "Финтех и банки"},
            {"code": "it-products", "name": "ИТ-продукты и аутсорс"},
        ],
        "hidden": [],
    }
    for hidden in (
        "Ёлкина",
        "yulia.yolkina",
        "123-45-67",
        "yolkina_qa",
        "флаки",
        # Роли и софт-скиллы — свободный текст: в метку можно вписать имя или контакт.
        "тимлид",
        "Наставничество",
        "287500",
        "salary",
        "contact",
        "full_name",
    ):
        assert hidden not in response.text, hidden


def test_card_without_filled_profile(
    candidate: TestClient, employer: TestClient, seeds: Seeds
) -> None:
    pass_test(candidate, seeds)

    card = employer.get(CARD.format(candidate_id(candidate))).json()

    assert card["category"]["grade"]["code"] == "middle"
    assert card["self_reported"] is None


MIDDLE = {"code": "middle", "name": "Middle"}


def test_card_of_a_confirmed_grade(
    candidate: TestClient, employer: TestClient, seeds: Seeds
) -> None:
    pass_test(candidate, seeds)

    card = employer.get(CARD.format(candidate_id(candidate))).json()

    assert card["grade_status"] == {"kind": "confirmed", "claimed": MIDDLE, "confirmed": MIDDLE}


def test_card_of_a_category_below_the_claim(
    candidate: TestClient, employer: TestClient, seeds: Seeds
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    assert answer_items(candidate, seeds, nothing)["offer_grade"] == "junior"
    start(candidate, "junior")
    # Каскад мог спуститься и ниже junior: важно, что категория ниже заявки.
    confirmed = answer_items(candidate, seeds, everything)["category"]["grade"]
    assert confirmed != MIDDLE

    card = employer.get(CARD.format(candidate_id(candidate))).json()

    assert card["grade_status"] == {
        "kind": "below_claimed",
        "claimed": MIDDLE,
        "confirmed": confirmed,
    }


def test_card_of_an_unconfirmed_claim_is_anonymized(
    candidate: TestClient, employer: TestClient, seeds: Seeds
) -> None:
    take_survey(candidate)
    start(candidate, "middle")
    assert answer_items(candidate, seeds, nothing)["stage"] == "offer"
    candidate.put(PROFILE, json=profile_body()).raise_for_status()

    response = employer.get(CARD.format(candidate_id(candidate)))

    assert response.status_code == 200, response.text
    card = response.json()
    assert card["grade_status"] == {"kind": "unconfirmed", "claimed": MIDDLE, "confirmed": None}
    assert (card["category"], card["skill_profile"]) == (None, None)
    assert card["self_reported"]["experience_years"] == 4
    for hidden in ("Ёлкина", "yulia.yolkina", "123-45-67", "yolkina_qa", "287500", "contact"):
        assert hidden not in response.text, hidden


def test_card_keeps_the_claim_after_a_new_survey(
    candidate: TestClient, employer: TestClient, seeds: Seeds, db_engine: Engine
) -> None:
    """Сохранённая подборка могла показать кандидата нижним блоком: смена направления карточку
    не отнимает, статус — по последней попытке."""
    take_survey(candidate)
    start(candidate, "middle")
    assert answer_items(candidate, seeds, nothing)["stage"] == "offer"
    with transaction(db_engine) as session:
        session.add(
            Survey(
                user_id=uuid.UUID(candidate_id(candidate)),
                number=2,
                specialization_code="backend",
                created_at=datetime.now(UTC),
            )
        )

    response = employer.get(CARD.format(candidate_id(candidate)))

    assert response.status_code == 200, response.text
    assert response.json()["grade_status"]["claimed"] == MIDDLE


def test_card_exists_only_for_candidates_with_category_or_claim(
    candidate: TestClient, employer: TestClient
) -> None:
    candidate.put(PROFILE, json=profile_body()).raise_for_status()
    # Опрос без выбранного грейда — заявки нет.
    take_survey(candidate)

    for unknown in (candidate_id(candidate), candidate_id(employer), str(uuid.uuid4())):
        response = employer.get(CARD.format(unknown))
        assert response.status_code == 404
        assert response.json()["code"] == "candidate_not_found"
