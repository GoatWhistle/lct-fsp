"""Подбор проверки согласия семейства с моделью на настроечном наборе D3 (план валидации, D3,
правило для `item_fit_*`; mechanics.md, §7).

Банк специализации с испорченными семействами в скрытой истине прогревается на честных кандидатах
набора, как в M21. Выводов из выдачи во время прогрева нет — ни по согласию, ни по расхождению с
экспертом: каждое семейство набирает ответы до конца, и гипотезы сравниваются на одних и тех же
ответах. У каждого неякорного семейства берутся первые `size` ответов с итоговой оценкой — те, на
которых сервис переоценивает семейство, — уровни переводятся связкой шкалы на конец прогрева,
переоценка — прод. Каждая гипотеза отмечает семейства при каждом пороге своей сетки; порог и
гипотеза выбираются по правилу плана.
"""

import math
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from itertools import product

from app.adapter.code_runner import InProcessCodeRunner
from app.domain.calibration import (
    Parameters,
    Response,
    ceiling_gain,
    ceilings,
    expected_correct,
    item_fit_rmsd,
    refit,
)
from settings import Mechanics
from validation.main import catalog
from validation.market import TUNING_SEED, Market, corrupted_families, mean_responses
from validation.population import D1, Generator, GeneratorParams
from validation.simulate import warm_source
from validation.truth import Corruption

# D3 для M21: модель ответа D1 с угадыванием и промахом, сид настроечного набора, честные кандидаты.
D3 = replace(D1, name="d3", seed=TUNING_SEED)
# Испорченных при подборе больше, чем в M21 (5 %): иначе на вид порчи пришлось бы по пять-шесть
# семейств, и TPR шагал бы по 0,17.
TUNING_CORRUPTED_SHARE = 0.2
# Ответов на семейство: на первом размере сервис переоценивает семейство и проверяет согласие,
# по нему выбирается порог; второй — как меняется проверка с числом ответов.
SIZES = (200, 500)
# Прогрев — до стольких ответов на семейство в среднем: так второй размер набирает большинство.
TUNING_WARM = 650
# Допустимая доля ложных срабатываний в каждой группе исправных — порог FPR M21.
FPR_MAX = 0.05


@dataclass(frozen=True)
class FitSample:
    """Неякорное семейство после прогрева: истина и ответы с итоговыми оценками по порядку
    показа, уровни переведены связкой шкалы."""

    code: str
    choice: bool
    corruption: Corruption | None
    start: Parameters
    responses: tuple[Response, ...]


def collect(job: tuple[GeneratorParams, str, Mechanics, int, float]) -> list[FitSample]:
    """Прогрев банка специализации с испорченными семействами — задача пула процессов."""
    params, code, mechanics, warm, share = job
    quiet = mechanics.model_copy(
        update={
            "item_fit_rmsd_max": math.inf,
            "item_fit_discrimination_min": 0.0,
            "item_fit_ceiling_gain_max": math.inf,
            "calibration_expert_gap_review": math.inf,
        }
    )
    m = Market(code, quiet, params.seed, params.response)
    generator = Generator(params, quiet, catalog())
    m.corrupted = corrupted_families(m.families, share, generator.rng(f"corrupt:{code}"))
    source = warm_source(params, code, quiet)
    while mean_responses(m) < warm:
        m.attempt(source())
    runner = InProcessCodeRunner()
    with m.stand.uow:
        link = m.stand.calibration.links(code)[1]
        return [
            FitSample(
                f.code,
                bool(f.instance(0, runner).options),
                m.corrupted.get(f.code),
                m.expert(f.grade),
                tuple(
                    Response(link.apply(r.level), r.correct)
                    for r in m.stand.calibration.rest_answers(f.code)
                ),
            )
            for f in m.families
            if not f.anchor
        ]


# --- Статистики ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Statistics:
    """Что меряют гипотезы на ответах одного семейства."""

    # Действующая проверка: RMSD против переоценённых (a, b), за вычетом шума.
    rmsd: float
    # Г1: RMSD против экспертной формы — a = a₀, b переоценена при этой a.
    rmsd_expert: float
    # Г2: переоценённая разделяющая сила.
    discrimination: float
    # Г3: недобор доли верных в верхней группе против экспертной формы.
    upper_shortfall: float
    # Г4: перевес апостериорной плотности модели с потолком над 2PL, в натах.
    ceiling_gain: float


def measure(responses: Sequence[Response], start: Parameters, mechanics: Mechanics) -> Statistics:
    sd_b = mechanics.calibration_refit_difficulty_prior_sd
    sd_log_a = mechanics.calibration_refit_log_discrimination_prior_sd
    fitted = refit(responses, start, difficulty_prior_sd=sd_b, log_discrimination_prior_sd=sd_log_a)
    # a закреплена на экспертной: штраф на ln a так узок, что шаг по ln a нулевой.
    expert_shape = refit(
        responses, start, difficulty_prior_sd=sd_b, log_discrimination_prior_sd=1e-9
    )
    groups = mechanics.item_fit_groups
    return Statistics(
        rmsd=item_fit_rmsd(responses, fitted, groups=groups),
        rmsd_expert=item_fit_rmsd(responses, expert_shape, groups=groups),
        discrimination=fitted.discrimination,
        upper_shortfall=upper_shortfall(responses, expert_shape),
        ceiling_gain=ceiling_gain(
            responses,
            start,
            fitted,
            ceilings=ceilings(mechanics.item_fit_ceiling_min, mechanics.item_fit_ceiling_step),
            difficulty_prior_sd=sd_b,
            log_discrimination_prior_sd=sd_log_a,
        ),
    )


def upper_shortfall(responses: Sequence[Response], params: Parameters) -> float:
    """Ожидаемая минус наблюдённая доля верных у ответов, где модель `params` ждёт верного с
    вероятностью не ниже ½; без таких ответов — 0."""
    expected = [(expected_correct(params, r.level), r.correct) for r in responses]
    upper = [(p, u) for p, u in expected if p >= 0.5]
    if not upper:
        return 0.0
    return sum(p for p, _ in upper) / len(upper) - sum(u for _, u in upper) / len(upper)


# --- Гипотезы и правило выбора -------------------------------------------------------------------


def _grid(first: float, last: float, step: float) -> tuple[float, ...]:
    return tuple(round(first + step * i, 4) for i in range(round((last - first) / step) + 1))


@dataclass(frozen=True)
class Hypothesis:
    key: str
    name: str
    # Сетка каждого свободного числа; порог — точка их произведения.
    grids: tuple[tuple[float, ...], ...]
    flags: Callable[[Statistics, tuple[float, ...]], bool]

    def thresholds(self) -> list[tuple[float, ...]]:
        return list(product(*self.grids))


DISCRIMINATION_GRID = _grid(0.40, 1.10, 0.05)
CEILING_GAIN_GRID = _grid(0.25, 6.0, 0.25)
# Действующая проверка — для сравнения, не кандидат.
CURRENT = Hypothesis(
    "Г0",
    "действующая: RMSD против переоценённых (a, b)",
    ((0.12,),),
    lambda s, t: s.rmsd > t[0],
)
HYPOTHESES = (
    Hypothesis(
        "Г1",
        "RMSD против экспертной формы",
        (_grid(0.05, 0.25, 0.01),),
        lambda s, t: s.rmsd_expert > t[0],
    ),
    Hypothesis(
        "Г2",
        "нижняя граница â",
        (DISCRIMINATION_GRID,),
        lambda s, t: s.discrimination < t[0],
    ),
    Hypothesis(
        "Г3",
        "недобор верхней группы",
        (_grid(0.03, 0.30, 0.01),),
        lambda s, t: s.upper_shortfall > t[0],
    ),
    Hypothesis(
        "Г4",
        "модель с потолком против 2PL",
        (CEILING_GAIN_GRID,),
        lambda s, t: s.ceiling_gain > t[0],
    ),
    Hypothesis(
        "Г5",
        "Г2 или Г4",
        (DISCRIMINATION_GRID, CEILING_GAIN_GRID),
        lambda s, t: s.discrimination < t[0] or s.ceiling_gain > t[1],
    ),
)


@dataclass(frozen=True)
class Measured:
    """Семейство при одном размере выборки: истина и статистики."""

    code: str
    choice: bool
    corruption: Corruption | None
    statistics: Statistics


Count = tuple[int, int]


def share(count: Count) -> float:
    hits, total = count
    return hits / total if total else math.nan


@dataclass(frozen=True)
class Rates:
    tpr: dict[Corruption, Count]
    fpr_choice: Count
    fpr_value: Count

    @property
    def min_tpr(self) -> float:
        """По видам порчи, где есть семейства; без испорченных — 0: ловить нечего, и выбирать по
        такому прогону нельзя."""
        return min((share(x) for x in self.tpr.values() if x[1]), default=0.0)

    @property
    def max_fpr(self) -> float:
        return max((share(x) for x in (self.fpr_choice, self.fpr_value) if x[1]), default=0.0)

    def admissible(self) -> bool:
        return all(share(x) <= FPR_MAX for x in (self.fpr_choice, self.fpr_value) if x[1])


def rates(
    measured: Sequence[Measured], hypothesis: Hypothesis, threshold: tuple[float, ...]
) -> Rates:
    def count(items: Sequence[Measured]) -> Count:
        return sum(hypothesis.flags(m.statistics, threshold) for m in items), len(items)

    good = [m for m in measured if m.corruption is None]
    return Rates(
        {k: count([m for m in measured if m.corruption == k]) for k in Corruption},
        count([m for m in good if m.choice]),
        count([m for m in good if not m.choice]),
    )


Choice = tuple[tuple[float, ...], Rates]


def choose_threshold(measured: Sequence[Measured], hypothesis: Hypothesis) -> Choice | None:
    """Порог гипотезы по правилу плана: FPR не выше `FPR_MAX` в каждой группе исправных; среди
    таких — наибольший минимальный TPR по видам порчи, при равенстве — меньший наибольший FPR,
    затем порог, отмечающий меньше всего семейств, затем первый в сетке."""
    found = []
    for i, threshold in enumerate(hypothesis.thresholds()):
        r = rates(measured, hypothesis, threshold)
        if not r.admissible():
            continue
        flagged = sum(hypothesis.flags(m.statistics, threshold) for m in measured)
        found.append(((-r.min_tpr, r.max_fpr, flagged, i), threshold, r))
    if not found:
        return None
    _, threshold, r = min(found, key=lambda x: x[0])
    return threshold, r


def choose_hypothesis(chosen: Mapping[str, Choice | None]) -> str | None:
    """Гипотеза по правилу плана: наибольший минимальный TPR; кто отстал от лучшей не больше чем
    на 0,02 — меньше свободных чисел, затем меньший наибольший FPR, затем раньше по списку."""
    grids = {h.key: len(h.grids) for h in HYPOTHESES}
    scored = [(i, key, x[1]) for i, (key, x) in enumerate(chosen.items()) if x is not None]
    if not scored:
        return None
    best = max(r.min_tpr for _, _, r in scored)
    close = [x for x in scored if x[2].min_tpr >= best - 0.02]
    return min(close, key=lambda x: (grids[x[1]], x[2].max_fpr, x[0]))[1]


# --- Прогон --------------------------------------------------------------------------------------


def measure_all(samples: Sequence[FitSample], size: int, mechanics: Mechanics) -> list[Measured]:
    """Семейства, набравшие `size` ответов, — на первых `size`."""
    return [
        Measured(s.code, s.choice, s.corruption, measure(s.responses[:size], s.start, mechanics))
        for s in samples
        if len(s.responses) >= size
    ]


def _measure_job(job: tuple[list[FitSample], int, Mechanics]) -> list[Measured]:
    return measure_all(*job)


def tune(mechanics: Mechanics, params: GeneratorParams = D3, warm: int = TUNING_WARM) -> str | None:
    """Правило подбора на наборе `params`: таблицы Markdown в stdout, ключ выбранной гипотезы."""
    codes = list(catalog().specializations)
    jobs = [(params, code, mechanics, warm, TUNING_CORRUPTED_SHARE) for code in codes]
    with ProcessPoolExecutor(max(1, min(len(codes), (os.cpu_count() or 2) - 1))) as pool:
        by_code = list(pool.map(collect, jobs))
        measured = {
            size: [
                m
                for found in pool.map(
                    _measure_job, [(samples, size, mechanics) for samples in by_code]
                )
                for m in found
            ]
            for size in SIZES
        }
    print(
        f"## Подбор проверки согласия: набор {params.name}, сид {params.seed}, честные "
        f"кандидаты\n\nИспорчено {TUNING_CORRUPTED_SHARE:.0%} неякорных семейств, поровну двух "
        f"видов; прогрев до {warm} ответов на семейство в среднем без выводов из выдачи. Порог "
        f"выбирается на {SIZES[0]} ответах, на {SIZES[1]} — тот же порог.\n"
    )
    for size in SIZES:
        group = measured[size]
        bad = {k: sum(m.corruption == k for m in group) for k in Corruption}
        choice = sum(m.corruption is None and m.choice for m in group)
        value = sum(m.corruption is None and not m.choice for m in group)
        print(
            f"- {size} ответов набрали: ошибка эталона — {bad[Corruption.key]}, ответ не зависит "
            f"от уровня — {bad[Corruption.flat]}, исправные с выбором из вариантов — {choice}, "
            f"с вычисляемым ответом — {value}."
        )
    chosen = {h.key: choose_threshold(measured[SIZES[0]], h) for h in HYPOTHESES}
    print(
        "\n| Гипотеза | Порог | Ответов | TPR, ошибка эталона | TPR, не зависит от уровня | "
        "FPR, выбор из вариантов | FPR, вычисляемый ответ |"
    )
    print("|---|---|---|---|---|---|---|")
    rows: list[tuple[Hypothesis, tuple[float, ...] | None]] = [(CURRENT, (0.12,))]
    rows += [(h, None if chosen[h.key] is None else chosen[h.key][0]) for h in HYPOTHESES]  # type: ignore[index]
    for h, threshold in rows:
        if threshold is None:
            print(f"| {h.key} {h.name} | нет порога с FPR ≤ {FPR_MAX} | | | | | |")
            continue
        cell = " / ".join(f"{t:g}" for t in threshold)
        for size in SIZES:
            r = rates(measured[size], h, threshold)
            print(
                f"| {h.key} {h.name} | {cell} | {size} | {_cell(r.tpr[Corruption.key])} | "
                f"{_cell(r.tpr[Corruption.flat])} | {_cell(r.fpr_choice)} | "
                f"{_cell(r.fpr_value)} |"
            )
    winner = choose_hypothesis(chosen)
    if winner is None:
        print("\nНи у одной гипотезы нет порога с допустимым FPR.")
        return None
    found = chosen[winner]
    assert found is not None
    print(
        f"\nВыбрана {winner}, порог {' / '.join(f'{t:g}' for t in found[0])}: минимальный TPR "
        f"{found[1].min_tpr:.2f}, наибольший FPR {found[1].max_fpr:.3f}."
    )
    return winner


def _cell(count: Count) -> str:
    hits, total = count
    return f"{hits / total:.2f} ({hits} из {total})" if total else "—"
