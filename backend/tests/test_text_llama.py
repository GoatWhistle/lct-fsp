"""Адаптер `llama-server` на фейковом HTTP-сервере (docs/adr/0002): общие тесты модельного разбора,
запрос в формате llama.cpp, ни одного соединения мимо адреса из конфига, сервис в compose под своим
profile и бэкенд без него."""

import json
import socket
import threading
from collections.abc import Iterator
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest
import yaml

from app.adapter.text_llama import LlamaCompletion
from app.adapter.text_model import Completion, ModelRequest, WithFallback
from app.adapter.text_rules import RulesTextUnderstanding
from app.domain.need_draft import CheckedDraft
from main import text_understanding
from settings import BACKEND_DIR, Settings
from tests.text_model_contract import (
    CATALOG,
    SYNONYMS,
    TEXT,
    Brain,
    Scripted,
    answer,
    parse,
    test_answer_inside_catalog_becomes_draft,
    test_answer_outside_catalog_is_dropped,
    test_instruction_in_text_stays_data_and_inside_catalog,
    test_model_failure_answers_by_rules,
    test_out_of_catalog_offers_only_catalog_specializations,
    test_resume_answer_outside_catalog_is_dropped,
    test_resume_instruction_stays_data,
    test_resume_model_failure_answers_by_rules,
    test_resume_schema_lists_only_catalog_values,
    test_resume_takes_model_fields_and_rules_contacts,
    test_resume_timeout_answers_by_rules,
    test_schema_lists_only_catalog_values,
    test_timeout_answers_by_rules_in_time,
    test_unreadable_answer_answers_by_rules,
)

__all__ = [
    "test_answer_inside_catalog_becomes_draft",
    "test_answer_outside_catalog_is_dropped",
    "test_instruction_in_text_stays_data_and_inside_catalog",
    "test_model_failure_answers_by_rules",
    "test_out_of_catalog_offers_only_catalog_specializations",
    "test_resume_answer_outside_catalog_is_dropped",
    "test_resume_instruction_stays_data",
    "test_resume_model_failure_answers_by_rules",
    "test_resume_schema_lists_only_catalog_values",
    "test_resume_takes_model_fields_and_rules_contacts",
    "test_resume_timeout_answers_by_rules",
    "test_schema_lists_only_catalog_values",
    "test_timeout_answers_by_rules_in_time",
    "test_unreadable_answer_answers_by_rules",
]

COMPOSE_FILE = BACKEND_DIR.parent / "docker-compose.yml"


class FakeLlama:
    """`llama-server` на локальном порту: `/v1/chat/completions` отвечает тем, что решит `brain`;
    исключение мозга — ответ 500. Запросы тела копит в `bodies`."""

    def __init__(self) -> None:
        self.brain: Brain = lambda _: answer()
        self.bodies: list[dict[str, Any]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.bodies.append(body)
                messages = body["messages"]
                request = ModelRequest(
                    system=messages[0]["content"],
                    user=messages[1]["content"],
                    schema=body["response_format"]["json_schema"]["schema"],
                )
                try:
                    content = json.dumps(fake.brain(request), ensure_ascii=False)
                except Exception:
                    self.send_response(500)
                    self.end_headers()
                    return
                reply = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)

            def log_message(self, *_: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        host, port = self.server.server_address[:2]
        self.url = f"http://{host!s}:{port}"
        self.address = (str(host), port)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def llama() -> Iterator[FakeLlama]:
    fake = FakeLlama()
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


@pytest.fixture
def scripted(llama: FakeLlama) -> Scripted:
    def make(brain: Brain, timeout: float) -> Completion:
        llama.brain = brain
        return LlamaCompletion(llama.url, "local", timeout)

    return make


def test_request_is_llama_chat_with_json_schema(llama: FakeLlama) -> None:
    """Схема — в `response_format`: из неё llama.cpp строит грамматику; температура нулевая."""
    parse(LlamaCompletion(llama.url, "yandexgpt-lite", 2.0))

    body = llama.bodies[0]
    assert body["model"] == "yandexgpt-lite"
    assert body["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == TEXT
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["required"]


def test_connects_only_to_configured_server(
    llama: FakeLlama, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Наружу ни одного соединения: только адрес `llama-server` из конфига, даже при прокси в
    окружении."""
    connected: list[tuple[str, int]] = []
    connect = socket.socket.connect

    def spy(sock: socket.socket, address: Any) -> None:
        connected.append(address)
        connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", spy)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example:3128")
    llama.brain = lambda _: answer(specialization="qa")

    draft = parse(LlamaCompletion(llama.url, "local", 2.0))

    assert isinstance(draft, CheckedDraft)
    assert connected and set(connected) == {llama.address}


def test_default_server_is_compose_service() -> None:
    """По умолчанию адрес — имя сервиса compose, а сам сервис поднимается только своим profile:
    в разработке и по умолчанию в сдаче его нет."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    service = urlparse(Settings().llama_url).hostname

    assert service in compose["services"]
    assert compose["services"][service]["profiles"] == ["llama"]
    assert "llama" not in compose["services"]["backend"].get("depends_on", {})
    assert Settings().text_understanding == "rules"


def test_backend_answers_without_llama_server() -> None:
    """`llama` в конфиге, а сервера нет: сборка не падает, разбор отвечает правилами."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    settings = Settings(
        text_understanding="llama",
        llama_url=f"http://127.0.0.1:{port}",
        text_understanding_timeout_seconds=2.0,
    )

    understanding = text_understanding(settings)

    assert isinstance(understanding, WithFallback)
    assert understanding.need(TEXT, CATALOG) == RulesTextUnderstanding(SYNONYMS).need(TEXT, CATALOG)


def test_unknown_name_fails_assembly() -> None:
    with pytest.raises(ValueError, match="неизвестный разбор текста"):
        text_understanding(Settings(text_understanding="gpt"))
    with pytest.raises(ValueError, match="неизвестный разбор текста"):
        text_understanding(Settings(text_understanding="../etc"))


def test_any_model_failure_answers_by_rules() -> None:
    """Сбой не из `ModelError` — кривой адрес в конфиге — тоже откат на правила, а не 500."""
    understanding = text_understanding(
        Settings(text_understanding="llama", llama_url="http://llama:80a")
    )

    assert understanding.need(TEXT, CATALOG) == RulesTextUnderstanding(SYNONYMS).need(TEXT, CATALOG)


def test_resume_asks_the_model_for_stack_roles_and_experience(llama: FakeLlama) -> None:
    """Резюме — правила и модель вместе (lct-91): модель получает видимый текст и схему со
    значениями справочника и словаря, ФИО и контакты достают правила."""
    understanding = text_understanding(Settings(text_understanding="llama", llama_url=llama.url))
    resume = "Иванова Мария Сергеевна\nmaria@example.ru\nPython, pytest"

    draft = understanding.resume(resume, CATALOG, date(2026, 10, 8))

    rules = RulesTextUnderstanding(SYNONYMS).resume(resume, CATALOG, date(2026, 10, 8))
    assert (draft.full_name, draft.contact_email) == (rules.full_name, rules.contact_email)
    assert len(llama.bodies) == 1
    assert llama.bodies[0]["messages"][1]["content"] == resume
