"""Векторы B2 — `intfloat/multilingual-e5-small` в ONNX, локально на CPU.

Веса и токенизатор — из Hugging Face Hub на закреплённой ревизии: в репо они не лежат, первый
прогон их скачивает в кэш Hub, следующие берут из кэша без сети. Вектор — среднее скрытых
состояний по токенам с маской внимания, нормированное на единицу, как в карточке модели.
Зависимости — группа `validation` в pyproject.toml: в прод-образ и в образ тестов они не идут.
"""

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MAX_TOKENS = 512
WORKERS = max(1, (os.cpu_count() or 2) - 1)


class E5Encoder:
    def __init__(self) -> None:
        try:
            import numpy as np
            import onnxruntime
            from huggingface_hub import hf_hub_download
            from tokenizers import Tokenizer
        except ImportError as e:
            raise SystemExit(
                "B2 нужна группа зависимостей validation: uv run --group validation …"
            ) from e
        self._np = np
        model = hf_hub_download(MODEL, "onnx/model.onnx", revision=REVISION)
        tokenizer = hf_hub_download(MODEL, "onnx/tokenizer.json", revision=REVISION)
        self._tokenizer = Tokenizer.from_file(tokenizer)
        self._tokenizer.enable_truncation(MAX_TOKENS)
        options = onnxruntime.SessionOptions()
        # Один поток — тот же результат на любой машине и параллельные прогоны не мешают.
        options.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(
            model, options, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        """Каждый текст — отдельным прогоном модели, без выравнивания по соседям; прогоны идут в
        `WORKERS` потоков: сессия ONNX потокобезопасна, а вектор от потока не зависит."""
        with ThreadPoolExecutor(WORKERS) as pool:
            return list(pool.map(self._one, texts))

    def _one(self, text: str) -> list[float]:
        np = self._np
        encoded = self._tokenizer.encode(text)
        ids = np.array([encoded.ids], dtype=np.int64)
        mask = np.array([encoded.attention_mask], dtype=np.int64)
        feeds: dict[str, Any] = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feeds)[0][0]
        pooled = (hidden * mask[0][:, None]).sum(axis=0) / mask[0].sum()
        pooled /= np.linalg.norm(pooled)
        return [float(x) for x in pooled]
