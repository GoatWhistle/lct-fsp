"""Модель принятия на стенде (mechanics.md, §13; docs/validation-plan.md, M7): пары «потребность —
кандидат», решения синтетических кандидатов, обучение и оценка.

Пара — кандидат из подборки потребности, построенной теми же сценариями, что HTTP: категория по
тесту и S — то, что записала платформа. На пару — top-K кандидатов по S и доля случайных из той же
подборки сверх них. Загрузка кандидата открытыми приглашениями — Poisson со средним, растущим с
перцентилем S: сильных зовут чаще. Решение — Бернулли по правилу `AcceptanceRule` из скрытой
склонности и наблюдаемых факторов; признаки модели — `AcceptanceFeatures` из наблюдаемого, так же,
как в проде. Склонность в признаки не попадает.

Обучение — `train`: набор со своим сидом `TRAIN_SEED`, 20 000 пар, файл модели в репо и базовые
линии M7 рядом с ним. Отложенные пары — по 5 000 на D1 и D2 из их же прогонов отчёта.
"""

import bisect
import itertools
import json
import math
import random
import statistics
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from app.adapter.acceptance import acceptance_model
from app.adapter.acceptance_catboost import CatBoostAcceptanceModel, Training, fit
from app.domain.acceptance import COLUMNS, Row, encode
from app.domain.selection import AcceptanceFeatures
from app.domain.work import SalaryRange
from settings import BACKEND_DIR, Mechanics
from validation.metrics import ece, roc_auc
from validation.population import (
    Dataset,
    Employer,
    Generator,
    GeneratorParams,
    ObservedCandidate,
    SyntheticNeed,
)
from validation.simulate import Scored
from validation.truth import CandidateTruth

# Обучающая синтетика — свой сид, отдельный от D1 и D2.
TRAIN_SEED = 20261008
TRAIN_PAIRS = 20_000
HOLDOUT_PAIRS = 5_000
# Базовые линии M7, обученные на тех же парах, что модель, — рядом с отчётом стенда.
BASELINES_FILE = BACKEND_DIR / "validation" / "data" / "acceptance_baselines.json"
# Сетка монотонности: отношение середины вилки к ожиданию 0,5–2,0 шагом 0,05, загрузка 0–10;
# остальные признаки — с `GRID_ROWS` строк отложенной выборки.
GRID_RATIOS = tuple(round(0.5 + 0.05 * i, 2) for i in range(31))
GRID_LOADS = tuple(range(11))
GRID_ROWS = 50
ECE_BINS = 10


@dataclass(frozen=True)
class Offer:
    """Пара обучения или оценки: признаки модели и решение кандидата."""

    need: uuid.UUID
    candidate: uuid.UUID
    features: AcceptanceFeatures
    accepted: int


def needs_for(pairs: int, params: GeneratorParams, specializations: int) -> int:
    """Потребностей пар на специализацию — с запасом: у потребности бывает меньше кандидатов,
    чем пар на неё."""
    per_need = params.acceptance_train_top_k + round(
        params.acceptance_random_share * params.acceptance_train_top_k
    )
    return math.ceil(1.25 * pairs / per_need / specializations)


def offer_needs(generator: Generator, dataset: Dataset, pairs: int) -> list[SyntheticNeed]:
    """Потребности пар набора — своим потоком генератора, по кругу специализаций: пары
    обрезаются до `pairs` поровну по специализациям, а не на последней."""
    codes = list(generator.catalog.specializations)
    count = needs_for(pairs, dataset.params, len(codes))
    by_code = [generator.needs(c, dataset.employers, count, stream="offers") for c in codes]
    return [needs[i] for i in range(count) for needs in by_code]


def percentiles(scored: Sequence[Scored]) -> dict[uuid.UUID, float]:
    """Перцентиль S кандидата в подборке, 0–1; ничьи — средним местом."""
    if len(scored) == 1:
        return {scored[0].candidate: 0.5}
    ordered = sorted(s.match_score for s in scored)
    n = len(ordered)
    found = {}
    for s in scored:
        below = bisect.bisect_left(ordered, s.match_score)
        equal = bisect.bisect_right(ordered, s.match_score) - below
        found[s.candidate] = (below + (equal - 1) / 2) / (n - 1)
    return found


def chosen(scored: Sequence[Scored], params: GeneratorParams, rng: random.Random) -> list[Scored]:
    """Top-K по S и случайные кандидаты той же подборки сверх них."""
    ranked = sorted(scored, key=lambda s: (-s.match_score, s.candidate))
    k = params.acceptance_train_top_k
    rest = ranked[k:]
    extra = min(len(rest), round(params.acceptance_random_share * k))
    return ranked[:k] + rng.sample(rest, extra)


def poisson(mean: float, rng: random.Random) -> int:
    """Пуассон методом Кнута: средние здесь — единицы."""
    limit, k, p = math.exp(-mean), 0, rng.random()
    while p > limit:
        k += 1
        p *= rng.random()
    return k


def features_of(
    need: SyntheticNeed,
    employer: Employer,
    seen: ObservedCandidate,
    scored: Scored,
    load: int,
    mechanics: Mechanics,
) -> AcceptanceFeatures:
    """Признаки пары из наблюдаемого — те же поля, что прод берёт из потребности, профиля
    кандидата и компании."""
    form = need.form
    return AcceptanceFeatures(
        salary=SalaryRange.optional(form.salary_from, form.salary_to),
        expected_salary=seen.expected_salary,
        market_salary=mechanics.market_salary_median[scored.grade],
        work_formats=seen.work_formats,
        city=seen.city,
        relocation=seen.relocation,
        need_work_format=form.work_format,
        need_city=form.city,
        grade=scored.grade,
        match_score=scored.match_score,
        open_invitations=load,
        industries=frozenset(seen.industries),
        company_industry=employer.industry,
    )


def make_offers(
    dataset: Dataset,
    needs: Iterable[SyntheticNeed],
    scored: Mapping[uuid.UUID, Sequence[Scored]],
    mechanics: Mechanics,
    total: int,
) -> list[Offer]:
    """Пары по потребностям `needs` по порядку — не больше `total`, решения кандидатов по правилу.
    Случайность пары — поток её потребности: от числа процессов и порядка задач не зависит."""
    params = dataset.params
    truth = {t.id: t for t in dataset.truths}
    seen = {o.id: o for o in dataset.observed}
    employers = {e.id: e for e in dataset.employers}
    found: list[Offer] = []
    for need in needs:
        pool = scored.get(need.id, ())
        if not pool:
            continue
        rng = random.Random(f"{params.seed}:acceptance:{need.id}")
        place = percentiles(pool)
        for s in chosen(pool, params, rng):
            load = poisson(params.acceptance_load_mean * (0.5 + place[s.candidate]), rng)
            features = features_of(
                need, employers[need.employer], seen[s.candidate], s, load, mechanics
            )
            accepted = rng.random() < decision(truth[s.candidate], features, params)
            found.append(Offer(need.id, s.candidate, features, int(accepted)))
            if len(found) == total:
                return found
    return found


def decision(truth: CandidateTruth, features: AcceptanceFeatures, params: GeneratorParams) -> float:
    """P(кандидат примет) по скрытой истине — только для генерации решения."""
    return params.acceptance.probability(truth.acceptance, features)


def rows(offers: Sequence[Offer]) -> list[Row]:
    found = []
    for o in offers:
        row = encode(o.features)
        assert row is not None, "у синтетической потребности вилка всегда есть"
        found.append(row)
    return found


# --- Базовые линии ------------------------------------------------------------------------------

SALARY_TO_EXPECTED = COLUMNS.index("salary_to_expected")


@dataclass(frozen=True)
class Baselines:
    """Базовые линии M7: логистическая регрессия по ln(середина вилки / ожидание) и константа —
    средняя доля принятий обучающих пар."""

    intercept: float
    slope: float
    constant: float

    def logistic(self, row: Row) -> float:
        x = row[SALARY_TO_EXPECTED]
        assert isinstance(x, float)
        return 1 / (1 + math.exp(-(self.intercept + self.slope * x)))


def logistic_fit(xs: Sequence[float], ys: Sequence[int], steps: int = 50) -> tuple[float, float]:
    """Логистическая регрессия с одним признаком — Ньютоном до сходимости."""
    a = b = 0.0
    for _ in range(steps):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys, strict=True):
            p = 1 / (1 + math.exp(-(a + b * x)))
            w = p * (1 - p)
            ga += y - p
            gb += (y - p) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a + da, b + db
        if abs(da) + abs(db) < 1e-12:
            break
    return a, b


def baselines(train: Sequence[Row], labels: Sequence[int]) -> Baselines:
    """Регрессия — на парах с ожиданием кандидата; константа — на всех."""
    known = [
        (float(r[SALARY_TO_EXPECTED]), y)
        for r, y in zip(train, labels, strict=True)
        if not math.isnan(float(r[SALARY_TO_EXPECTED]))
    ]
    a, b = logistic_fit([x for x, _ in known], [y for _, y in known])
    return Baselines(a, b, statistics.fmean(labels))


def save_baselines(found: Baselines, path: Path = BASELINES_FILE) -> None:
    data = {"intercept": found.intercept, "slope": found.slope, "constant": found.constant}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_baselines(path: Path = BASELINES_FILE) -> Baselines | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Baselines(data["intercept"], data["slope"], data["constant"])


# --- Оценка -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Quality:
    roc_auc: float
    ece: float


def quality(predicted: Sequence[float], labels: Sequence[int]) -> Quality:
    return Quality(roc_auc(predicted, labels), ece(predicted, labels, ECE_BINS))


@dataclass(frozen=True)
class Monotonicity:
    """Соседние точки сетки, где P не нарушает ограничение, — из всех пар соседних точек."""

    salary_ok: int
    salary_total: int
    load_ok: int
    load_total: int

    @property
    def share(self) -> float:
        return (self.salary_ok + self.load_ok) / (self.salary_total + self.load_total)


def monotonicity(
    predict: Callable[[Sequence[AcceptanceFeatures]], Sequence[float | None]],
    offers: Sequence[Offer],
) -> Monotonicity:
    """Сетка монотонности на первых `GRID_ROWS` парах: вилка ↑ — P не ниже, открытые
    приглашения ↑ — P не выше. Вилка на сетке — точка: середина — отношение к ожиданию."""
    salary_ok = salary_total = load_ok = load_total = 0
    for offer in offers[:GRID_ROWS]:
        f = offer.features
        assert f.expected_salary is not None
        by_salary = [
            replace(f, salary=SalaryRange(m, m))
            for m in (round(r * f.expected_salary) for r in GRID_RATIOS)
        ]
        by_load = [replace(f, open_invitations=n) for n in GRID_LOADS]
        ps = [_known(p) for p in predict(by_salary)]
        pl = [_known(p) for p in predict(by_load)]
        salary_ok += sum(b >= a for a, b in itertools.pairwise(ps))
        salary_total += len(ps) - 1
        load_ok += sum(b <= a for a, b in itertools.pairwise(pl))
        load_total += len(pl) - 1
    return Monotonicity(salary_ok, salary_total, load_ok, load_total)


def _known(p: float | None) -> float:
    assert p is not None, "у точки сетки вилка есть — P посчитана"
    return p


@dataclass(frozen=True)
class Evaluation:
    """M7 на отложенных парах набора."""

    pairs: int
    accepted: float
    model: Quality
    logistic: Quality
    constant: Quality
    monotonicity: Monotonicity


def evaluate(
    model: CatBoostAcceptanceModel, found: Baselines, offers: Sequence[Offer]
) -> Evaluation:
    labels = [o.accepted for o in offers]
    table = rows(offers)
    return Evaluation(
        pairs=len(offers),
        accepted=statistics.fmean(labels),
        model=quality(model.predict_rows(table), labels),
        logistic=quality([found.logistic(r) for r in table], labels),
        constant=quality([found.constant] * len(table), labels),
        monotonicity=monotonicity(model.predict, offers),
    )


def training(mechanics: Mechanics) -> Training:
    return Training(
        iterations=mechanics.acceptance_model_iterations,
        depth=mechanics.acceptance_model_depth,
        learning_rate=mechanics.acceptance_model_learning_rate,
        random_seed=mechanics.acceptance_model_random_seed,
        thread_count=mechanics.acceptance_model_thread_count,
    )


def train_on(
    offers: Sequence[Offer], mechanics: Mechanics
) -> tuple[CatBoostAcceptanceModel, Baselines]:
    table, labels = rows(offers), [o.accepted for o in offers]
    return fit(table, labels, training(mechanics)), baselines(table, labels)


def load_model(path: Path) -> CatBoostAcceptanceModel | None:
    """Модель, которую загрузит прод по тому же пути; файла нет — None."""
    model = acceptance_model(path)
    return model if isinstance(model, CatBoostAcceptanceModel) else None
