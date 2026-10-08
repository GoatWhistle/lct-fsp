"""M16 (б), набор D7 (docs/validation-plan.md): Claude Sonnet через Claude Agent SDK проходит
наш тест — определение категории с каскадом и, если результат подозрительный, проверочный блок.

Модель видит только задание банка: условие, листинг и варианты — как их видит кандидат на
фронте; данных кандидатов у неё нет. Ответ проверяет бэкенд. Время ответа — записанное время
модели плюс `COPY_SECONDS` на копирование задания и ответа. Истинного уровня у модели нет, поэтому
отчёт публикует грейд и долю помеченных попыток как есть.

Ответы записываются в репо (`validation.recorded`): живой прогон — `python -m validation llm
--record N`, с ключом API или входом Agent SDK; отчёт пересобирается из записи без сети. Путь
теста адаптивный и зависит от ответов, поэтому запись идёт вдоль пути: каждая попытка — на своей
копии прогретого банка со своим seed, и повтор по записи проходит тот же путь.
"""

import json
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.adapter.text_model import Completion, ModelError, ModelRequest
from app.domain.bank import AnswerFormat, Instance, get_family
from validation.market import Candidate, Market
from validation.population import D1, GeneratorParams
from validation.recorded import Answer, request_key
from validation.truth import Response

# Две специализации и по 20 попыток на каждую — план, D7.
SPECIALIZATIONS = ("backend", "qa")
ATTEMPTS = 20
# Помощник целится выше: заявляет старший грейд, каскад сам спустит ниже.
CLAIMED = "senior"
COPY_SECONDS = 10.0
PARAMS: GeneratorParams = D1

SYSTEM = (
    "Ты проходишь технический тест для ИТ-специалистов. Реши задание и верни только итоговый "
    "ответ в поле answer, без пояснений. Если ответ — буква варианта, верни одну букву. Если "
    "нужно упорядочить варианты, верни буквы всех вариантов подряд в верном порядке, например "
    "«KBXF». Иначе верни значение так, как его ввёл бы человек в поле ответа."
)
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "description": "Итоговый ответ"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def item_request(instance: Instance) -> ModelRequest:
    """Задание так, как его видит кандидат: условие, листинг, варианты с буквами."""
    parts = [instance.prompt]
    if instance.code:
        parts.append(f"```\n{instance.code}\n```")
    if instance.options:
        parts.append("\n".join(f"{o.letter}. {o.text}" for o in instance.options))
    match instance.answer_format:
        case AnswerFormat.CHOICE:
            parts.append("Ответ — буква одного варианта.")
        case AnswerFormat.ORDERING:
            parts.append("Ответ — буквы всех вариантов в верном порядке одной строкой.")
        case _:
            parts.append("Ответ — значение.")
    return ModelRequest(SYSTEM, "\n\n".join(parts), SCHEMA)


class Answering:
    """Ответы модели по ключу запроса: из записи, а чего нет — у живой модели `live`, если она
    есть. Новое копится в `added`; без живой модели нет ответа — `missing` растёт, задание
    считается неверным."""

    def __init__(self, known: Mapping[str, Answer], live: Completion | None = None) -> None:
        self.known = dict(known)
        self.live = live
        self.added: dict[str, Answer] = {}
        self.missing = 0

    def __call__(self, family_code: str, instance: Instance) -> Response:
        request = item_request(instance)
        key = request_key(request)
        found = self.known.get(key) or self.added.get(key)
        if found is None and self.live is not None:
            start = time.perf_counter()
            try:
                raw, error = self.live(request), None
            except ModelError as e:
                raw, error = None, str(e)
            found = self.added[key] = Answer(raw, error, (time.perf_counter() - start) * 1000)
        if found is None:
            self.missing += 1
            return Response(False, COPY_SECONDS)
        seconds = found.ms / 1000 + COPY_SECONDS
        if found.raw is None:
            return Response(False, seconds)
        try:
            answer = str(json.loads(found.raw)["answer"])
        except (ValueError, KeyError, TypeError):
            return Response(False, seconds)
        family = get_family(family_code)
        return Response(family.check(instance, answer), seconds)


@dataclass(frozen=True)
class LlmAttempt:
    """Попытка модели: грейд результата до проверочного блока, помечен ли он, категория после
    блока, заданий и верных в тесте."""

    specialization: str
    before: str | None
    flagged: bool
    after: str | None


def run_attempts(
    m: Market, code: str, indices: range, answering: Callable[[str, Instance], Response]
) -> list[LlmAttempt]:
    """Попытки модели на копиях прогретого банка `m` — у каждой свой seed."""
    found = []
    for i in indices:
        fork = m.fork(attempt_seed(code, i))
        fork.responder = answering
        d = fork.determine(Candidate({}, CLAIMED))
        after = d.grade
        if d.pending is not None:
            after = fork.verify(d.user).grade
        found.append(LlmAttempt(code, d.pending or d.grade, d.pending is not None, after))
    return found


def attempt_seed(code: str, index: int) -> int:
    """Seed копии банка попытки: запись и повтор по ней проходят один путь."""
    return random.Random(f"{PARAMS.seed}:{code}:d7:{index}").getrandbits(32)


def recording_path(directory: Path, model: str) -> Path:
    return directory / f"d7.{model}.json"
