"""Определение категории — чистые функции: бланк попытки и каскад вниз (mechanics.md, §4)."""

import pytest

from app.assessment.bank import BANK, families_for_topics, get_family
from app.assessment.blueprint import fixed_blueprint
from app.assessment.catalog import load_catalog
from app.assessment.determination import (
    Assign,
    NoCategory,
    Offer,
    decide,
    grade_probabilities,
    grade_up_hint,
    grades_by_threshold,
)
from app.skills.irt import Normal

THRESHOLDS = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}
GRADES = grades_by_threshold(THRESHOLDS)
CONFIDENCE = 0.8
QA_TOPICS = [t.code for s in load_catalog().specializations if s.code == "qa" for t in s.topics]


def blueprint(grade: str, seen: set[str] | None = None) -> list[str]:
    return fixed_blueprint(
        topics=QA_TOPICS,
        families=families_for_topics(QA_TOPICS),
        grades=GRADES,
        grade=grade,
        seen=seen or set(),
        per_topic=2,
    )


def grades_of(codes: list[str]) -> list[str]:
    return [get_family(code).grade for code in codes]


def test_blueprint_asks_grade_and_grade_below_in_every_topic() -> None:
    codes = blueprint("middle")

    assert len(codes) == 2 * len(QA_TOPICS)
    assert sorted({get_family(c).topic for c in codes}) == sorted(QA_TOPICS)
    # Сначала задания грейда ниже, по темам в порядке справочника.
    assert grades_of(codes) == ["junior"] * len(QA_TOPICS) + ["middle"] * len(QA_TOPICS)
    assert [get_family(c).topic for c in codes[: len(QA_TOPICS)]] == QA_TOPICS


def test_intern_blueprint_has_only_intern_families() -> None:
    assert grades_of(blueprint("intern")) == ["intern"] * len(QA_TOPICS)


def test_cascade_blueprint_adds_only_unseen_families() -> None:
    seen = set(blueprint("middle"))

    assert grades_of(blueprint("junior", seen)) == ["intern"] * len(QA_TOPICS)
    seen |= set(blueprint("junior", seen))
    assert blueprint("intern", seen) == []


def test_blueprint_respects_per_topic_limit() -> None:
    codes = fixed_blueprint(
        topics=QA_TOPICS,
        families=families_for_topics(QA_TOPICS),
        grades=GRADES,
        grade="senior",
        seen=set(),
        per_topic=1,
    )

    assert grades_of(codes) == ["senior"] * len(QA_TOPICS)


def always(_: str) -> bool:
    return True


def test_confident_grade_is_assigned() -> None:
    # P(θ̄ ≥ 0.5) = Φ(0.5 / 0.4) ≈ 0.89
    result = decide(
        Normal(1.0, 0.4), "middle", thresholds=THRESHOLDS, confidence=CONFIDENCE, has_items=always
    )

    assert result == Assign("middle")


def test_failed_grade_offers_dotest_one_grade_below() -> None:
    result = decide(
        Normal(0.0, 0.6), "middle", thresholds=THRESHOLDS, confidence=CONFIDENCE, has_items=always
    )

    assert result == Offer("junior")


def test_grade_below_is_assigned_without_dotest_when_already_confident() -> None:
    # P(θ̄ ≥ 0.5) ≈ 0.4, P(θ̄ ≥ −0.5) ≈ 0.99
    result = decide(
        Normal(0.4, 0.4), "middle", thresholds=THRESHOLDS, confidence=CONFIDENCE, has_items=always
    )

    assert result == Assign("junior")


def test_failed_intern_leaves_no_category() -> None:
    result = decide(
        Normal(-2.0, 0.5), "intern", thresholds=THRESHOLDS, confidence=CONFIDENCE, has_items=always
    )

    assert result == NoCategory()


def test_dotest_with_nothing_to_ask_fails_at_once_and_cascade_goes_on() -> None:
    result = decide(
        Normal(-1.0, 0.6),
        "junior",
        thresholds=THRESHOLDS,
        confidence=CONFIDENCE,
        has_items=lambda grade: grade != "intern",
    )

    assert result == NoCategory()


def test_grade_probabilities_decrease_with_grade() -> None:
    probabilities = grade_probabilities(Normal(0.3, 0.5), THRESHOLDS)

    assert list(probabilities) == GRADES
    values = list(probabilities.values())
    assert values == sorted(values, reverse=True)
    assert probabilities["middle"] == pytest.approx(0.3445783)


def test_grade_up_hint_needs_hint_confidence_for_next_grade() -> None:
    def hint(mean: float, grade: str) -> str | None:
        return grade_up_hint(Normal(mean, 0.4), grade, thresholds=THRESHOLDS, confidence=0.5)

    assert hint(1.6, "middle") == "senior"
    assert hint(1.4, "middle") is None
    assert hint(3.0, "senior") is None


def test_bank_has_families_for_every_grade_of_its_topics() -> None:
    topics = {f.topic for f in BANK}
    for topic in topics:
        assert sorted(grades_of([f.code for f in BANK if f.topic == topic])) == sorted(GRADES)
