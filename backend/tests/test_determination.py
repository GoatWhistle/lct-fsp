"""Определение категории — чистые функции: правило уверенности и каскад вниз (mechanics.md, §4)."""

import pytest

from app.domain.determination import (
    Assign,
    NoCategory,
    Offer,
    decide,
    grade_probabilities,
    grade_up_hint,
    grades_by_threshold,
)
from app.domain.skill import Normal

THRESHOLDS = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}
GRADES = grades_by_threshold(THRESHOLDS)
CONFIDENCE = 0.8


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
