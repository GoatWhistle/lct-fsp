"""Сценарий чат-поиска (mechanics.md, §16): текст работодателя → вызов тех же сценариев, что у
формы, → выдача и пересказ.

Инструменты агента — `parse_need` (разбор потребности), `build_selection` (подборка функцией скора),
`apply_filters` (фильтры подборки) — это сценарии `NeedDrafts` и `Selections`, своей логики у чата
нет. Модель за `Completion` только выбирает, что вызвать, и пишет пересказ; список кандидатов —
ровно вывод инструментов в их порядке. Без модели, по сбою и таймауту чат недоступен —
работодатель идёт путём руками.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.domain.chat import (
    SCHEMA,
    SYSTEM,
    AgentAnswer,
    Card,
    ChatReply,
    Chip,
    checked_summary,
    read_answer,
)
from app.domain.errors import ChatUnavailable, StepUnavailable
from app.domain.need import NeedForm
from app.domain.need_draft import CheckedDraft
from app.domain.search import CandidateFilters
from app.domain.selection import Page
from app.domain.work import WorkFormat
from app.usecase.interface import Completion, ModelRequest
from app.usecase.need_draft import NeedDrafts
from app.usecase.selection import Selections

log = logging.getLogger(__name__)

PAGE = 20


def form_of(draft: CheckedDraft) -> NeedForm | None:
    """Форма потребности по разобранному тексту; без специализации и грейда — `None`."""
    if draft.specialization is None or draft.grade is None:
        return None
    return NeedForm(
        title=draft.title or "Вакансия",
        team_description="",
        specialization=draft.specialization.code,
        grade=draft.grade.code,
        stack=tuple(t.code for t in draft.stack),
        topic_importance={},
        work_format=draft.work_format or WorkFormat.remote,
        city=draft.city,
        salary_from=draft.salary_from,
        salary_to=draft.salary_to,
    )


class SearchChat:
    def __init__(
        self,
        drafts: NeedDrafts,
        selections: Selections,
        complete: Completion | None,
        *,
        timeout: float,
    ) -> None:
        self._drafts = drafts
        self._selections = selections
        self._complete = complete
        self._timeout = timeout
        self._pool = ThreadPoolExecutor(thread_name_prefix="search-chat")

    @property
    def available(self) -> bool:
        return self._complete is not None

    def send(self, user_id: uuid.UUID, message: str, selection_id: uuid.UUID | None) -> ChatReply:
        """Одно сообщение работодателя. `selection_id` — подборка, начатая раньше (в чате или в
        форме): сообщение без текста вакансии уточняет её фильтрами."""
        answer = self._ask(message)
        page = self._tools(user_id, answer, selection_id)
        chips = self._chips(answer)
        cards = tuple(
            Card(
                str(e.candidate_id),
                e.position,
                e.block.value,
                e.grade.code,
                e.match_score,
            )
            for e in page.entries
        )
        total = sum(page.filtered_totals.values())
        summary = checked_summary(answer.summary, [total, *page.filtered_totals.values()], cards)
        return ChatReply(str(page.selection.id), cards, chips, summary, total)

    def _ask(self, message: str) -> AgentAnswer:
        if self._complete is None:
            raise ChatUnavailable()
        request = ModelRequest(system=SYSTEM, user=message, schema=SCHEMA)
        future = self._pool.submit(self._complete, request)
        try:
            answer = read_answer(future.result(timeout=self._timeout))
        except FutureTimeout:
            future.cancel()
            raise ChatUnavailable() from None
        except Exception as e:
            log.warning("чат: модель не ответила: %r", e)
            raise ChatUnavailable() from e
        if answer is None:
            raise ChatUnavailable()
        return answer

    def _tools(
        self, user_id: uuid.UUID, answer: AgentAnswer, selection_id: uuid.UUID | None
    ) -> Page:
        """parse_need → build_selection → apply_filters: те же сценарии, что у формы."""
        filters = CandidateFilters(
            specialization=answer.specialization,
            grade=answer.grade,
            stack=frozenset(answer.stack),
            fsp_confirmed=answer.fsp_confirmed,
            confident=answer.confident,
        )
        if answer.need_text:
            parsed = self._drafts.parse(answer.need_text)
            form = form_of(parsed) if isinstance(parsed, CheckedDraft) else None
            if form is None:
                raise StepUnavailable()
            selection_id = self._selections.build_draft(user_id, form, limit=1).selection.id
        if selection_id is None:
            raise StepUnavailable()
        return self._selections.refine(user_id, selection_id, filters, offset=0, limit=PAGE)

    @staticmethod
    def _chips(answer: AgentAnswer) -> tuple[Chip, ...]:
        chips = [Chip("stack", s) for s in answer.stack]
        if answer.fsp_confirmed:
            chips.append(Chip("fsp", "true"))
        if answer.confident:
            chips.append(Chip("confident", "true"))
        if answer.grade:
            chips.append(Chip("grade", answer.grade))
        if answer.specialization:
            chips.append(Chip("specialization", answer.specialization))
        return tuple(chips)
