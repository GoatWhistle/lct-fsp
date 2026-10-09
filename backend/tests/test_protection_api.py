"""Защита теста через HTTP API и Postgres (mechanics.md, §8): подозрительный результат ждёт
проверочного блока, блок подтверждает категорию, а работодатель видит только итоговую пометку —
ни флагов, ни событий, ни статуса подозрения."""

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.domain.account import Role
from settings import Mechanics
from tests.candidate_path import ITEM, PATH, RUNNER, WRONG, presented, take_survey, with_company
from tests.conftest import Seeds

Json = dict[str, Any]

# Что работодатель видеть не должен: сигналы защиты и сам факт подозрения.
FORBIDDEN = (
    "time_flag",
    "focus",
    "paste",
    "suspici",
    "withheld",
    "dropped",
    "compromised",
    "expected_correct",
    "mismatch",
)


def _answer(
    c: TestClient, seeds: Seeds, *, correct: bool, focus_losses: int, more: Callable[[Json], bool]
) -> Json:
    path: Json = c.get(PATH).json()
    while more(path):
        item = c.get(ITEM).json()
        family, seed = presented(seeds, item)
        response = family.instance(seed, RUNNER).answer if correct else WRONG
        answered = c.post(
            f"{ITEM}/answer",
            json={
                "presentation_id": item["id"],
                "response": response,
                "focus_losses": focus_losses,
            },
        )
        assert answered.status_code == 200, answered.text
        path = answered.json()
    return path


def _in_test(path: Json) -> bool:
    return bool(path["stage"] == "test")


def _in_block(path: Json) -> bool:
    return path["verification"] is not None and path["verification"]["progress"] is not None


def _employer_texts(employer: TestClient, candidate_id: str) -> list[str]:
    need = employer.post(
        "/api/employer/needs",
        json={
            "title": "QA-инженер",
            "specialization": "qa",
            "grade": "middle",
            "stack": ["pytest"],
            "work_format": "remote",
        },
    )
    need.raise_for_status()
    selection = employer.post(f"/api/employer/needs/{need.json()['id']}/selections")
    selection.raise_for_status()
    card = employer.get(f"/api/employer/candidates/{candidate_id}")
    card.raise_for_status()
    return [selection.text, card.text]


def test_suspicious_result_waits_for_block_and_employer_sees_only_the_mark(
    signed_in: Callable[[Role], TestClient], seeds: Seeds, mechanics: Mechanics
) -> None:
    candidate, employer = signed_in(Role.candidate), signed_in(Role.employer)
    with_company(employer)
    candidate_id: str = candidate.get("/api/auth/me").json()["id"]
    take_survey(candidate)
    started = candidate.post(f"{PATH}/attempts", json={"grade": "middle", "focus_consent": True})
    assert started.status_code == 200, started.text
    path = _answer(
        candidate,
        seeds,
        correct=True,
        focus_losses=mechanics.focus_events_for_verification,
        more=_in_test,
    )
    assert path["stage"] == "verification" and path["category"] is None
    assert path["verification"]["grade"] == "middle"

    # Пока блок не пройден, категории нет и работодатель кандидата в категории не видит.
    card = employer.get(f"/api/employer/candidates/{candidate_id}").json()
    assert card["category"] is None
    for text in [json.dumps(card)]:
        assert not any(word in text for word in FORBIDDEN), text

    again = candidate.post(f"{PATH}/attempts", json={"grade": "middle"})
    assert again.status_code == 409 and again.json()["code"] == "verification_pending"

    block = candidate.post(f"{PATH}/verification")
    assert block.status_code == 200, block.text
    item = candidate.get(ITEM).json()
    assert item["verification"] and item["deadline"] is not None
    path = _answer(candidate, seeds, correct=True, focus_losses=0, more=_in_block)
    assert path["stage"] == "category"
    assert path["category"]["grade"]["code"] == "middle"
    assert path["category"]["verified_at"] is not None

    selection, card_text = _employer_texts(employer, candidate_id)
    for text in (selection, card_text):
        assert not any(word in text for word in FORBIDDEN), text
    assert json.loads(card_text)["category"]["verified_at"] is not None
    topics = json.loads(selection)["entries"][0]["topics"]
    assert any(t["verification_confirmed"] for t in topics)


def test_block_mismatch_shows_reason_and_retest_date(
    signed_in: Callable[[Role], TestClient], seeds: Seeds, mechanics: Mechanics
) -> None:
    candidate = signed_in(Role.candidate)
    take_survey(candidate)
    candidate.post(
        f"{PATH}/attempts", json={"grade": "middle", "focus_consent": True}
    ).raise_for_status()
    _answer(
        candidate,
        seeds,
        correct=True,
        focus_losses=mechanics.focus_events_for_verification,
        more=_in_test,
    )
    candidate.post(f"{PATH}/verification").raise_for_status()
    path = _answer(candidate, seeds, correct=False, focus_losses=0, more=_in_block)
    assert path["stage"] == "verification" and path["category"] is None
    last = path["verification"]["last"]
    assert last == {
        "confirmed": False,
        "expected": last["expected"],
        "correct": 0,
        "items": mechanics.verification_items,
        "at": last["at"],
    }
    assert last["expected"] > 3
    assert path["verification"]["available_at"] is not None
    early = candidate.post(f"{PATH}/verification")
    assert early.status_code == 409 and early.json()["code"] == "verification_too_early"
    assert early.json()["available_at"] == path["verification"]["available_at"]


def test_without_consent_events_are_ignored(
    signed_in: Callable[[Role], TestClient], seeds: Seeds
) -> None:
    candidate = signed_in(Role.candidate)
    take_survey(candidate)
    candidate.post(f"{PATH}/attempts", json={"grade": "middle"}).raise_for_status()
    path = _answer(candidate, seeds, correct=True, focus_losses=50, more=_in_test)
    assert path["stage"] == "category"
    assert path["category"]["verified_at"] is None
