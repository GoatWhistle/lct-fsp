"""Симуляция теста на кандидатах с известной истиной — для проверок адаптивности, калибровки и
честности погрешности.

Истина (уровни кандидатов, параметры семейств) живёт только здесь: движок теста и калибровка
видят ответы и свои оценки, как в сервисе. Истина отличается от модели оценки, как в наборе D1
плана валидации: уровни шире априорного оценщика, b* = b₀ + N(0; 0,5²), ln a* = ln a₀ + N(0; 0,3²)
— калибровке есть что исправлять.

Команды `uv run python -m tests.simulation …`:

- без команды — сравнение адаптивного теста с фиксированным бланком и сходимость калибровки по
  всем специализациям;
- `honesty` — честность погрешности уровня и стабильность грейда при повторе на прогретом банке
  D1;
- `tune` — подбор поправки погрешности `level_sd_inflation` на настроечном наборе D3 по правилу
  плана валидации.
"""

import argparse
import math
import os
import random
import statistics
from collections import deque
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from app.assessment.adaptive import (
    Blueprint,
    Exposure,
    Option,
    choose,
    selection_prior,
    should_stop,
)
from app.assessment.calibration import (
    Link,
    Parameters,
    Response,
    elo_update,
    expert,
    fit_link,
    refit,
    rest_levels,
)
from app.assessment.catalog import load_catalog
from app.assessment.determination import Assign, Offer, decide, grades_by_threshold
from app.config import BACKEND_DIR, Mechanics
from app.domain.bank import Family, families_for_topics
from app.domain.skill import Normal, Observation
from app.skills.irt import estimate, initial, sigmoid, update
from app.usecase.skill_profile import specialization_prior

# Сиды наборов плана валидации: D1 — основной, D3 — настроечный.
SEED = 20261005
TUNING_SEED = 7
# Прогретый банк: ответов на семейство в среднем.
WARM_RESPONSES = 500
# Сетка подбора поправки погрешности κ — шаг 0,05.
INFLATION_GRID = tuple(round(1 + 0.05 * i, 2) for i in range(11))
# Прошлые попытки определения: в симуляции важен только факт показа, не время.
_SEEN = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Candidate:
    level: dict[str, float]
    claimed: str


@dataclass
class Item:
    family: Family
    truth: Parameters
    params: Parameters
    responses: int = 0
    # Ответы с итоговой оценкой кандидата без связки — для пакетной переоценки.
    answers: list[Response] = field(default_factory=list)
    refitted: bool = False


@dataclass(frozen=True)
class Run:
    # Погрешность общего уровня σ̄ после каждого задания.
    sds: list[float]
    shown: list[str]
    # Оценка общего уровня по окончании.
    overall: Normal
    # Семейства, взятые сверх потолка показов: под потолком в теме ничего не осталось.
    capped: tuple[str, ...] = ()
    # Ответы, на которых стоит оценка: прошлых попыток определения и этой.
    answers: tuple[Observation, ...] = ()

    def items_to(self, sd: float) -> int | None:
        return next((n for n, s in enumerate(self.sds, 1) if s <= sd), None)


# Ответ на якорь: параметры, оценка темы до ответа и итоговая без ответа.
AnchorAnswer = tuple[Parameters, Response, Response]


class Market:
    """Банк одной специализации с калибровкой и окном показов, через который идут кандидаты."""

    def __init__(
        self,
        families: Sequence[Family],
        topics: Sequence[str],
        mechanics: Mechanics,
        rng: random.Random,
        *,
        calibrate: bool = True,
    ) -> None:
        self.mechanics = mechanics
        self.rng = rng
        self.calibrate = calibrate
        self.prior = specialization_prior(topics, mechanics)
        self.blueprint = Blueprint.from_prior(self.prior, mechanics)
        self.items = {}
        for f in families:
            start = expert(f.grade, mechanics)
            # Параметры якоря известны — на этом знании и держится шкала.
            truth = (
                start
                if f.anchor
                else Parameters(
                    start.discrimination * math.exp(rng.gauss(0, 0.3)),
                    start.difficulty + rng.gauss(0, 0.5),
                )
            )
            self.items[f.code] = Item(f, truth, start)
        self.window: deque[set[str]] = deque(maxlen=mechanics.exposure_window_attempts - 1)
        self.anchors: deque[list[AnchorAnswer]] = deque(
            maxlen=mechanics.calibration_link_window_attempts
        )
        self.before_link = self.rest_link = Link()
        self.attempts = 0

    def candidate(self) -> Candidate:
        """Уровни шире априорного оценщика; заявка — истинный грейд, на один выше или ниже."""
        common = self.rng.gauss(0, 1.2)
        level = {t: common + self.rng.gauss(0, 0.7) for t in self.prior.topics}
        grades = grades_by_threshold(self.mechanics.grade_thresholds)
        thresholds = self.mechanics.grade_thresholds
        overall = self._overall(level)
        true = max((i for i, g in enumerate(grades) if overall >= thresholds[g]), default=0)
        shift = self.rng.choices([0, 1, -1], weights=[0.6, 0.25, 0.15])[0]
        return Candidate(level, grades[min(max(true + shift, 0), len(grades) - 1)])

    def overall(self, candidate: Candidate) -> float:
        """Истинный общий уровень θ̄* — с весами тем, как в оценке."""
        return self._overall(candidate.level)

    def respond(self, candidate: Candidate, item: Item) -> bool:
        a, b = item.truth.discrimination, item.truth.difficulty
        return self.rng.random() < sigmoid(a * (candidate.level[item.family.topic] - b))

    def adaptive(
        self,
        candidate: Candidate,
        *,
        length: int | None = None,
        grade: str | None = None,
        previous: Sequence[Observation] = (),
        seen: frozenset[str] = frozenset(),
    ) -> Run:
        """Адаптивный тест на заявленный грейд; без `length` — до правила остановки, иначе ровно
        `length` заданий. Дотест каскада (§4) — на `grade`: оценка продолжает ответы `previous`
        прошлых попыток определения, их семейства `seen` идут после невиданных."""
        threshold = self.mechanics.grade_thresholds[grade or candidate.claimed]
        test = estimate(self.prior, previous)
        selection = estimate(selection_prior(self.prior, threshold), previous)
        counts: dict[str, int] = {}
        shown: list[str] = []
        sds: list[float] = []
        tally: dict[str, int] = {}
        for attempt in self.window:
            for code in attempt:
                tally[code] = tally.get(code, 0) + 1
        exposure = Exposure.from_mechanics(len(self.window), self.mechanics)
        answered: list[tuple[Item, Observation, Normal]] = []
        capped: list[str] = []
        limit = length or self.blueprint.max_items
        while len(shown) < limit:
            options = [
                Option(
                    code,
                    i.family.topic,
                    *_params(i),
                    shown=tally.get(code, 0),
                    seen_at=_SEEN if code in seen else None,
                )
                for code, i in self.items.items()
                if code not in shown
            ]
            picked = choose(self.blueprint, counts, selection, options, exposure, self.rng)
            if picked is None:
                break
            if picked.capped:
                capped.append(picked.code)
            item = self.items[picked.code]
            before = test.topic(item.family.topic)
            correct = self.respond(candidate, item)
            obs = Observation(item.family.topic, correct, *_params(item))
            test, selection = update(test, obs), update(selection, obs)
            self._learn(item, Response(before, correct))
            answered.append((item, obs, before))
            shown.append(picked.code)
            counts[item.family.topic] = counts.get(item.family.topic, 0) + 1
            sds.append(test.overall().sd)
            if length is None and should_stop(self.blueprint, counts, test.overall()):
                break
        self._finish(set(shown), answered, previous)
        answers = (*previous, *(obs for _, obs, _ in answered))
        return Run(sds, shown, test.overall(), tuple(capped), answers)

    def fixed(self, candidate: Candidate, length: int, *, target: float | None = None) -> Run:
        """Фиксированный бланк с тем же покрытием тем: по кругу тем, в теме — семейства с
        экспертной сложностью ближе к `target` первыми. С `target` бланк общий для всех (схема
        S2 плана валидации); без него — по середине заявленного грейда."""
        if target is None:
            target = self.mechanics.expert_difficulty_by_grade[candidate.claimed]
        queues = {
            t: sorted(
                (i for i in self.items.values() if i.family.topic == t),
                key=lambda i: (
                    abs(expert(i.family.grade, self.mechanics).difficulty - target),
                    i.family.code,
                ),
            )
            for t in self.prior.topics
        }
        order: list[Item] = []
        while any(queues.values()) and len(order) < length:
            for t in self.prior.topics:
                if queues[t] and len(order) < length:
                    order.append(queues[t].pop(0))
        test = initial(self.prior)
        sds = []
        for item in order:
            obs = Observation(item.family.topic, self.respond(candidate, item), *_params(item))
            test = update(test, obs)
            sds.append(test.overall().sd)
        return Run(sds, [i.family.code for i in order], test.overall())

    def _overall(self, level: dict[str, float]) -> float:
        return sum(w * level[t] for t, w in zip(self.prior.topics, self.prior.weights, strict=True))

    def _learn(self, item: Item, response: Response) -> None:
        """Эло до пакетной переоценки; после неё текущие параметры — опорные (§7)."""
        if self.calibrate and not item.family.anchor and not item.refitted:
            linked = Response(self.before_link.apply(response.level), response.correct)
            item.params = elo_update(item.params, linked, item.responses, self.mechanics)
        item.responses += 1

    def _finish(
        self,
        shown: set[str],
        answered: list[tuple[Item, Observation, Normal]],
        previous: Sequence[Observation] = (),
    ) -> None:
        """Остановка попытки, как в сервисе: итоговые оценки без ответа по всему определению,
        пересчёт связок шкалы по якорям, пакетная переоценка набравших ответы семейств."""
        self.window.append(shown)
        self.attempts += 1
        if not self.calibrate:
            return
        observations = [*previous, *(obs for _, obs, _ in answered)]
        levels = rest_levels(self.prior, observations, range(len(previous), len(observations)))
        self.anchors.append(
            [
                (item.params, Response(before, obs.correct), Response(level, obs.correct))
                for (item, obs, before), level in zip(answered, levels, strict=True)
                if item.family.anchor
            ]
        )
        anchors = [a for attempt in self.anchors for a in attempt]
        self.before_link = fit_link([(p, before) for p, before, _ in anchors], self.mechanics)
        self.rest_link = fit_link([(p, rest) for p, _, rest in anchors], self.mechanics)
        for (item, obs, _), level in zip(answered, levels, strict=True):
            item.answers.append(Response(level, obs.correct))
            due = len(item.answers) >= self.mechanics.calibration_refit_min_responses
            if due and not item.refitted and not item.family.anchor:
                start = expert(item.family.grade, self.mechanics)
                linked = [Response(self.rest_link.apply(r.level), r.correct) for r in item.answers]
                item.params = refit(linked, start, self.mechanics)
                item.refitted = True


def market(specialization: str, mechanics: Mechanics, seed: int = SEED) -> Market:
    topics = next(
        [t.code for t in s.topics]
        for s in load_catalog().specializations
        if s.code == specialization
    )
    return Market(families_for_topics(topics), topics, mechanics, random.Random(seed))


def calibration_quality(m: Market) -> tuple[float, float, float]:
    """r(b̂, b*), RMSE(b̂, b*) и RMSE экспертных b₀ по неякорным семействам."""
    items = [i for i in m.items.values() if not i.family.anchor]
    truth = [i.truth.difficulty for i in items]
    start = [expert(i.family.grade, m.mechanics).difficulty for i in items]
    current = [i.params.difficulty for i in items]
    return pearson(current, truth), rmse(current, truth), rmse(start, truth)


def mean_responses(m: Market) -> float:
    items = [i for i in m.items.values() if not i.family.anchor]
    return sum(i.responses for i in items) / len(items)


def _params(item: Item) -> tuple[float, float]:
    return item.params.discrimination, item.params.difficulty


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / math.sqrt(vx * vy)


def rmse(xs: Sequence[float], ys: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys, strict=True)) / len(xs))


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _compare(m: Market, candidates: int) -> str:
    """Те же кандидаты проходят адаптивный тест и два фиксированных бланка без лимита заданий:
    медиана числа заданий до σ̄ ≤ `test_stop_sd`, доля дошедших за `test_max_items`, средняя σ̄
    на длине 20, честность погрешности адаптивного на остановке — sd((θ̂ − θ*) / σ̂)."""
    limit = m.mechanics.test_max_items
    bank = len(m.items)
    m.blueprint = replace(m.blueprint, max_items=bank)
    target = m.mechanics.test_stop_sd
    runs: dict[str, list[int]] = {"adaptive": [], "common": [], "claimed": []}
    at_20: dict[str, list[float]] = {"adaptive": [], "common": []}
    z = []
    for _ in range(candidates):
        c = m.candidate()
        adaptive = m.adaptive(c)
        common = m.fixed(c, bank, target=0.0)
        claimed = m.fixed(c, bank)
        for name, run in (("adaptive", adaptive), ("common", common), ("claimed", claimed)):
            runs[name].append(run.items_to(target) or bank + 1)
        z.append((adaptive.overall.mean - m.overall(c)) / adaptive.overall.sd)
        at_20["common"].append(common.sds[19])
    m.calibrate = False
    for _ in range(candidates):
        at_20["adaptive"].append(m.adaptive(m.candidate(), length=20).sds[-1])
    m.blueprint = replace(m.blueprint, max_items=limit)

    def cell(name: str) -> str:
        ns = runs[name]
        within = sum(n <= limit for n in ns) / len(ns)
        return f"{median(ns):4.1f} ({within:.2f})"

    ratio = median(runs["adaptive"]) / median(runs["common"])
    spread = statistics.pstdev(z)
    mean_20 = {k: sum(v) / len(v) for k, v in at_20.items()}
    return (
        f"{cell('adaptive')} | {cell('common')} | {cell('claimed')} | {ratio:.2f} | "
        f"{mean_20['adaptive']:.3f} / {mean_20['common']:.3f} | {spread:.2f}"
    )


def warm(m: Market, responses: int = WARM_RESPONSES) -> Market:
    """Калибровка на потоке кандидатов до `responses` ответов на семейство в среднем; дальше
    параметры заморожены."""
    while mean_responses(m) < responses:
        m.adaptive(m.candidate())
    m.calibrate = False
    return m


def true_grade(m: Market, candidate: Candidate) -> str | None:
    """Истинный грейд — полоса θ̄*; None — ниже порога младшего грейда."""
    thresholds = m.mechanics.grade_thresholds
    level = m.overall(candidate)
    passed = [g for g in grades_by_threshold(thresholds) if level >= thresholds[g]]
    return passed[-1] if passed else None


def determine(m: Market, candidate: Candidate) -> tuple[str | None, Normal]:
    """Первичное определение категории (§4): тест на заявленный грейд и каскад дотестов вниз.
    Грейд None — без категории; оценка общего уровня — на конец определения."""
    grade = candidate.claimed
    answers: tuple[Observation, ...] = ()
    seen: frozenset[str] = frozenset()
    while True:
        run = m.adaptive(candidate, grade=grade, previous=answers, seen=seen)
        answers, seen = run.answers, seen | set(run.shown)
        decision = decide(
            run.overall,
            grade,
            thresholds=m.mechanics.grade_thresholds,
            confidence=m.mechanics.grade_confidence,
            has_items=lambda _: True,
        )
        match decision:
            case Assign(assigned):
                return assigned, run.overall
            case Offer(lower):
                grade = lower
            case _:
                return None, run.overall


@dataclass(frozen=True)
class Honesty:
    """Тест на заявленный грейд с лимитом заданий: z = (θ̂ − θ*) / σ̂ общего уровня на остановке,
    длина теста и сколько семейств взято сверх потолка показов. Погрешность честная, когда
    sd(z) ≈ 1."""

    z: list[float]
    lengths: list[int]
    capped: list[int]


def honesty(m: Market, candidates: int) -> Honesty:
    z, lengths, capped = [], [], []
    for _ in range(candidates):
        c = m.candidate()
        run = m.adaptive(c)
        z.append((run.overall.mean - m.overall(c)) / run.overall.sd)
        lengths.append(len(run.shown))
        capped.append(len(run.capped))
    return Honesty(z, lengths, capped)


@dataclass(frozen=True)
class Stability:
    """Повтор первичного определения с независимыми экземплярами (M9) и совпадение с истиной
    (M10)."""

    # Доля пар с совпавшей категорией, включая «без категории», и из них — на истинном грейде.
    agreement: float
    agreement_true: float
    # Каппа Коэна по категориям.
    kappa: float
    # r(θ̄₁, θ̄₂).
    correlation: float
    # Доля пар с разницей не больше грейда.
    within_one: float
    # Доли определений с грейдом выше истинного и равным ему.
    overestimate: float
    exact: float


def stability(m: Market, pairs: int) -> Stability:
    grades: list[str | None] = [None, *grades_by_threshold(m.mechanics.grade_thresholds)]
    rank = {g: i for i, g in enumerate(grades)}
    results: list[tuple[str | None, str | None]] = []
    levels: list[tuple[float, float]] = []
    over = exact = both_true = 0
    for _ in range(pairs):
        c = m.candidate()
        truth = rank[true_grade(m, c)]
        (first, first_level), (second, second_level) = determine(m, c), determine(m, c)
        results.append((first, second))
        levels.append((first_level.mean, second_level.mean))
        over += (rank[first] > truth) + (rank[second] > truth)
        exact += (rank[first] == truth) + (rank[second] == truth)
        both_true += rank[first] == rank[second] == truth
    return Stability(
        agreement=sum(a == b for a, b in results) / pairs,
        agreement_true=both_true / pairs,
        kappa=cohen_kappa(results, grades),
        correlation=pearson([a for a, _ in levels], [b for _, b in levels]),
        within_one=sum(abs(rank[a] - rank[b]) <= 1 for a, b in results) / pairs,
        overestimate=over / (2 * pairs),
        exact=exact / (2 * pairs),
    )


def cohen_kappa(pairs: Sequence[tuple[object, object]], categories: Sequence[object]) -> float:
    """Каппа Коэна; не определена, когда все определения в одной категории, — тогда nan."""
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    expected = sum(
        sum(a == c for a, _ in pairs) / n * sum(b == c for _, b in pairs) / n for c in categories
    )
    return (observed - expected) / (1 - expected) if expected < 1 else math.nan


def _warm_run(
    job: tuple[str, int, Mechanics, int, int],
) -> tuple[str, float, Honesty, Stability | None]:
    """Прогрев банка специализации и замеры на нём — задача для пула процессов."""
    code, seed, mechanics, candidates, pairs = job
    m = warm(market(code, mechanics, seed))
    measured = honesty(m, candidates)
    return (
        code,
        mechanics.level_sd_inflation,
        measured,
        stability(m, pairs) if pairs else None,
    )


def _pool() -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1))


def report_honesty(mechanics: Mechanics, seed: int, candidates: int, pairs: int) -> None:
    """Честность погрешности и стабильность грейда по специализациям на прогретом банке."""
    specializations = [s.code for s in load_catalog().specializations]
    jobs = [(code, seed, mechanics, candidates, pairs) for code in specializations]
    print(
        f"Прогретый банк ({WARM_RESPONSES} ответов на семейство), сид {seed}, "
        f"κ = {mechanics.level_sd_inflation}, test_stop_sd = {mechanics.test_stop_sd}: "
        f"{candidates} тестов на заявленный грейд, {pairs} пар первичных определений"
    )
    print(
        "| Специализация | sd(z) | Среднее z | Медиана заданий | Доля до лимита | "
        "Сверх потолка показов | Совпадение категорий | Из них на истинном грейде | Каппа | "
        "r(θ̄₁, θ̄₂) | Разница ≤ 1 грейда | Завышение | Точное совпадение |"
    )
    print("|---" * 13 + "|")
    with _pool() as pool:
        for code, _, h, st in pool.map(_warm_run, jobs):
            assert st is not None
            at_limit = sum(n >= mechanics.test_max_items for n in h.lengths) / len(h.lengths)
            over_cap = sum(h.capped) / sum(h.lengths)
            print(
                f"| {code} | {statistics.pstdev(h.z):.3f} | {statistics.fmean(h.z):+.3f} | "
                f"{median(h.lengths):.0f} | {at_limit:.2f} | {over_cap:.3f} | {st.agreement:.3f} | "
                f"{st.agreement_true:.3f} | "
                f"{st.kappa:.3f} | {st.correlation:.3f} | {st.within_one:.3f} | "
                f"{st.overestimate:.3f} | {st.exact:.3f} |",
                flush=True,
            )


def tune_inflation(mechanics: Mechanics, candidates: int) -> float:
    """Подбор `level_sd_inflation` на настроечном наборе D3 по правилу плана валидации.

    Для каждого κ из `INFLATION_GRID` банк прогревается заново — κ меняет и длину теста, и
    калибровку, — и меряется sd(z) по всем кандидатам всех специализаций вместе. Погрешность
    модели занижена в c раз, поэтому sd(z) ≈ c / κ: c — среднее κ · sd(z) по сетке, выбранное κ —
    c, округлённое до шага сетки. По отдельной точке сетки выбирать нельзя: разброс от прогрева
    банка больше разницы соседних точек."""
    specializations = [s.code for s in load_catalog().specializations]
    jobs = [
        (code, TUNING_SEED, mechanics.model_copy(update={"level_sd_inflation": k}), candidates, 0)
        for k in INFLATION_GRID
        for code in specializations
    ]
    z: dict[float, dict[str, list[float]]] = {k: {} for k in INFLATION_GRID}
    with _pool() as pool:
        for code, k, h, _ in pool.map(_warm_run, jobs):
            z[k][code] = h.z
    print(f"Подбор κ: сид {TUNING_SEED}, прогретый банк, {candidates} тестов на специализацию")
    print("| κ | sd(z) вместе | κ · sd(z) | " + " | ".join(specializations) + " |")
    print("|---" * (len(specializations) + 3) + "|")
    understated = []
    for k, by_code in z.items():
        pooled = statistics.pstdev([v for code in specializations for v in by_code[code]])
        understated.append(k * pooled)
        cells = " | ".join(f"{statistics.pstdev(by_code[code]):.3f}" for code in specializations)
        print(f"| {k:.2f} | {pooled:.3f} | {k * pooled:.3f} | {cells} |")
    c = statistics.fmean(understated)
    step = INFLATION_GRID[1] - INFLATION_GRID[0]
    chosen = round(round(c / step) * step, 2)
    print(f"\nc = {c:.3f}, выбрано κ = {chosen:.2f}")
    return chosen


def report(mechanics: Mechanics) -> None:
    specializations = [s.code for s in load_catalog().specializations]
    checkpoints = (50, 100, 200, 500)

    print("Калибровка: r(b̂, b*) / RMSE(b̂, b*) при среднем числе ответов на семейство")
    print("| Специализация | " + " | ".join(str(n) for n in checkpoints) + " | RMSE b₀ |")
    print("|---" * (len(checkpoints) + 2) + "|")
    warmed: dict[str, Market] = {}
    for code in specializations:
        m = market(code, mechanics)
        cells = []
        for n in checkpoints:
            while mean_responses(m) < n:
                m.adaptive(m.candidate())
            r, error, start = calibration_quality(m)
            cells.append(f"{r:.3f} / {error:.3f}")
        print(f"| {code} | " + " | ".join(cells) + f" | {start:.3f} |", flush=True)
        warmed[code] = m

    header = (
        "| Специализация | Адаптивный | Общий бланк | Бланк по заявке | Адаптивный / общий | "
        "σ̄ на 20: адаптивный / общий | sd(z) адаптивного |"
    )
    cold = {code: market(code, mechanics) for code in specializations}
    for title, markets in (
        ("Холодный банк — экспертные параметры", cold),
        ("Прогретый банк — после калибровки выше", warmed),
    ):
        print(f"\n{title}: медиана заданий до σ̄ ≤ test_stop_sd (доля дошедших за лимит)")
        print(header)
        print("|---" * 7 + "|")
        for code in specializations:
            m = markets[code]
            m.calibrate = False
            print(f"| {code} | {_compare(m, 300)} |", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tests.simulation")
    parser.add_argument("command", nargs="?", choices=("honesty", "tune"))
    parser.add_argument("--seed", type=int, default=SEED, help="сид для honesty, по умолчанию D1")
    parser.add_argument("--candidates", type=int, default=1500)
    parser.add_argument("--pairs", type=int, default=1500)
    args = parser.parse_args()
    mechanics = Mechanics.from_yaml(BACKEND_DIR / "config" / "mechanics.yaml")
    match args.command:
        case "honesty":
            report_honesty(mechanics, args.seed, args.candidates, args.pairs)
        case "tune":
            tune_inflation(mechanics, args.candidates)
        case _:
            report(mechanics)


if __name__ == "__main__":
    main()
