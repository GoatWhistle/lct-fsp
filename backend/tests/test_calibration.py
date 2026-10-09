"""Калибровка семейств — чистые функции (mechanics.md, §7) и сходимость на симуляции с
известными параметрами (план валидации, M12)."""

import math
import random
from collections.abc import Collection
from datetime import UTC, datetime

import pytest

from app.adapter import irt
from app.adapter.irt import estimate, sigmoid
from app.domain import bank
from app.domain.calibration import (
    AnchorAnswer,
    ExpertGap,
    Link,
    Parameters,
    Response,
    ceiling_gain,
    ceilings,
    elo_step,
    elo_update,
    expected_correct,
    expert_gap,
    fit_link,
    item_fit_rmsd,
    refit,
)
from app.domain.skill import Normal, Observation
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.unit_of_work import MemoryStore
from app.usecase.attempt import rest_levels
from app.usecase.skill_profile import specialization_prior
from composition import elo_calibration
from settings import Mechanics, Settings
from validation.market import calibration_quality, expert, market, mean_responses
from validation.truth import Corruption

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


@pytest.mark.parametrize(
    ("difficulty", "flag"),
    [
        (-0.1, ExpertGap.EASIER),
        (0.1, None),
        (1.9, None),
        (2.1, ExpertGap.HARDER),
    ],
)
def test_reference_is_checked_against_expert_both_ways(
    difficulty: float, flag: ExpertGap | None
) -> None:
    start = Parameters(1.2, 1.0)

    gap = MECHANICS.calibration_expert_gap_review

    assert expert_gap(Parameters(1.2, difficulty), start, gap=gap) is flag


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


class AnsweredCalibrationRepository(MemoryCalibrationRepository):
    """Калибровка в памяти с готовыми ответами на семейства: истинная сложность — по коду."""

    def __init__(
        self, truth: dict[str, float], *, answers: dict[str, list[Response]] | None = None
    ) -> None:
        super().__init__(MemoryStore())
        rng = random.Random(7)
        self.answers = {
            code: calibrated_responses(Parameters(1.2, b), 3000, rng) for code, b in truth.items()
        } | (answers or {})

    def rest_answers(self, code: str) -> list[Response]:
        return self.answers.get(code, [])

    def ready_responses(self, code: str) -> int:
        return len(self.answers.get(code, []))


def test_refit_takes_easier_family_out_and_only_flags_harder_one() -> None:
    """Легче экспертной — утечка или ошибка эксперта: из выдачи до проверки. Тяжелее — кандидату
    не подыгрывает: остаётся в выдаче, пометка — в отчёт покрытия."""
    middle = [f for f in bank.BANK if f.grade == "middle" and not f.anchor]
    easy, hard, fair = middle[:3]
    expert_b = MECHANICS.expert_difficulty_by_grade["middle"]
    calibration = elo_calibration(
        AnsweredCalibrationRepository(
            {easy.code: expert_b - 2.5, hard.code: expert_b + 2.5, fair.code: expert_b}
        ),
        MECHANICS,
    )

    calibration.refit_due([easy.code, hard.code, fair.code], "backend", datetime.now(UTC))

    assert set(calibration.current([easy, hard, fair])) == {hard.code, fair.code}
    assert calibration.expert_gaps([easy, hard, fair]) == {
        easy.code: ExpertGap.EASIER,
        hard.code: ExpertGap.HARDER,
    }


def item_fit(responses: list[Response], params: Parameters) -> float:
    return item_fit_rmsd(responses, params, groups=MECHANICS.item_fit_groups)


def flat_responses(center: float, n: int, rng: random.Random, *, sd: float = 0.5) -> list[Response]:
    """Ответ не зависит от уровня: P(верно) = 0,5 при широком разбросе уровней вокруг `center`."""
    return [Response(Normal(rng.gauss(center, 1.5), sd), rng.random() < 0.5) for _ in range(n)]


def test_item_fit_is_small_for_family_answered_by_its_own_2pl() -> None:
    rng = random.Random(11)
    params = Parameters(1.2, 1.0)

    rmsd = item_fit(calibrated_responses(params, 2000, rng), params)

    assert rmsd < MECHANICS.item_fit_rmsd_max / 2


def test_item_fit_exceeds_threshold_when_answer_does_not_depend_on_level() -> None:
    rng = random.Random(12)
    params = Parameters(1.2, 1.0)

    assert item_fit(flat_responses(params.difficulty, 2000, rng), params) > (
        MECHANICS.item_fit_rmsd_max
    )


def test_item_fit_expects_share_closer_to_half_for_uncertain_levels() -> None:
    """Половина верных у кандидатов на два логита выше сложности: при точной оценке уровня модель
    ждёт почти всех верных, при неточной — ближе к половине, и расхождение меньше."""
    params = Parameters(1.2, 0.0)

    def rmsd(sd: float) -> float:
        responses = [Response(Normal(2.0, sd), i % 2 == 0) for i in range(100)]
        return item_fit_rmsd(responses, params, groups=1)

    assert rmsd(3.0) < rmsd(0.2)


def test_item_fit_weights_groups_by_size_and_discounts_sampling_noise() -> None:
    """Пять ответов на две группы по уровню: остаток — в первую, 3 и 2 ответа. RMSD — корень из
    взвешенного числом ответов среднего квадрата расхождения за вычетом дисперсии доли верных,
    которую даёт сама модель: Σ p(1 − p) / nₖ по группе."""
    params = Parameters(1.2, 0.0)
    levels = [Normal(m, 0.4) for m in (2.0, 1.0, 3.0, 1.5, 2.5)]
    responses = [Response(level, False) for level in levels]
    groups = [[levels[1], levels[3], levels[0]], [levels[4], levels[2]]]
    squares = noise = 0.0
    for group in groups:
        expected = [expected_correct(params, x) for x in group]
        squares += len(group) * (sum(expected) / len(group)) ** 2
        noise += sum(p * (1 - p) for p in expected) / len(group)

    rmsd = item_fit_rmsd(responses, params, groups=2)

    assert squares > noise
    assert rmsd == pytest.approx(math.sqrt((squares - noise) / 5))


def test_item_fit_does_not_take_sampling_noise_for_misfit() -> None:
    """Семейство по 2PL на `calibration_refit_min_responses` ответах кандидатов около его
    сложности, как их подбирает адаптивный тест: в группе по 20 ответов доля верных сама гуляет
    на ±0,1, и без поправки на шум RMSD упирается в порог."""
    rng = random.Random(13)
    params = Parameters(1.2, 1.0)
    above = 0
    for _ in range(100):
        responses = []
        for _ in range(MECHANICS.calibration_refit_min_responses):
            level = Normal(rng.gauss(params.difficulty, 0.8), 0.45)
            theta = rng.gauss(level.mean, level.sd)
            correct = rng.random() < sigmoid(params.discrimination * (theta - params.difficulty))
            responses.append(Response(level, correct))
        above += item_fit(responses, params) > MECHANICS.item_fit_rmsd_max

    assert above <= 5


def reversed_responses(params: Parameters, n: int, rng: random.Random) -> list[Response]:
    """Эталон — дистрактор, который выбирают слабые: доля верных падает с уровнем. Такой кривой
    нет у 2PL ни при каких (a, b), a > 0."""
    return [Response(r.level, not r.correct) for r in calibrated_responses(params, n, rng)]


def test_refit_takes_misfitting_family_out_and_keeps_fitting_one() -> None:
    """Кривая ответа не той формы — после переоценки семейство уходит из выдачи, хотя опорная
    сложность не легче экспертной. Семейство по 2PL без дрейфа остаётся."""
    misfit, fair = [f for f in bank.BANK if f.grade == "middle" and not f.anchor][:2]
    expert_b = MECHANICS.expert_difficulty_by_grade["middle"]
    misfit_answers = reversed_responses(
        Parameters(1.2, expert_b), MECHANICS.calibration_refit_min_responses, random.Random(8)
    )
    calibration = elo_calibration(
        AnsweredCalibrationRepository({fair.code: expert_b}, answers={misfit.code: misfit_answers}),
        MECHANICS,
    )

    calibration.refit_due([misfit.code, fair.code], "backend", datetime.now(UTC))

    assert set(calibration.current([misfit, fair])) == {fair.code}
    assert ExpertGap.EASIER not in calibration.expert_gaps([misfit, fair]).values()


def m21_responses(
    truth: Parameters, n: int, rng: random.Random, *, kind: Corruption | None, center: float
) -> list[Response]:
    """Ответы кандидатов с уровнями около `center`, как их подбирает адаптивный тест, по 2PL
    истины `truth` или с порчей M21: ответ не зависит от уровня — P = 0,5; ошибка эталона у
    половины экземпляров — P = ½ · p(θ)."""
    responses = []
    for _ in range(n):
        level = Normal(rng.gauss(center, 0.8), 0.45)
        theta = rng.gauss(level.mean, level.sd)
        p = sigmoid(truth.discrimination * (theta - truth.difficulty))
        if kind == Corruption.flat:
            p = 0.5
        elif kind == Corruption.key:
            p *= rng.random() < 0.5
        responses.append(Response(level, rng.random() < p))
    return responses


def retired_after_refit(
    discrimination: float, kind: Corruption | None, *, center_shift: float = 0.0
) -> tuple[int, int]:
    """Сколько из двадцати семейств грейда middle выводит переоценка на
    `calibration_refit_min_responses` ответах — тем же сценарием, что в сервисе."""
    families = [f for f in bank.BANK if f.grade == "middle" and not f.anchor][:20]
    start = expert("middle", MECHANICS)
    truth = Parameters(discrimination, start.difficulty)
    rng = random.Random(21)
    answers = {
        f.code: m21_responses(
            truth,
            MECHANICS.calibration_refit_min_responses,
            rng,
            kind=kind,
            center=start.difficulty + center_shift,
        )
        for f in families
    }
    calibration = elo_calibration(AnsweredCalibrationRepository({}, answers=answers), MECHANICS)

    calibration.refit_due(answers, "backend", datetime.now(UTC))

    return len(families) - len(calibration.current(families)), len(families)


def test_ceiling_gain_is_small_for_2pl_and_large_for_level_independent_answers() -> None:
    """У 2PL потолок не нужен — перевес около нуля и не меньше нуля: потолок 1 — сама переоценённая
    2PL. Ответ, не зависящий от уровня, модель с потолком объясняет без штрафа на a — перевес
    большой."""
    start = expert("middle", MECHANICS)
    rng = random.Random(22)
    ceilings_grid = ceilings(MECHANICS.item_fit_ceiling_min, MECHANICS.item_fit_ceiling_step)

    def gain(responses: list[Response]) -> float:
        fitted = refit_with_priors(responses, start)
        return ceiling_gain(
            responses,
            start,
            fitted,
            ceilings=ceilings_grid,
            difficulty_prior_sd=MECHANICS.calibration_refit_difficulty_prior_sd,
            log_discrimination_prior_sd=MECHANICS.calibration_refit_log_discrimination_prior_sd,
        )

    fair = gain(m21_responses(start, 500, rng, kind=None, center=start.difficulty))
    flat = gain(m21_responses(start, 500, rng, kind=Corruption.flat, center=start.difficulty))

    assert ceilings_grid[0] == MECHANICS.item_fit_ceiling_min
    assert ceilings_grid[-1] < 1
    assert 0 <= fair < MECHANICS.item_fit_ceiling_gain_max
    assert flat > 3 * MECHANICS.item_fit_ceiling_gain_max


def test_refit_takes_out_level_independent_family() -> None:
    """Ответ не зависит от уровня — переоценка уводит a к нулю, сколько позволяет штраф, и RMSD
    против переоценённых (a, b) мал; проверка согласия всё равно выводит семейство."""
    retired, total = retired_after_refit(MECHANICS.expert_discrimination, Corruption.flat)

    assert retired / total >= 0.8


def test_refit_takes_out_family_with_wrong_key_in_half_of_instances() -> None:
    """Ошибка эталона у половины экземпляров: доля верных не выше ½ при любом уровне. Эло к
    переоценке уже сдвинул сложность вверх, и адаптивный тест подбирает семейству кандидатов
    сильнее истинной b* — у них потолок ½ и виден."""
    retired, total = retired_after_refit(
        MECHANICS.expert_discrimination, Corruption.key, center_shift=1.0
    )

    assert retired / total >= 0.8


def test_refit_keeps_2pl_family_at_upper_edge_of_d1_spread() -> None:
    """ln a* = ln a₀ + 2 · 0,3 — край разброса истинных параметров D1: крутая кривая не похожа ни
    на плоскую, ни на кривую с потолком."""
    retired, _ = retired_after_refit(MECHANICS.expert_discrimination * math.exp(0.6), None)

    assert retired == 0


def test_refit_keeps_most_2pl_families_at_lower_edge_of_d1_spread() -> None:
    """ln a* = ln a₀ − 2 · 0,3: пологую кривую модель с потолком отчасти имитирует, и на 200
    ответах около трети таких семейств выводится (mechanics.md, §7). Край разброса редок — на D3
    ложных срабатываний 0,03 в целом."""
    retired, total = retired_after_refit(MECHANICS.expert_discrimination * math.exp(-0.6), None)

    assert retired / total <= 0.4


class AnchoredCalibrationRepository(MemoryCalibrationRepository):
    """Калибровка в памяти с готовыми ответами на якоря; запоминает, по каким якорям спрашивали."""

    def __init__(self, answers: list[AnchorAnswer]) -> None:
        super().__init__(MemoryStore())
        self.answers = answers
        self.asked: list[set[str]] = []

    def anchor_answers(
        self, specialization: str, anchors: Collection[str], window_attempts: int
    ) -> list[AnchorAnswer]:
        self.asked.append(set(anchors))
        return [a for a in self.answers if a.family_code in anchors]


def anchor_answers_of(
    family: bank.Family, link: Link, n: int, rng: random.Random, *, flat: bool = False
) -> list[AnchorAnswer]:
    """Ответы на якорь при оценках, пережатых связкой; `flat` — ответ не зависит от уровня."""
    params = expert(family.grade, MECHANICS)
    answers = []
    for _ in range(n):
        level = Normal(rng.gauss(params.difficulty, 1.0), rng.uniform(0.4, 0.8))
        true = link.apply(level)
        theta = rng.gauss(true.mean, true.sd)
        p = 0.5 if flat else sigmoid(params.discrimination * (theta - params.difficulty))
        response = Response(level, rng.random() < p)
        answers.append(AnchorAnswer(family.code, params, response, response))
    return answers


def test_relink_takes_misfitting_anchor_out_of_rotation_and_link() -> None:
    """Якорь, на который отвечают независимо от уровня, выводится из выдачи, а связка строится
    без его ответов — и в этом пересчёте, и в следующих."""
    anchors = [f for f in bank.families_for_topics(["qa.api", "qa.theory"]) if f.anchor]
    *good, bad = anchors
    rng = random.Random(9)
    truth = Link(-0.2, 1.25)
    fitting = [a for f in good for a in anchor_answers_of(f, truth, 800, rng)]
    repository = AnchoredCalibrationRepository(
        fitting + anchor_answers_of(bad, truth, 800, rng, flat=True)
    )
    calibration = elo_calibration(repository, MECHANICS)
    minimum = MECHANICS.calibration_refit_min_responses
    expected = (
        fit_link([(a.params, a.before) for a in fitting], min_responses=minimum),
        fit_link([(a.params, a.rest) for a in fitting if a.rest], min_responses=minimum),
    )

    calibration.relink("qa", datetime.now(UTC))

    assert set(calibration.current(anchors)) == {f.code for f in good}
    assert repository.links("qa") == expected

    calibration.relink("qa", datetime.now(UTC))

    assert bad.code not in repository.asked[-1]
    assert repository.links("qa") == expected


def test_relink_keeps_anchor_with_too_few_answers_to_judge() -> None:
    anchor = next(f for f in bank.families_for_topics(["qa.api"]) if f.anchor)
    few = MECHANICS.calibration_refit_min_responses - 1
    repository = AnchoredCalibrationRepository(
        anchor_answers_of(anchor, Link(), few, random.Random(10), flat=True)
    )
    calibration = elo_calibration(repository, MECHANICS)

    calibration.relink("qa", datetime.now(UTC))

    assert set(calibration.current([anchor])) == {anchor.code}


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


@pytest.mark.simulation
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


def test_lock_takes_anchors_of_attempt_specialization_too() -> None:
    """Пересчёт связки может вывести якорь из выдачи: его строку остановка берёт заранее, в общем
    порядке кодов, а якоря чужих специализаций не трогает."""
    repository = MemoryCalibrationRepository(MemoryStore())
    calibration = elo_calibration(repository, MECHANICS)
    regular = next(f for f in bank.families_for_topics(["qa.api"]) if not f.anchor)
    qa_anchors = {f.code for f in bank.BANK if f.anchor and f.code.startswith("qa.")}

    calibration.lock([regular.code])

    assert set(repository.parameters([f.code for f in bank.BANK])) == {regular.code} | qa_anchors
