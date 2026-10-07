"""Хранимый формат подборки: снимок потребности и объяснение в JSONB.

Эталоны ниже — то, что писала схема API до выноса снимка и объяснения в домен: сохранённые
тогда подборки открываются без миграции данных. Формат задают кодеки репозитория, поэтому
правка схемы API его не меняет; правка эталона — только вместе с миграцией данных.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.catalog import CatalogRef
from app.domain.importance import TopicImportance
from app.domain.match import Verdict
from app.domain.selection import (
    Explanation,
    NeedRequirement,
    NeedSnapshot,
    StackExplanation,
    TopicExplanation,
)
from app.domain.work import SalaryRange, WorkFormat
from app.repository.selection import (
    explanation_json,
    explanation_of,
    snapshot_json,
    snapshot_of,
)

SNAPSHOT = NeedSnapshot(
    title="QA",
    specialization=CatalogRef("qa", "QA"),
    grade=CatalogRef("middle", "Middle"),
    stack=(CatalogRef("pytest", "pytest"),),
    work_format=WorkFormat.hybrid,
    city="Казань",
    salary=SalaryRange(200_000, 300_000),
    topics=(
        NeedRequirement(CatalogRef("qa.api", "API"), TopicImportance.key, True, 0.75, 0.5),
        NeedRequirement(CatalogRef("qa.theory", "Теория"), TopicImportance.nice, False, 0.25, 0.5),
    ),
    updated_at=datetime(2026, 10, 7, 9, 30, 15, 123456, tzinfo=UTC),
)

TOPICS_JSON = (
    '[{"topic": {"code": "qa.api", "name": "API"}, "importance": "key", "edited": true, '
    '"weight": 0.75, "requirement": 0.5}, {"topic": {"code": "qa.theory", "name": "Теория"}, '
    '"importance": "nice", "edited": false, "weight": 0.25, "requirement": 0.5}]'
)
SNAPSHOT_JSON = (
    '{"title": "QA", "specialization": {"code": "qa", "name": "QA"}, "grade": {"code": '
    '"middle", "name": "Middle"}, "stack": [{"code": "pytest", "name": "pytest"}], '
    '"work_format": "hybrid", "city": "Казань", "salary_from": 200000, "salary_to": 300000, '
    f'"topics": {TOPICS_JSON}, "updated_at": "2026-10-07T09:30:15.123456Z", '
    '"salary_basis": "gross"}'
)
# Без вилки и города, время без долей секунды.
BARE_SNAPSHOT_JSON = (
    '{"title": "QA", "specialization": {"code": "qa", "name": "QA"}, "grade": {"code": '
    '"middle", "name": "Middle"}, "stack": [{"code": "pytest", "name": "pytest"}], '
    '"work_format": "hybrid", "city": null, "salary_from": null, "salary_to": null, '
    f'"topics": {TOPICS_JSON}, "updated_at": "2026-10-07T09:30:00Z", "salary_basis": "gross"}}'
)

EXPLANATION = Explanation(
    topics=(TopicExplanation("qa.api", 1.0, 0.4, 0.9, 0.6, Verdict.confidently_above, False),),
    stack=StackExplanation(("pytest",), 1.0, 0.15),
)
EXPLANATION_JSON = (
    '{"topics": [{"topic": "qa.api", "theta": 1.0, "theta_sd": 0.4, "probability": 0.9, '
    '"contribution": 0.6, "verdict": "confidently_above", "low_data": false}], '
    '"stack": {"matched": ["pytest"], "overlap": 1.0, "contribution": 0.15}}'
)

BARE_SNAPSHOT = NeedSnapshot(
    **{
        **vars(SNAPSHOT),
        "city": None,
        "salary": None,
        "updated_at": datetime(2026, 10, 7, 9, 30, tzinfo=UTC),
    }
)


def dumped(data: dict[str, Any]) -> str:
    # Порядок ключей — как в JSONB его видит человек; сам JSONB порядок не хранит.
    return json.dumps(data, ensure_ascii=False)


@pytest.mark.parametrize(
    ("snapshot", "stored"),
    [(SNAPSHOT, SNAPSHOT_JSON), (BARE_SNAPSHOT, BARE_SNAPSHOT_JSON)],
)
def test_need_snapshot_is_stored_in_the_saved_format(snapshot: NeedSnapshot, stored: str) -> None:
    assert dumped(snapshot_json(snapshot)) == stored
    assert snapshot_of(json.loads(stored)) == snapshot


def test_explanation_is_stored_in_the_saved_format() -> None:
    assert dumped(explanation_json(EXPLANATION)) == EXPLANATION_JSON
    assert explanation_of(json.loads(EXPLANATION_JSON)) == EXPLANATION
