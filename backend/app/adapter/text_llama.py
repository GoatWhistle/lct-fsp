"""Модель за `llama-server` из llama.cpp — `Completion` для `ModelTextUnderstanding`
(docs/adr/0002-text-understanding-port.md). Сервер — свой контейнер в compose: модель GGUF на CPU,
наружу адаптер не ходит, только на адрес из конфига.

Запрос — OpenAI-совместимый `/v1/chat/completions` со схемой ответа в `response_format`: сервер
переводит схему в грамматику и не даёт модели вывести ничего, кроме JSON по ней. Температура
нулевая — один и тот же текст разбирается одинаково.
"""

from typing import Any

import httpx

from app.adapter.text_model import ModelError, ModelRequest


class LlamaCompletion:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/") + "/v1/chat/completions"
        self._model = model
        self._client = httpx.Client(timeout=timeout, transport=transport, trust_env=False)

    def __call__(self, request: ModelRequest) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "need_draft", "strict": True, "schema": request.schema},
            },
        }
        try:
            response = self._client.post(self._url, json=body)
            response.raise_for_status()
            answer: Any = response.json()
            content = answer["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, LookupError, TypeError) as e:
            raise ModelError(f"llama-server: {e!r}") from e
        if not isinstance(content, str):
            raise ModelError("llama-server: ответ без текста")
        return content
