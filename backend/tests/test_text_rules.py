"""Разбор потребности на правилах (docs/adr/0002-text-understanding-port.md): что адаптер узнаёт в
тексте вакансии, вилка числами и честный ответ «вне справочника»."""

import socket
from typing import Any

import pytest

from app.adapter.catalog_file import load_catalog
from app.adapter.text_rules import SURE, UNSURE, RulesTextUnderstanding, load_synonyms
from app.domain.catalog import Catalog
from app.domain.need_draft import DraftField, NeedDraft, OutOfCatalog
from app.domain.work import WorkFormat
from settings import CATALOG_FILE, SYNONYMS_FILE

CATALOG = load_catalog(CATALOG_FILE)
RULES = RulesTextUnderstanding(load_synonyms(SYNONYMS_FILE))


def draft(text: str, catalog: Catalog = CATALOG) -> NeedDraft:
    result = RULES.need(text, catalog)
    assert isinstance(result, NeedDraft), result
    return result


VACANCY = """Senior Python-разработчик в команду платежей
Пишем сервисы на FastAPI, храним данные в PostgreSQL и Redis, очереди — Kafka.
Офис в Москве, можно гибрид. Зарплата от 350 до 450 тыс. руб.
"""


def test_vacancy_text_gives_draft_with_catalog_values() -> None:
    result = draft(VACANCY)

    assert result.title == "Senior Python-разработчик в команду платежей"
    assert result.specialization == "backend"
    assert result.grade == "senior"
    assert set(result.stack) == {"python", "fastapi", "postgresql", "redis", "kafka"}
    assert result.work_format == WorkFormat.hybrid
    assert result.city == "Москва"
    assert (result.salary_from, result.salary_to) == (350_000, 450_000)
    assert result.confidence[DraftField.specialization] == SURE
    assert result.confidence[DraftField.grade] == SURE


@pytest.mark.parametrize(
    ("text", "salary"),
    [
        ("Вилка от 200 до 300 тыс.", (200_000, 300_000)),
        ("Зарплата 200–300к", (200_000, 300_000)),
        ("Зарплата 200-300 k", (200_000, 300_000)),
        ("Оклад 200 000 — 300 000 рублей", (200_000, 300_000)),
        ("Доход до 350 000", (None, 350_000)),
        ("Зарплата до 350 000 ₽", (None, 350_000)),
        ("Оплата от 250 тысяч", (250_000, None)),
        ("Для руководителя — от 1,5 млн", (1_500_000, None)),
        ("Опыт от 3 до 5 лет", (None, None)),
        ("Без зарплаты в тексте", (None, None)),
        ("Зарплата 3000–4000 $", (None, None)),
    ],
)
def test_salary_is_parsed_into_numbers(text: str, salary: tuple[Any, Any]) -> None:
    result = draft(text)

    assert (result.salary_from, result.salary_to) == salary


def test_salary_without_range_is_empty_not_zero() -> None:
    result = draft("Ищем QA-инженера, удалённо")

    assert result.salary_from is None
    assert result.salary_to is None
    assert DraftField.salary not in result.confidence


def test_net_salary_is_kept_but_uncertain() -> None:
    result = draft("Бэкенд, 200–250 тыс. на руки")

    assert (result.salary_from, result.salary_to) == (200_000, 250_000)
    assert result.confidence[DraftField.salary] == UNSURE


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("Программист 1С\nДоработка конфигураций 1С:Предприятие, обмены", "1С"),
        ("Unity-разработчик в геймдев-студию\nПишем мобильные игры на C#", "Геймдев"),
        ("Инженер embedded\nПрошивки для микроконтроллеров STM32", "Встраиваемые системы"),
    ],
)
def test_text_out_of_catalog_gives_nearest_specializations(text: str, asked: str) -> None:
    result = RULES.need(text, CATALOG)

    assert isinstance(result, OutOfCatalog)
    assert result.asked == asked
    assert result.nearest


def test_mention_out_of_catalog_does_not_outweigh_named_specialization() -> None:
    result = draft("Python-разработчик\nИнтеграция с 1С и банками")

    assert result.specialization == "backend"


def test_specialization_by_stack_when_not_named_is_uncertain() -> None:
    result = draft("Нужен человек: React, TypeScript, Jest")

    assert result.specialization == "frontend"
    assert result.confidence[DraftField.specialization] == UNSURE


def test_grade_by_experience_is_uncertain() -> None:
    result = draft("Тестировщик, опыт от 3 лет")

    assert result.grade == "middle"
    assert result.confidence[DraftField.grade] == UNSURE


def test_short_synonym_is_a_whole_word() -> None:
    result = draft("Бэкенд на Java, ищем через google")

    assert "java" in result.stack
    assert "javascript" not in result.stack
    assert "go" not in result.stack


def test_nothing_recognized_gives_empty_draft() -> None:
    result = draft("Привет! Расскажу о себе позже.")

    assert result.specialization is None
    assert result.grade is None
    assert result.stack == ()
    assert result.work_format is None
    assert result.city is None


def test_parsing_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("разбор пошёл в сеть")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    assert isinstance(RULES.need(VACANCY, CATALOG), NeedDraft)


@pytest.mark.parametrize(
    ("text", "salary"),
    [
        ("Зарплата от 10 тыс. долларов", (None, None)),
        ("Работа с европейскими клиентами, от 250 000 до 300 000", (250_000, 300_000)),
    ],
)
def test_currency_is_found_by_whole_word(text: str, salary: tuple[Any, Any]) -> None:
    result = draft(text)

    assert (result.salary_from, result.salary_to) == salary


def test_experience_range_takes_lower_bound() -> None:
    result = draft("Тестировщик, опыт работы от 3 до 5 лет")

    assert result.grade == "middle"


def test_title_after_empty_lines_keeps_its_weight() -> None:
    result = draft("\n\nSenior QA-инженер\nРабота с бэкендом и бэкенд-командой")

    assert result.title == "Senior QA-инженер"
    assert result.specialization == "qa"
