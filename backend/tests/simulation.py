"""Симуляция теста на кандидатах с известной истиной — для проверок адаптивности и калибровки.

Истина (уровни кандидатов, параметры семейств) живёт только здесь: движок теста и калибровка
видят ответы и свои оценки, как в сервисе. Истина отличается от модели оценки, как в наборе D1
плана валидации: уровни шире априорного оценщика, b* = b₀ + N(0; 0,5²), ln a* = ln a₀ + N(0; 0,3²)
— калибровке есть что исправлять.

Сравнение адаптивного теста с фиксированным бланком и сходимость калибровки по всем
специализациям: `uv run python -m tests.simulation`.
"""

import math
import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from app.assessment.adaptive import (
    Blueprint,
    Exposure,
    Option,
    choose,
    selection_prior,
    should_stop,
)
from app.assessment.bank import Family, families_for_topics
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
from app.assessment.determination import grades_by_threshold
from app.config import BACKEND_DIR, Mechanics
from app.skills.irt import Normal, Observation, initial, sigmoid, update
from app.skills.service import specialization_prior

SEED = 20261005


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

    def adaptive(self, candidate: Candidate, *, length: int | None = None) -> Run:
        """Адаптивный тест; без `length` — до правила остановки, иначе ровно `length` заданий."""
        threshold = self.mechanics.grade_thresholds[candidate.claimed]
        test = initial(self.prior)
        selection = initial(selection_prior(self.prior, threshold))
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
                Option(code, i.family.topic, *_params(i), shown=tally.get(code, 0))
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
        self._finish(set(shown), answered)
        return Run(sds, shown, test.overall(), tuple(capped))

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
        if self.calibrate and not item.family.anchor:
            linked = Response(self.before_link.apply(response.level), response.correct)
            item.params = elo_update(item.params, linked, item.responses, self.mechanics)
        item.responses += 1

    def _finish(self, shown: set[str], answered: list[tuple[Item, Observation, Normal]]) -> None:
        """Остановка попытки, как в сервисе: итоговые оценки без ответа, пересчёт связок шкалы
        по якорям, пакетная переоценка набравших ответы семейств."""
        self.window.append(shown)
        self.attempts += 1
        if not self.calibrate:
            return
        observations = [obs for _, obs, _ in answered]
        levels = rest_levels(self.prior, observations, range(len(answered)))
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
    spread = math.sqrt(sum(v * v for v in z) / len(z) - (sum(z) / len(z)) ** 2)
    mean_20 = {k: sum(v) / len(v) for k, v in at_20.items()}
    return (
        f"{cell('adaptive')} | {cell('common')} | {cell('claimed')} | {ratio:.2f} | "
        f"{mean_20['adaptive']:.3f} / {mean_20['common']:.3f} | {spread:.2f}"
    )


def main() -> None:
    mechanics = Mechanics.from_yaml(BACKEND_DIR / "config" / "mechanics.yaml")
    specializations = [s.code for s in load_catalog().specializations]
    checkpoints = (50, 100, 200, 500)

    print("Калибровка: r(b̂, b*) / RMSE(b̂, b*) при среднем числе ответов на семейство")
    print("| Специализация | " + " | ".join(str(n) for n in checkpoints) + " | RMSE b₀ |")
    print("|---" * (len(checkpoints) + 2) + "|")
    warm: dict[str, Market] = {}
    for code in specializations:
        m = market(code, mechanics)
        cells = []
        for n in checkpoints:
            while mean_responses(m) < n:
                m.adaptive(m.candidate())
            r, error, start = calibration_quality(m)
            cells.append(f"{r:.3f} / {error:.3f}")
        print(f"| {code} | " + " | ".join(cells) + f" | {start:.3f} |", flush=True)
        warm[code] = m

    header = (
        "| Специализация | Адаптивный | Общий бланк | Бланк по заявке | Адаптивный / общий | "
        "σ̄ на 20: адаптивный / общий | sd(z) адаптивного |"
    )
    cold = {code: market(code, mechanics) for code in specializations}
    for title, markets in (
        ("Холодный банк — экспертные параметры", cold),
        ("Прогретый банк — после калибровки выше", warm),
    ):
        print(f"\n{title}: медиана заданий до σ̄ ≤ test_stop_sd (доля дошедших за лимит)")
        print(header)
        print("|---" * 7 + "|")
        for code in specializations:
            m = markets[code]
            m.calibrate = False
            print(f"| {code} | {_compare(m, 300)} |", flush=True)


if __name__ == "__main__":
    main()
