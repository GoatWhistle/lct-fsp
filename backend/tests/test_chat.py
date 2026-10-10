"""Чат-поиск (mechanics.md, §16): агент поверх сценариев подбора на стенде в памяти."""

import json
import uuid
from typing import Any

import pytest

from app.adapter.text_model import ModelRequest
from app.domain.chat import Card, checked_summary
from app.domain.errors import ChatUnavailable
from app.domain.search import NO_FILTERS, CandidateFilters
from app.usecase.chat import SearchChat, form_of
from settings import Mechanics, Settings
from validation.main import build_stand
from validation.market import Candidate, Market, warm
from validation.simulate import EMPLOYER

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
TEXT = "Ищем Middle QA-инженера. Стек: Python, pytest, PostgreSQL. Удалённо."


def answer(**changes: Any) -> str:
    base: dict[str, Any] = {
        "need_text": TEXT,
        "filters": {
            "stack": [],
            "fsp_confirmed": False,
            "confident": False,
            "grade": None,
            "specialization": None,
        },
        "summary": "Нашлись кандидаты.",
    }
    return json.dumps(base | changes)


@pytest.fixture(scope="module")
def market() -> Market:
    m = warm(Market("qa", MECHANICS, 7), 100)
    for i, (grade, level) in enumerate([("middle", 1.2), ("middle", 0.4), ("junior", -0.6)]):
        d = m.determine(Candidate(dict.fromkeys(m.prior.topics, level), grade))
        m.enlist(d.user, stack=frozenset({"pytest"} if i == 0 else ()), claimed=grade)
    return m


def chat(
    market: Market, reply: str | Exception, seen: list[ModelRequest] | None = None
) -> SearchChat:
    def complete(request: ModelRequest) -> str:
        if seen is not None:
            seen.append(request)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return SearchChat(market.stand.need_drafts(), market.stand.selections(), complete, timeout=5.0)


def form_cards(market: Market, filters: CandidateFilters = NO_FILTERS) -> list[str]:
    parsed = market.stand.need_drafts().parse(TEXT)
    form = form_of(parsed)  # type: ignore[arg-type]
    assert form is not None
    selections = market.stand.selections()
    page = selections.build_draft(EMPLOYER, form, limit=1)
    page = selections.refine(EMPLOYER, page.selection.id, filters, offset=0, limit=20)
    return [str(e.candidate_id) for e in page.entries]


def test_chat_list_equals_the_form_list(market: Market) -> None:
    reply = chat(market, answer()).send(EMPLOYER, TEXT, None)
    assert [c.candidate_id for c in reply.cards] == form_cards(market)
    assert reply.cards


def test_every_narrowing_is_a_visible_chip_and_removal_restores(market: Market) -> None:
    filters = {
        "stack": ["pytest"],
        "fsp_confirmed": False,
        "confident": False,
        "grade": None,
        "specialization": None,
    }
    narrowed = chat(market, answer(filters=filters)).send(EMPLOYER, TEXT, None)
    assert [(c.kind, c.value) for c in narrowed.chips] == [("stack", "pytest")]
    assert [c.candidate_id for c in narrowed.cards] == form_cards(
        market, CandidateFilters(stack=frozenset({"pytest"}))
    )
    assert len(narrowed.cards) < len(form_cards(market))

    cleared = chat(market, answer(need_text=None, summary="")).send(
        EMPLOYER, "сними фильтры", uuid.UUID(narrowed.selection_id)
    )
    assert not cleared.chips
    assert [c.candidate_id for c in cleared.cards] == form_cards(market)


def test_agent_cannot_add_a_candidate_outside_tool_output(market: Market) -> None:
    """Агент отвечает только фильтрами и текстом: «выдуманного» кандидата в ответе взять негде."""
    invented = answer(summary=f"Лучший — {uuid.uuid4()}")
    reply = chat(market, invented).send(EMPLOYER, TEXT, None)
    assert {c.candidate_id for c in reply.cards} <= set(form_cards(market))


def test_summary_with_foreign_numbers_is_dropped() -> None:
    cards = [Card("a", 1, "exact", "middle", 0.65)]
    assert checked_summary("Нашёлся 1 кандидат, соответствие 65 %.", [1], cards) is not None
    assert checked_summary("Нашлось 42 кандидата.", [1], cards) is None


def test_model_sees_only_the_message_and_not_personal_data(market: Market) -> None:
    seen: list[ModelRequest] = []
    chat(market, answer(), seen).send(EMPLOYER, TEXT, None)
    assert seen[0].user == TEXT
    text = (seen[0].system + seen[0].user).lower()
    for forbidden in ("email", "телефон", "фио", "зарплата кандидата"):
        assert forbidden not in text


def test_without_a_model_the_chat_is_unavailable(market: Market) -> None:
    broken = SearchChat(market.stand.need_drafts(), market.stand.selections(), None, timeout=1.0)
    assert not broken.available
    with pytest.raises(ChatUnavailable):
        broken.send(EMPLOYER, TEXT, None)
    with pytest.raises(ChatUnavailable):
        chat(market, RuntimeError("упала")).send(EMPLOYER, TEXT, None)
    with pytest.raises(ChatUnavailable):
        chat(market, "не json").send(EMPLOYER, TEXT, None)


def test_build_stand_is_untouched() -> None:
    assert build_stand(MECHANICS) is not None
