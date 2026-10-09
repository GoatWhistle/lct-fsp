"""Модель по имени в отдельных процессах, у каждого — свой каталог конфигурации CLI.

Модель через Agent SDK на каждый вопрос поднимает процесс CLI, а тот пишет свой конфиг. Десятки
параллельных вопросов с общим конфигом портят файл друг другу — и конфиг пользователя вместе с
ними. Здесь каждый процесс пула получает свой `CLAUDE_CONFIG_DIR`. Вход — симлинк на файл
учётных данных пользователя: сам токен не копируется, а обновлённый CLI пишет туда же.
"""

import os
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from app.adapter.text_model import Completion, ModelRequest

CONFIG_ENV = "CLAUDE_CONFIG_DIR"
CREDENTIALS = ".credentials.json"

_completion: Completion | None = None


def user_config_dir() -> Path:
    return Path(os.environ.get(CONFIG_ENV) or Path.home() / ".claude")


def _isolate(root: str, credentials: str, name: str, timeout: float) -> None:
    """Инициализация процесса пула: свой каталог конфигурации и модель в нём."""
    global _completion
    from composition import named_completion

    own = Path(root) / f"w{os.getpid()}"
    own.mkdir()
    (own / CREDENTIALS).symlink_to(credentials)
    os.environ[CONFIG_ENV] = str(own)
    _completion = named_completion(name, timeout)


def _ask(request: ModelRequest) -> str:
    assert _completion is not None
    return _completion(request)


class IsolatedCompletion:
    """`Completion` поверх пула из `workers` процессов; `model` — какая модель отвечает. Вызывать
    из `workers` потоков: каждый ждёт свой процесс. После работы — `close`: каталоги удаляются."""

    def __init__(self, name: str, timeout: float, workers: int, model: str | None) -> None:
        credentials = user_config_dir() / CREDENTIALS
        if not credentials.exists():
            raise SystemExit(f"нет {credentials}: войдите в CLI или задайте ключ API")
        self.model = model
        self._root = tempfile.mkdtemp(prefix="b3-config-")
        self._pool = ProcessPoolExecutor(
            workers,
            initializer=_isolate,
            initargs=(self._root, str(credentials.resolve()), name, timeout),
        )

    def __call__(self, request: ModelRequest) -> str:
        return self._pool.submit(_ask, request).result()

    def close(self) -> None:
        self._pool.shutdown()
        shutil.rmtree(self._root, ignore_errors=True)
