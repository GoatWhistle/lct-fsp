"""Записанные ответы модели для M21: модель зовётся один раз, отчёт пересобирается без сети.

Запись — JSON рядом с набором: ключ — хэш запроса (системное сообщение, текст, схема), значение —
сырой ответ модели или её ошибка и время ответа. Повтор отдаёт записанное тем же путём, что ответ
модели: чтение ответа, откат на правила и проверку сценарием код проходит заново. Записанный
ответ дольше таймаута — таймаут, как в проде; время разбора в отчёте — записанное время модели.
Запись делается без таймаута: таймаут можно сменить и пересобрать отчёт из той же записи. Одна
запись — одна модель: дописать её ответами другой нельзя.

Время ответа — снаружи вызова модели, как его видит прод: со стартом клиента и при параллельной
записи — с соседними вопросами в очереди к модели.
"""

import hashlib
import json
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from app.adapter.text_model import Completion, ModelError, ModelRequest


@dataclass(frozen=True)
class Answer:
    raw: str | None
    error: str | None
    ms: float


def request_key(request: ModelRequest) -> str:
    payload = json.dumps(
        [request.system, request.user, request.schema], ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class Recording:
    """Файл записи: что за модель и ответы по ключу запроса."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.model: str | None = None
        self.answers: dict[str, Answer] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.model = data["model"]
            self.answers = {k: Answer(**v) for k, v in data["answers"].items()}
        self._lock = threading.Lock()

    def add(self, key: str, answer: Answer) -> None:
        with self._lock:
            self.answers[key] = answer

    def save(self) -> None:
        with self._lock:
            data = {
                "model": self.model,
                "answers": {k: asdict(a) for k, a in sorted(self.answers.items())},
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
            self.path.write_text(text, encoding="utf-8")


def record(
    recording: Recording,
    requests: Iterable[ModelRequest],
    live: Completion,
    *,
    workers: int,
    model: str | None,
) -> int:
    """Спросить модель о запросах, которых нет в записи, — `workers` параллельно; запись
    сохраняется после каждого ответа. Возвращает, сколько ответов добавлено."""
    missing = {request_key(r): r for r in requests if request_key(r) not in recording.answers}
    if recording.model and model and recording.model != model:
        raise ValueError(f"{recording.path.name} — ответы {recording.model}, а не {model}")
    recording.model = recording.model or model

    def ask(key: str, request: ModelRequest) -> None:
        start = time.perf_counter()
        try:
            raw, error = live(request), None
        except ModelError as e:
            raw, error = None, str(e)
        recording.add(key, Answer(raw, error, (time.perf_counter() - start) * 1000))
        recording.save()

    with ThreadPoolExecutor(max(1, workers)) as pool:
        for future in [pool.submit(ask, k, r) for k, r in missing.items()]:
            future.result()
    return len(missing)


class Replay:
    """`Completion` из записи. `take_ms` — сколько записанного времени модели набежало с прошлого
    вызова, `failed` — сколько ответов ушло в правила: ошибка или дольше таймаута, `missing` —
    сколько запросов не нашлось в записи. Нет ответа — тоже откат на правила, как у прода при
    любом сбое, поэтому отчёт проверяет `missing` сам."""

    def __init__(self, recording: Recording, timeout: float) -> None:
        self._recording = recording
        self._timeout_ms = timeout * 1000
        self._spent_ms = 0.0
        self.failed = 0
        self.missing = 0

    def __call__(self, request: ModelRequest) -> str:
        answer = self._recording.answers.get(request_key(request))
        if answer is None:
            self.missing += 1
            raise ModelError(f"в {self._recording.path.name} нет ответа на запрос")
        self._spent_ms += min(answer.ms, self._timeout_ms)
        if answer.error is not None or answer.raw is None:
            self.failed += 1
            raise ModelError(answer.error or "нет ответа")
        if answer.ms > self._timeout_ms:
            self.failed += 1
            raise ModelError("дольше таймаута")
        return answer.raw

    def take_ms(self) -> float:
        spent, self._spent_ms = self._spent_ms, 0.0
        return spent
