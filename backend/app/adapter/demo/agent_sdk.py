"""Claude через Claude Agent SDK — `Completion` для `ModelTextUnderstanding`: модель разработки,
тестов и демо. Включается `TEXT_UNDERSTANDING=agent_sdk`, модель — `AGENT_SDK_MODEL`, вход — как у
Agent SDK (`ANTHROPIC_API_KEY` или вход CLI).

Ответ — структурированный вывод по схеме запроса. Агенту не даётся ни одного инструмента, ни
настроек и навыков с диска: один вопрос — один ответ по схеме.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from app.adapter.text_model import Completion, ModelError, ModelRequest

MODEL_ENV = "AGENT_SDK_MODEL"
DEFAULT_MODEL = "claude-sonnet-5-5"
# Структурированный вывод — отдельный ход агента после ответа.
MAX_TURNS = 3

Query = Callable[..., AsyncIterator[Any]]


class AgentSdkCompletion:
    """`model` — какая модель отвечает: стенд пишет его в запись ответов."""

    def __init__(self, model: str, timeout: float, ask: Query = query) -> None:
        self.model = model
        self._timeout = timeout
        self._ask = ask

    def __call__(self, request: ModelRequest) -> str:
        try:
            return asyncio.run(asyncio.wait_for(self._answer(request), self._timeout))
        except ModelError:
            raise
        except TimeoutError as e:
            raise ModelError(f"Agent SDK: нет ответа за {self._timeout} с") from e
        except Exception as e:
            raise ModelError(f"Agent SDK: {e!r}") from e

    async def _answer(self, request: ModelRequest) -> str:
        options = ClaudeAgentOptions(
            system_prompt=request.system,
            model=self.model,
            output_format={"type": "json_schema", "schema": dict(request.schema)},
            tools=[],
            setting_sources=[],
            skills=[],
            max_turns=MAX_TURNS,
        )
        # Поток дочитывается до конца: выход из середины оставляет клиент SDK незакрытым.
        result: ResultMessage | None = None
        async for message in self._ask(prompt=request.user, options=options):
            if isinstance(message, ResultMessage):
                result = message
        if result is None:
            raise ModelError("Agent SDK: нет результата")
        if result.is_error or result.structured_output is None:
            raise ModelError(f"Agent SDK: {result.subtype}, {result.errors or ''}")
        return json.dumps(result.structured_output, ensure_ascii=False)


def completion(timeout: float) -> Completion:
    """Точка входа для сборки по имени."""
    return AgentSdkCompletion(os.environ.get(MODEL_ENV, DEFAULT_MODEL), timeout)
