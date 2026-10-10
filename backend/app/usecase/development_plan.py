"""План развития кандидата на модели (mechanics.md, §15–§16): текст поверх подсказок обратной
связи. Модель — за `Completion`; без модели, по сбою и таймауту плана нет, кабинет показывает
подсказки как есть. Готовый план кэшируется до изменения профиля навыков."""

import logging
import uuid
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.adapter.text_model import Completion, ModelRequest
from app.domain.development_plan import (
    SYSTEM,
    DevelopmentPlan,
    fingerprint,
    prompt,
    read_plan,
    schema,
    usable,
)
from app.domain.feedback import Hint
from app.usecase.feedback import CandidateFeedback

log = logging.getLogger(__name__)


class DevelopmentPlans:
    def __init__(
        self,
        feedback: CandidateFeedback,
        complete: Completion | None,
        *,
        timeout: float,
        cache: dict[tuple[uuid.UUID, str], DevelopmentPlan | None] | None = None,
    ) -> None:
        self._feedback = feedback
        self._complete = complete
        self._timeout = timeout
        self._pool = ThreadPoolExecutor(thread_name_prefix="development-plan")
        # Кэш живёт на процесс; ключ — кандидат и отпечаток профиля с подсказками.
        self._cache = cache if cache is not None else {}

    def own(self, candidate_id: uuid.UUID) -> DevelopmentPlan | None:
        """План по подсказкам кандидата или `None`: нет модели, нет подсказок с темой, сбой, таймаут
        или ответ не прошёл сверку."""
        if self._complete is None:
            return None
        result = self._feedback.own(candidate_id)
        hints = usable(result.hints)
        if not hints:
            return None
        levels = self._feedback.levels(candidate_id)
        key = (candidate_id, fingerprint(result.hints, levels))
        if key in self._cache:
            return self._cache[key]
        plan = self._ask(result.hints)
        # Кэш одного кандидата — один отпечаток: прежние планы устарели вместе с профилем.
        for old in [k for k in self._cache if k[0] == candidate_id]:
            del self._cache[old]
        self._cache[key] = plan
        return plan

    def _ask(self, hints: Sequence[Hint]) -> DevelopmentPlan | None:
        assert self._complete is not None
        topics = [h.topic.code for h in usable(hints) if h.topic is not None]
        request = ModelRequest(system=SYSTEM, user=prompt(hints), schema=schema(topics))
        future = self._pool.submit(self._complete, request)
        try:
            raw = future.result(timeout=self._timeout)
        except FutureTimeout:
            future.cancel()
            log.warning("модель не ответила за %s с — плана нет", self._timeout)
            return None
        except Exception as e:
            log.warning("модель не ответила: %r — плана нет", e)
            return None
        return read_plan(raw, hints)
