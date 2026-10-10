"""Согласие попытки с моделью, l_z (mechanics.md, §8): чистая функция, правило подозрительного
результата и сценарий пути."""

import json
import random

from app.domain.attempt import AttemptOutcome
from app.domain.protection import (
    AttemptSignals,
    SuspicionReason,
    SuspicionRule,
    person_fit,
    suspicion,
)
from app.domain.skill import sigmoid
from tests.test_protection_scenarios import MECHANICS, Bench


def model_answers(rng: random.Random, n: int = 200) -> list[tuple[float, float, float, bool]]:
    items = []
    for _ in range(n):
        a, b, level = rng.uniform(0.8, 2.0), rng.gauss(0, 1.2), rng.gauss(0, 1)
        items.append((a, b, level, rng.random() < sigmoid(a * (level - b))))
    return items


def test_answers_by_the_model_are_near_zero() -> None:
    rng = random.Random(1)
    values = [person_fit(model_answers(rng)) for _ in range(200)]
    assert all(v is not None for v in values)
    mean = sum(v for v in values if v is not None) / len(values)
    assert abs(mean) < 0.3


def test_solved_hard_failed_easy_is_strongly_negative() -> None:
    items = [(1.5, b, 0.0, b > 0) for b in (-2.0, -1.5, -1.0, -0.5, 0.5, 1.0, 1.5, 2.0) * 3]
    value = person_fit(items)
    assert value is not None and value < -4


def test_no_answers_give_no_statistic() -> None:
    assert person_fit([]) is None


def test_low_person_fit_is_a_suspicion_reason() -> None:
    rule = SuspicionRule(time_flags=3, focus_events=5, person_fit=2.0)
    low = AttemptSignals(time_flags=0, focus_events=None, person_fit=-2.5)
    fine = AttemptSignals(time_flags=0, focus_events=None, person_fit=-1.0)
    assert suspicion(low, rule) == (SuspicionReason.misfit,)
    assert suspicion(fine, rule) == ()
    assert suspicion(low, SuspicionRule(time_flags=3, focus_events=5)) == ()


# Порог −4: помечается любая попытка с l_z не выше 4 — проверяется проводка правила, а не порог.
ALWAYS = MECHANICS.model_copy(update={"person_fit_lz": -4.0})


def test_raising_attempt_with_low_person_fit_goes_to_verification() -> None:
    bench = Bench(mechanics=ALWAYS)
    user = bench.enrol()
    bench.paths.start_attempt(user, grade="junior")
    view = bench.answer(user, lambda f: True)
    attempt = bench.path_attempt(user)
    assert attempt.person_fit is not None and attempt.person_fit <= 4
    assert attempt.outcome == AttemptOutcome.verification
    assert view.category is None


def test_attempt_that_does_not_raise_is_not_verified() -> None:
    bench = Bench(mechanics=ALWAYS)
    user = bench.enrol()
    bench.paths.start_attempt(user, grade="senior")
    bench.answer(user, lambda f: False)
    attempt = bench.path_attempt(user)
    assert attempt.person_fit is not None
    assert attempt.outcome in (AttemptOutcome.offered, AttemptOutcome.no_category)


def test_honest_attempt_passes_at_the_configured_threshold() -> None:
    bench = Bench()
    user = bench.enrol()
    bench.paths.start_attempt(user, grade="junior")
    view = bench.answer(user, lambda f: True)
    attempt = bench.path_attempt(user)
    assert attempt.person_fit is not None and attempt.person_fit > -MECHANICS.person_fit_lz
    assert view.category is not None


def test_person_fit_never_reaches_the_api() -> None:
    """l_z — для стенда и разбора: ни одна схема ответа API его не несёт."""
    from main import create_app

    schema = json.dumps(create_app().openapi()).lower()
    assert "person_fit" not in schema
    assert "l_z" not in schema
    assert "misfit" not in schema
