"""Калибровка семейств — чистые функции (mechanics.md, §7) и сходимость на симуляции с
известными параметрами (план валидации, M12)."""

import math
import random

import pytest

from app.adapter import irt
from app.adapter.irt import estimate, sigmoid
from app.domain.calibration import (
    Link,
    Parameters,
    Response,
    elo_step,
    elo_update,
    fit_link,
    needs_review,
    refit,
)
from app.domain.skill import Normal, Observation
from app.usecase.attempt import rest_levels
from app.usecase.skill_profile import specialization_prior
from settings import Mechanics, Settings
from validation.market import calibration_quality, expert, market, mean_responses

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
# Порог M12 плана валидации на 200 ответах в среднем на семейство.
CALIBRATION_MIN_CORRELATION = 0.95


def step(responses: int) -> float:
    return elo_step(
        responses,
        k_initial=MECHANICS.elo_k_initial,
        k_half_responses=MECHANICS.elo_k_half_responses,
        k_min=MECHANICS.elo_k_min,
    )


def elo(params: Parameters, response: Response, responses: int) -> Parameters:
    return elo_update(
        params,
        response,
        responses,
        k_initial=MECHANICS.elo_k_initial,
        k_half_responses=MECHANICS.elo_k_half_responses,
        k_min=MECHANICS.elo_k_min,
    )


def refit_with_priors(responses: list[Response], start: Parameters) -> Parameters:
    return refit(
        responses,
        start,
        difficulty_prior_sd=MECHANICS.calibration_refit_difficulty_prior_sd,
        log_discrimination_prior_sd=MECHANICS.calibration_refit_log_discrimination_prior_sd,
    )


def test_expert_start_is_middle_of_grade_band() -> None:
    assert expert("middle", MECHANICS) == Parameters(1.2, 1.0)
    assert expert("intern", MECHANICS) == Parameters(1.2, -1.0)


def test_elo_step_halves_over_half_responses_and_has_floor() -> None:
    k0, half = MECHANICS.elo_k_initial, MECHANICS.elo_k_half_responses

    assert step(0) == k0
    assert step(half) == pytest.approx(k0 / 2)
    assert step(10**6) == MECHANICS.elo_k_min


def test_elo_makes_family_easier_after_correct_answer_and_harder_after_wrong() -> None:
    start = Parameters(1.2, 0.0)
    level = Normal(0.0, 0.3)

    easier = elo(start, Response(level, True), 0)
    harder = elo(start, Response(level, False), 0)

    assert easier.difficulty < 0 < harder.difficulty
    assert easier.discrimination == harder.discrimination == 1.2


def test_answer_of_uncertain_candidate_moves_difficulty_less() -> None:
    start = Parameters(1.2, 1.0)

    sure = elo(start, Response(Normal(0.0, 0.2), True), 0)
    unsure = elo(start, Response(Normal(0.0, 1.5), True), 0)

    assert start.difficulty - sure.difficulty > start.difficulty - unsure.difficulty > 0


def test_review_when_reference_is_much_easier_than_expert() -> None:
    start = Parameters(1.2, 1.0)

    gap = MECHANICS.calibration_expert_gap_review

    assert needs_review(Parameters(1.2, -0.1), start, expert_gap=gap)
    assert not needs_review(Parameters(1.2, 0.1), start, expert_gap=gap)
    assert not needs_review(Parameters(1.2, 2.5), start, expert_gap=gap)


def calibrated_responses(
    truth: Parameters, n: int, rng: random.Random, *, sd: float = 0.5
) -> list[Response]:
    """Ответы кандидатов с точной апостериорной оценкой: θ ~ N(μ, σ²)."""
    responses = []
    for _ in range(n):
        level = Normal(rng.gauss(truth.difficulty, 1.0), sd)
        theta = rng.gauss(level.mean, level.sd)
        correct = rng.random() < sigmoid(truth.discrimination * (theta - truth.difficulty))
        responses.append(Response(level, correct))
    return responses


def test_refit_recovers_parameters_from_calibrated_levels() -> None:
    rng = random.Random(1)
    errors_b, errors_log_a = [], []
    for _ in range(30):
        truth = Parameters(1.2 * math.exp(rng.gauss(0, 0.3)), rng.uniform(-1.5, 2.5))
        start = Parameters(1.2, round(truth.difficulty))

        fitted = refit_with_priors(calibrated_responses(truth, 400, rng), start)

        errors_b.append(fitted.difficulty - truth.difficulty)
        errors_log_a.append(math.log(fitted.discrimination / truth.discrimination))

    assert math.sqrt(sum(e * e for e in errors_b) / len(errors_b)) < 0.15
    assert abs(sum(errors_log_a) / len(errors_log_a)) < 0.05


def test_refit_without_responses_keeps_expert_parameters() -> None:
    start = Parameters(1.2, 1.0)

    fitted = refit_with_priors([], start)

    assert fitted.difficulty == pytest.approx(1.0)
    assert fitted.discrimination == pytest.approx(1.2)


def test_rest_level_leaves_out_its_own_answer() -> None:
    prior = specialization_prior(["t.one", "t.two"], MECHANICS)
    observations = [
        Observation("t.one", True, 1.2, 0.0),
        Observation("t.one", False, 1.2, 1.0),
        Observation("t.two", True, 1.2, 0.5),
    ]

    levels = rest_levels(irt, prior, observations, [0, 2])

    assert levels[0] == estimate(prior, observations[1:]).topic("t.one")
    assert levels[1] == estimate(prior, observations[:2]).topic("t.two")


def test_link_maps_level_mean_and_variance_by_scale() -> None:
    link = Link(shift=0.1, scale=1.21)

    linked = link.apply(Normal(1.0, 0.5))
    assert linked.mean == pytest.approx(1.31)
    assert linked.sd == pytest.approx(0.55)
    assert Link().apply(Normal(1.0, 0.5)) == Normal(1.0, 0.5)


def anchor_answers(link: Link, n: int, rng: random.Random) -> list[tuple[Parameters, Response]]:
    """Ответы на якоря при оценках, пережатых связкой: θ | μ ~ N(α + β μ, β σ²)."""
    answers = []
    for _ in range(n):
        params = Parameters(1.2, rng.choice([0.0, 1.0]))
        level = Normal(rng.gauss(0.3, 0.8), rng.uniform(0.4, 0.8))
        true = link.apply(level)
        theta = rng.gauss(true.mean, true.sd)
        correct = rng.random() < sigmoid(params.discrimination * (theta - params.difficulty))
        answers.append((params, Response(level, correct)))
    return answers


def test_link_recovers_shift_and_scale_from_anchor_answers() -> None:
    rng = random.Random(3)
    truth = Link(shift=-0.2, scale=1.25)

    fitted = fit_link(
        anchor_answers(truth, 6000, rng),
        min_responses=MECHANICS.calibration_refit_min_responses,
    )

    assert fitted.shift == pytest.approx(truth.shift, abs=0.06)
    assert fitted.scale == pytest.approx(truth.scale, abs=0.08)


def test_link_is_identity_until_enough_anchor_answers() -> None:
    rng = random.Random(4)
    few = anchor_answers(Link(0.5, 1.5), MECHANICS.calibration_refit_min_responses - 1, rng)

    assert fit_link(few, min_responses=MECHANICS.calibration_refit_min_responses) == Link()


def test_link_is_identity_when_anchor_answers_contradict_levels() -> None:
    """Слабые решают трудный якорь, сильный ошибается на среднем: правдоподобие растёт при β < 0,
    где модели нет (погрешность √β σ). Скоринг уходит туда за несколько шагов — связке не на чем
    стоять."""
    anchors = [
        (Parameters(1.2, 1.5), Response(Normal(-0.1, 1.0), True)),
        (Parameters(1.2, -0.5), Response(Normal(-0.5, 1.0), True)),
        (Parameters(1.2, 0.5), Response(Normal(1.0, 0.6), False)),
    ]

    assert fit_link(anchors, min_responses=1) == Link()


def test_calibration_converges_on_simulated_candidates() -> None:
    """Истинные параметры отличаются от экспертных, уровни кандидатов шире априорного (D1). После
    в среднем `calibration_refit_min_responses` ответов на семейство сложности коррелируют с
    истинными не ниже порога M12 и ближе к ним, чем экспертные. Разделяющая сила не завышена:
    связка шкалы по якорям не даёт калибровке принять пережатые оценки уровня за точные."""
    m = market("qa", MECHANICS)

    while mean_responses(m) < MECHANICS.calibration_refit_min_responses:
        m.attempt(m.candidate())

    r, error, expert_error = calibration_quality(m)
    assert r >= CALIBRATION_MIN_CORRELATION
    assert error < expert_error
    refitted = [f for f in m.calibrated().values() if f.refitted_at is not None]
    assert refitted
    bias = sum(math.log(f.discrimination / m.truth[f.family_code].discrimination) for f in refitted)
    assert bias / len(refitted) < 0.15
