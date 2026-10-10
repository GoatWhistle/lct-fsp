"""Адаптер Agent SDK на фейковом `query` — общие тесты модельного разбора, агент без инструментов и
настроек с диска, сборка по имени из окружения."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from app.adapter.demo.agent_sdk import AgentSdkCompletion
from app.adapter.text_model import Completion, ModelError, ModelRequest, WithFallback
from main import text_understanding
from settings import Settings
from tests.text_model_contract import (
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

# Каталог вне `tests/`: маркер уровня ставится здесь, а не в conftest.
pytestmark = pytest.mark.unit

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


class FakeQuery:
    """`query` Agent SDK: отвечает структурированным выводом того, что решит `brain`; медленный
    мозг — медленный ответ, как у CLI."""

    def __init__(self, brain: Brain) -> None:
        self.brain = brain
        self.options: list[ClaudeAgentOptions] = []

    async def __call__(self, *, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Any]:
        self.options.append(options)
        assert options.output_format is not None and isinstance(options.system_prompt, str)
        request = ModelRequest(options.system_prompt, prompt, options.output_format["schema"])
        output = await asyncio.to_thread(self.brain, request)
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=2,
            session_id="test",
            structured_output=output,
        )


@pytest.fixture
def scripted() -> Scripted:
    def make(brain: Brain, timeout: float) -> Completion:
        return AgentSdkCompletion("claude-sonnet-5-5", timeout, FakeQuery(brain))

    return make


def test_agent_has_no_tools_and_no_settings_from_disk() -> None:
    fake = FakeQuery(lambda _: answer(specialization="qa"))

    parse(AgentSdkCompletion("claude-sonnet-5-5", 2.0, fake))

    options = fake.options[0]
    assert options.tools == []
    assert options.setting_sources == []
    assert options.skills == []
    assert options.model == "claude-sonnet-5-5"
    assert options.output_format is not None
    assert options.output_format["type"] == "json_schema"
    assert options.output_format["schema"]["additionalProperties"] is False


def test_error_result_answers_by_rules() -> None:
    async def failing(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Any]:
        yield ResultMessage(
            subtype="error_max_turns",
            duration_ms=0,
            duration_api_ms=0,
            is_error=True,
            num_turns=3,
            session_id="test",
        )

    complete = AgentSdkCompletion("claude-sonnet-5-5", 2.0, failing)

    with pytest.raises(ModelError, match="error_max_turns"):
        complete(ModelRequest("", "", {}))


def test_assembly_finds_adapter_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """`TEXT_UNDERSTANDING=agent_sdk` — модель по имени из окружения с откатом на правила."""
    monkeypatch.setenv("TEXT_UNDERSTANDING", "agent_sdk")
    monkeypatch.setenv("AGENT_SDK_MODEL", "claude-opus-5-5")

    understanding = text_understanding(Settings())

    assert isinstance(understanding, WithFallback)
    complete = understanding._model._complete  # type: ignore[attr-defined]
    assert isinstance(complete, AgentSdkCompletion)
    assert complete.model == "claude-opus-5-5"


def test_structured_output_is_returned_as_json() -> None:
    raw = AgentSdkCompletion("m", 2.0, FakeQuery(lambda _: answer(grade="senior")))(
        ModelRequest("", "текст", {})
    )

    assert json.loads(raw)["grade"] == "senior"


@pytest.mark.parametrize("name", ["test_agent_sdk", "__init__", "_private"])
def test_assembly_skips_tests_and_service_modules(name: str) -> None:
    with pytest.raises(ValueError, match="неизвестный разбор текста"):
        text_understanding(Settings(text_understanding=name))
