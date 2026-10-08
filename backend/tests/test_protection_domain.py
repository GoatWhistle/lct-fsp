"""Защита теста — чистые функции (mechanics.md, §8): детектор дрейфа, модель времени ответа,
правило подозрительного результата, сравнение проверочного блока и выбор его заданий."""

import math
import random
from datetime import UTC, datetime

import pytest

from app.adapter import irt
from app.domain.adaptive import Option
from app.domain.calibration import Parameters
from app.domain.protection import (
    AttemptSignals,
    ResponseTimes,
    SuspicionReason,
    SuspicionRule,
    cusum_step,
    suspicion,
    time_flag,
    verification_choice,
    verification_expectation,
    verification_verdict,
)
from app.domain.skill import Observation, Prior, sigmoid

REFERENCE = Parameters(1.2, 0.5)


def test_cusum_grows_on_surprising_correct_answers_and_never_goes_below_zero() -> None:
    s = cusum_step(0.0, REFERENCE, -1.0, True, shift=1.0)
    assert s > 0
    p0 = sigmoid(1.2 * (-1.0 - 0.5))
    p1 = sigmoid(1.2 * (-1.0 - 0.5 + 1.0))
    assert s == pytest.approx(math.log(p1 / p0))
    assert cusum_step(0.0, REFERENCE, -1.0, False, shift=1.0) == 0.0
    assert cusum_step(0.3, REFERENCE, -1.0, False, shift=1.0) == pytest.approx(
        max(0.0, 0.3 + math.log((1 - p1) / (1 - p0)))
    )


def test_cusum_is_risk_adjusted_a_strong_candidate_raises_less_alarm() -> None:
    weak = cusum_step(0.0, REFERENCE, -1.0, True, shift=1.0)
    strong = cusum_step(0.0, REFERENCE, 2.0, True, shift=1.0)
    assert strong < weak


def test_cusum_on_honest_answers_stays_low_and_on_leaked_rises() -> None:
    rng = random.Random(3)
    honest = leaked = 0.0
    peak = 0.0
    for _ in range(1000):
        level = rng.gauss(0, 1)
        p = sigmoid(1.2 * (level - 0.5))
        honest = cusum_step(honest, REFERENCE, level, rng.random() < p, shift=1.0)
        peak = max(peak, honest)
        leaked = cusum_step(leaked, REFERENCE, level, rng.random() < p + 0.5 * (1 - p), shift=1.0)
    assert peak < 8
    assert leaked > 50


def test_response_times_need_enough_correct_answers() -> None:
    assert ResponseTimes.fit([60.0] * 29, min_responses=30) is None
    model = ResponseTimes.fit([60.0] * 30, min_responses=30)
    assert model is not None


def test_response_times_are_robust_median_and_mad_of_log_time() -> None:
    seconds = [math.exp(v) for v in (3.0, 3.5, 4.0, 4.5, 5.0, 40.0)]
    model = ResponseTimes.fit(seconds, min_responses=3)
    assert model is not None
    # Медиана ln T — 4,25, MAD — 0,5 · 1,4826: выброс не сдвигает ни то, ни другое.
    assert model.center == pytest.approx(4.25)
    assert model.spread == pytest.approx(0.75 * 1.4826)
    assert model.z(math.exp(4.25)) == pytest.approx(0.0)


def test_response_times_with_identical_times_still_have_a_spread() -> None:
    model = ResponseTimes.fit([30.0] * 40, min_responses=30)
    assert model is not None
    assert model.spread > 0


def _model() -> ResponseTimes:
    model = ResponseTimes.fit([math.exp(4 + 0.1 * (i % 11 - 5)) for i in range(50)], 30)
    assert model is not None
    return model


def test_time_flag_only_on_correct_hard_and_anomalously_fast_answer() -> None:
    model = _model()
    fast = math.exp(model.center - 3 * model.spread)
    usual = math.exp(model.center)
    rule = {"hard_p": 0.5, "fast_z": 2.33}
    assert time_flag(0.3, True, fast, model, **rule)
    assert not time_flag(0.3, False, fast, model, **rule)
    assert not time_flag(0.8, True, fast, model, **rule)
    assert not time_flag(0.3, True, usual, model, **rule)
    assert not time_flag(0.3, True, fast, None, **rule)


RULE = SuspicionRule(time_flags=3, focus_events=3)


def test_suspicion_by_time_flags_or_focus_events() -> None:
    assert suspicion(AttemptSignals(time_flags=2, focus_events=None), RULE) == ()
    assert suspicion(AttemptSignals(time_flags=3, focus_events=None), RULE) == (
        SuspicionReason.fast_answers,
    )
    assert suspicion(AttemptSignals(time_flags=0, focus_events=3), RULE) == (
        SuspicionReason.focus_events,
    )
    assert suspicion(AttemptSignals(time_flags=5, focus_events=7), RULE) == (
        SuspicionReason.fast_answers,
        SuspicionReason.focus_events,
    )


def test_without_consent_focus_events_are_no_signal() -> None:
    assert suspicion(AttemptSignals(time_flags=0, focus_events=None), RULE) == ()


PRIOR = Prior.equal_weights(("sql", "python"), theta_sd=1.0, deviation_sd=0.6, sd_inflation=1.15)


def _estimate(correct: int, total: int) -> irt.Estimate:
    observations = [
        Observation("sql" if i % 2 else "python", i < correct, 1.2, 0.5) for i in range(total)
    ]
    return irt.estimate(PRIOR, observations)


def test_verification_expectation_is_sum_of_p_plus_main_estimate_uncertainty() -> None:
    estimate = _estimate(14, 20)
    items = [("sql", 1.2, 0.5), ("python", 1.0, 0.0)]
    expectation = verification_expectation(estimate, items, unshown=0, target_p=0.65)
    p = [
        sigmoid(1.2 * (estimate.topic("sql").mean - 0.5)),
        sigmoid(1.0 * (estimate.topic("python").mean - 0.0)),
    ]
    assert expectation.expected == pytest.approx(sum(p))
    binomial = sum(q * (1 - q) for q in p)
    assert expectation.variance > binomial
    # Чем точнее основная оценка, тем меньше вклад её погрешности.
    sharper = verification_expectation(_estimate(28, 40), items, unshown=0, target_p=0.65)
    assert (
        sharper.variance
        - sum(
            q * (1 - q)
            for q in (
                sigmoid(1.2 * (_estimate(28, 40).topic("sql").mean - 0.5)),
                sigmoid(1.0 * _estimate(28, 40).topic("python").mean),
            )
        )
        < expectation.variance - binomial
    )


def test_unshown_items_count_at_target_probability() -> None:
    estimate = _estimate(10, 20)
    expectation = verification_expectation(estimate, [], unshown=4, target_p=0.65)
    assert expectation.expected == pytest.approx(4 * 0.65)
    assert expectation.variance == pytest.approx(4 * 0.65 * 0.35)
    assert expectation.items == 4


def test_verdict_confirms_unless_correct_count_is_far_below_expected() -> None:
    estimate = _estimate(14, 20)
    items = [("sql", 1.2, estimate.topic("sql").mean - 0.5)] * 10
    expectation = verification_expectation(estimate, items, unshown=0, target_p=0.65)
    assert verification_verdict(7, expectation, mismatch_z=1.64).confirmed
    low = verification_verdict(2, expectation, mismatch_z=1.64)
    assert not low.confirmed
    assert low.z < -1.64
    assert low.correct == 2
    assert low.items == 10


def _option(code: str, topic: str, difficulty: float, seen: datetime | None = None) -> Option:
    return Option(code, topic, 1.0, difficulty, shown=0, seen_at=seen)


LEVELS = {"sql": 1.0, "python": 0.0}


def test_verification_choice_prefers_unseen_and_target_probability() -> None:
    target_b = {t: level - math.log(0.65 / 0.35) for t, level in LEVELS.items()}
    options = [
        _option("sql-far", "sql", 3.0),
        _option("sql-near", "sql", target_b["sql"] + 0.1),
        _option("sql-seen", "sql", target_b["sql"], seen=datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    choice = verification_choice(
        options, LEVELS, {}, topics=("sql",), target_p=0.65, top_k=1, rng=random.Random(0)
    )
    assert choice == "sql-near"


def test_verification_choice_spreads_items_over_topics_with_unseen_families() -> None:
    options = [_option("sql-a", "sql", 0.0), _option("py-a", "python", 0.0)]
    picked = verification_choice(
        options,
        LEVELS,
        {"sql": 1},
        topics=("sql", "python"),
        target_p=0.65,
        top_k=1,
        rng=random.Random(0),
    )
    assert picked == "py-a"


def test_verification_choice_falls_back_to_oldest_seen() -> None:
    old, recent = datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
    options = [_option("sql-recent", "sql", 0.0, recent), _option("sql-old", "sql", 0.0, old)]
    choice = verification_choice(
        options, LEVELS, {}, topics=("sql",), target_p=0.65, top_k=1, rng=random.Random(0)
    )
    assert choice == "sql-old"
    assert (
        verification_choice(
            [], LEVELS, {}, topics=("sql",), target_p=0.65, top_k=1, rng=random.Random(0)
        )
        is None
    )
