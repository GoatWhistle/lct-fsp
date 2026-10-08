"""Эксперименты защиты на стенде (docs/validation-plan.md, M14–M17) — их части: копия прогретого
банка, правило подбора порога детектора, сводка атаки и повтор ответов модели D7 из записи."""

import json
import math

from app.adapter.code_runner import InProcessCodeRunner
from app.domain.bank import get_family
from app.domain.skill import Normal
from settings import Mechanics, Settings
from validation.llm_attack import COPY_SECONDS, Answering, item_request
from validation.market import market
from validation.protection import (
    DRIFT_GRID,
    Drift,
    Twins,
    flagged_share,
    summarize,
    tune_threshold,
)
from validation.recorded import Answer, request_key
from validation.simulate import Determined

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
RUNNER = InProcessCodeRunner()


def test_fork_is_independent_and_reproducible() -> None:
    """Копия банка не меняет оригинал, две копии с одним seed проходят одинаково."""
    m = market("qa", MECHANICS)
    for _ in range(3):
        m.attempt(m.candidate())
    m.calibrate = False
    before = len(m.stand.store.collection("attempts"))
    one, two = m.fork(5), m.fork(5)
    candidate = m.candidate()
    first = one.attempt(candidate)
    second = two.attempt(candidate)
    assert first.shown == second.shown and first.overall == second.overall
    assert len(m.stand.store.collection("attempts")) == before


def _drift(peaks: list[float]) -> list[Drift]:
    return [Drift(f"f{i}", False, p, 1000) for i, p in enumerate(peaks)]


def test_threshold_is_smallest_grid_value_with_few_false_alarms() -> None:
    drift = _drift([0.5] * 90 + [3.2] * 5 + [7.9] * 5)
    assert flagged_share(drift, 3.0, 1000) == 0.10
    assert tune_threshold(drift, 1000) == 3.5
    assert tune_threshold(_drift([100.0] * 10), 1000) is None


def test_family_without_a_full_window_counts_only_if_it_fired() -> None:
    """Не набравшее окна и не сработавшее семейство в долю не входит."""
    drift = [Drift("a", True, 9.0, 40), Drift("b", True, 1.0, 40), Drift("c", True, 1.0, 300)]
    assert flagged_share(drift, 5.0, 300) == 0.5
    assert DRIFT_GRID[0] == 1.0 and tuple(sorted(DRIFT_GRID)) == DRIFT_GRID


def test_attack_summary_subtracts_repeat_baseline() -> None:
    def d(grade: str | None, theta: float) -> Determined:
        return Determined(grade, Normal(theta, 0.4))

    twins = [
        Twins(d("senior", 1.6), d("middle", 0.6), d("middle", 0.7)),
        Twins(d("middle", 0.8), d("middle", 0.6), d("senior", 1.5)),
    ]
    summary = summarize(twins, MECHANICS)
    assert math.isclose(summary.gain, (1.0 + 0.2) / 2)
    assert summary.raised == 0.5 and summary.baseline == 0.5
    assert summary.excess == 0.0


def test_model_answers_replay_from_recording_without_network() -> None:
    family = get_family("backend.databases.isolation-choice")
    instance = family.instance(1, RUNNER)
    request = item_request(instance)
    assert instance.options
    assert instance.prompt in request.user
    assert all(f"{o.letter}. {o.text}" in request.user for o in instance.options)

    recorded = {request_key(request): Answer(json.dumps({"answer": instance.answer}), None, 4000.0)}
    reply = Answering(recorded)(family.code, instance)
    assert reply.correct and math.isclose(reply.seconds, 4 + COPY_SECONDS)

    other = family.instance(2, RUNNER)
    empty = Answering({})
    assert not empty(family.code, other).correct
    assert empty.missing == 1
