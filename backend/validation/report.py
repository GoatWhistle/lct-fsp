"""Отчёт стенда валидации одной командой (docs/validation-plan.md, правило 7): прогон D1 и D2 по
сидам плана и `docs/validation-report.md` — по каждой метрике плана определение, значение на D1
и D2 рядом, порог и вердикт; не посчитанные здесь — «ожидает данных».

Прогон — `collect`: задачи `validation.simulate` в пуле процессов, по задаче на специализацию
набора. Метрики — здесь: только этот код соединяет записанное платформой со скрытой истиной
набора. Раздел метрики — функция `Runs → Section` под декоратором `section`: новый раздел
добавляется своей функцией, остальные не правятся. Первыми в отчёте — M9 и M10, их жюри
проверит руками, дальше — по номерам плана.
"""

import bisect
import heapq
import math
import os
import statistics
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.domain.determination import grades_by_threshold
from app.domain.selection import NeedSnapshot, SelectionBlock
from app.usecase.skill_profile import specialization_prior
from settings import BACKEND_DIR, Mechanics, Settings
from validation import d4, resume_parsing
from validation.acceptance import (
    HOLDOUT_PAIRS,
    Offer,
    evaluate,
    load_baselines,
    load_model,
    make_offers,
    offer_needs,
)
from validation.baselines import (
    B3_SYSTEM,
    BM25_B,
    BM25_K1,
    PASSAGE,
    QUERY,
    Baseline,
    Document,
    LlmRanker,
    need_text,
    resume_text,
)
from validation.e5 import MODEL as E5_MODEL
from validation.e5 import REVISION as E5_REVISION
from validation.figures import (
    Curve,
    CurvePanel,
    Panel,
    Series,
    curves_svg,
    ecdf_svg,
    reliability_svg,
)
from validation.invitation_market import STRATEGIES
from validation.invitation_market import metrics as market_metrics
from validation.llm_attack import CLAIMED
from validation.main import Catalog, catalog
from validation.market_weeks import MarketInput
from validation.metrics import (
    cohen_kappa,
    ece,
    median,
    ndcg_at,
    pearson,
    point_biserial,
    precision_at,
    quantile,
    reliability,
    spearman,
    weighted_kappa,
)
from validation.population import (
    DATASETS,
    Dataset,
    Gender,
    Generator,
    Pair,
    Person,
    SyntheticNeed,
    label,
    snapshot,
)
from validation.protection import (
    D3,
    DRIFT_GRID,
    LEAKS,
    MAIN_LEAK,
    MAIN_RHO,
    RHOS,
    SCHEMES,
    AttackSummary,
    Helper,
    ProtectionJob,
    ProtectionRun,
    ProtectionScale,
    Twins,
    rank_of,
    run_protection,
    summarize,
    tune_threshold,
)
from validation.protection import flagged_share as drift_flagged
from validation.recorded import Recording
from validation.simulate import (
    CORRUPTED_SHARE,
    Adaptivity,
    FamilyFit,
    ItemFit,
    Job,
    Outcome,
    Placed,
    Scale,
    SpecRun,
    run_cold,
    run_fit,
    run_spec,
)
from validation.truth import RELEVANCE_EDGES, CandidateTruth, Corruption, Persona
from validation.twins import M3_PER_NEED, Twin, TwinKind, twins

# Базовые линии набора: (имя набора, сид, корпус резюме пула специализации) → ранжировщики.
BaselineSource = Callable[[str, int, Sequence[str]], list[Baseline]]
BASELINES = ("B1", "B2", "B3")

DOCS = BACKEND_DIR.parent / "docs"
REPORT = DOCS / "validation-report.md"
# Картинки отчёта — рядом с ним, в каталоге его имени.
FIGURES = "validation-report"
PLAN = "validation-plan.md"
SETS = ("d1", "d2")
# M21 план считает только на D1.
FIT_SETS = ("d1",)
PLAN_SCALE = Scale()
PLAN_PROTECTION = ProtectionScale()
TOP = 10

# Метрики плана: номер → название и раздел плана со ссылкой.
METRICS: dict[str, tuple[str, str]] = {
    "M1": ("Доля релевантных в топ-10", "подбор"),
    "M2": ("nDCG@10", "подбор"),
    "M3": ("Подъём накрутчика", "подбор"),
    "M4": ("Калибровка вероятностей", "подбор"),
    "M5": ("Перекос по защищённым признакам", "подбор"),
    "M6": ("Перегрев", "подбор"),
    "M7": ("Модель принятия", "подбор"),
    "M8": ("Верность объяснений", "подбор"),
    "M9": ("Стабильность грейда", "тестирование-и-категоризация"),
    "M10": ("Совпадение грейда с истиной", "тестирование-и-категоризация"),
    "M11": ("Дискриминативность семейств", "тестирование-и-категоризация"),
    "M12": ("Сходимость калибровки", "тестирование-и-категоризация"),
    "M13": ("Эффективность адаптивности", "тестирование-и-категоризация"),
    "M14": ("Атака утечкой", "защита"),
    "M15": ("Детектор утечки", "защита"),
    "M16": ("LLM-помощник", "защита"),
    "M17": ("Проверочный блок у честных", "защита"),
    "M18": ("Инъекции в резюме", "защита"),
    "M19": ("Сдвиг генератора", "обобщение-и-согласие-с-людьми"),
    "M20": ("Согласие с людьми", "обобщение-и-согласие-с-людьми"),
    "M21": ("Согласие семейств с моделью и разбор потребности", "тестирование-и-категоризация"),
    "M22": ("Согласие попытки с моделью и разбор резюме", "защита"),
    "M23": ("Скорость подборки", "разбор-текстов-и-скорость"),
}
# Чего не хватает метрикам, которые этот прогон не считает.
PENDING: dict[str, str] = {
    "M6": "нет файла модели принятия: стратегии B нечем упорядочить выдачу",
    "M7": "нет файла модели принятия: `uv run python -m validation acceptance`",
    "M8": "нет проверки вкладов объяснений на выдачах стенда",
    "M14": "прогон без экспериментов защиты",
    "M15": "прогон без экспериментов защиты",
    "M16": "прогон без экспериментов защиты",
    "M17": "прогон без экспериментов защиты",
    "M18": "нет набора D6",
    "M22": "нет прогона l_z попытки; разбор резюме — нет набора D6",
    "M23": "нет замера времени подборки на 1000 кандидатах",
}

PASSED = "выполнен"
FAILED = "не выполнен"
WAITING = "ожидает данных"


@dataclass(frozen=True)
class B3Run:
    """Чем и когда отвечала B3 на этом наборе — из кэша ответов."""

    model: str | None
    first: str | None
    last: str | None
    answers: int


@dataclass(frozen=True)
class DatasetRuns:
    """Набор и всё, что по нему записала платформа: κ из конфига и κ = 1 (до поправки)."""

    dataset: Dataset
    runs: dict[str, SpecRun]
    before: dict[str, SpecRun]
    cold: dict[str, Adaptivity]
    # (потребность, кандидат) → эталон из истины.
    pairs: dict[tuple[uuid.UUID, uuid.UUID], Pair]
    # M21 — банк с испорченными семействами; только у набора, на котором его считает план.
    fit: dict[str, ItemFit] = field(default_factory=dict)
    # Отложенные пары модели принятия (M7) с решениями кандидатов.
    offers: tuple[Offer, ...] = ()
    # Эксперименты защиты по специализациям (M14–M17); пусто — прогон без них.
    protection: dict[str, ProtectionRun] = field(default_factory=dict)

    twins: tuple[Twin, ...] = ()
    # Базовая линия → (потребность, кандидат или двойник) → скор. Базовой линии без данных
    # здесь нет.
    scores: dict[str, dict[tuple[uuid.UUID, uuid.UUID], float]] = field(default_factory=dict)
    b3: B3Run | None = None

    def truth(self) -> dict[uuid.UUID, CandidateTruth]:
        return {t.id: t for t in self.dataset.truths}


@dataclass(frozen=True)
class Runs:
    mechanics: Mechanics
    catalog: Catalog
    scale: Scale
    specializations: tuple[str, ...]
    sets: dict[str, DatasetRuns]
    protection_scale: ProtectionScale = PLAN_PROTECTION
    # Честный поток детектора на D3 по специализациям — подбор `drift_cusum_h` (M15).
    tuning: dict[str, ProtectionRun] = field(default_factory=dict)
    # Посчитанные разделы — `computed`.
    memo: dict[str, "Section"] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class Section:
    metric: str
    body: str
    verdict: str
    # Картинки раздела: имя файла в каталоге картинок → содержимое.
    figures: dict[str, str] = field(default_factory=dict)
    # Вердикт по набору — `PASSED`, `FAILED` или `WAITING`: по нему M19 судит о D2.
    sets: dict[str, str] = field(default_factory=dict)


SECTIONS: dict[str, Callable[[Runs], Section]] = {}


def section(metric: str) -> Callable[[Callable[[Runs], Section]], Callable[[Runs], Section]]:
    """Регистрирует раздел метрики `metric`; метрика без раздела — «ожидает данных»."""

    def register(build: Callable[[Runs], Section]) -> Callable[[Runs], Section]:
        SECTIONS[metric] = build
        return build

    return register


def order(metrics: Iterable[str]) -> list[str]:
    """M9 и M10 первыми, дальше — по номерам плана."""
    first = ("M9", "M10")
    rest = sorted((m for m in metrics if m not in first), key=lambda m: int(m[1:]))
    return [m for m in first if m in metrics] + rest


# --- Прогон ------------------------------------------------------------------------------------


def collect(
    mechanics: Mechanics,
    scale: Scale = PLAN_SCALE,
    *,
    sets: Sequence[str] = SETS,
    specializations: Sequence[str] | None = None,
    workers: int | None = None,
    baselines: BaselineSource | None = None,
    protection: ProtectionScale | None = PLAN_PROTECTION,
    llm: Recording | None = None,
) -> Runs:
    """Задачи прогона в пуле процессов; результат от числа процессов не зависит: каждая задача
    собирает свой стенд из сида набора. `protection` — масштаб экспериментов защиты, None — без
    них; `llm` — запись ответов модели для D7."""
    known = catalog()
    codes = tuple(specializations or known.specializations)
    before = mechanics.model_copy(update={"level_sd_inflation": 1.0})
    generated: dict[str, Dataset] = {}
    doubles: dict[str, tuple[Twin, ...]] = {}
    offered: dict[str, list[SyntheticNeed]] = {}
    futures: dict[
        tuple[str, str, str],
        Future[SpecRun] | Future[Adaptivity] | Future[ItemFit] | Future[ProtectionRun],
    ] = {}
    with ProcessPoolExecutor(workers or max(1, (os.cpu_count() or 2) - 1)) as pool:
        for name in sets:
            generator, dataset, doubles[name] = prepared(name, mechanics, scale, codes, known)
            generated[name] = dataset
            offered[name] = offer_needs(generator, dataset, HOLDOUT_PAIRS)
            stacks = {o.id: frozenset(o.stack) for o in dataset.observed}
            employer_needs = Counter(n.employer for n in dataset.needs)
            for code in codes:
                job = Job(
                    DATASETS[name],
                    code,
                    mechanics,
                    scale,
                    tuple(t for t in dataset.truths if t.specialization == code),
                    tuple(n for n in dataset.needs if n.form.specialization == code),
                    stacks,
                    twins=tuple(tw for tw in doubles[name] if tw.observed.specialization == code),
                    offer_needs=tuple(n for n in offered[name] if n.form.specialization == code),
                    market=MarketInput(
                        DATASETS[name],
                        tuple(n for n in dataset.needs if n.form.specialization == code),
                        dataset.employers,
                        employer_needs,
                        {o.id: o for o in dataset.observed if o.specialization == code},
                        {t.id: t for t in dataset.truths if t.specialization == code},
                    ),
                )
                futures[name, code, "runs"] = pool.submit(run_spec, job)
                light = replace(job, mechanics=before, full=False, offer_needs=(), market=None)
                futures[name, code, "before"] = pool.submit(run_spec, light)
                futures[name, code, "cold"] = pool.submit(run_cold, job)
                if name in FIT_SETS:
                    futures[name, code, "fit"] = pool.submit(run_fit, job)
                if protection is not None:
                    futures[name, code, "protection"] = pool.submit(
                        run_protection,
                        ProtectionJob(
                            DATASETS[name],
                            code,
                            mechanics,
                            protection,
                            tuple(t for t in job.truths if t.persona == Persona.llm_helper),
                            llm_answers=dict(llm.answers) if llm and name == "d1" else None,
                            llm_model=llm.model if llm else None,
                        ),
                    )
        if protection is not None:
            for code in codes:
                futures["d3", code, "tuning"] = pool.submit(
                    run_protection,
                    ProtectionJob(D3, code, mechanics, protection, full=False),
                )
        done = {key: f.result() for key, f in futures.items()}

    def part(name: str, kind: str) -> dict:  # type: ignore[type-arg]
        return {code: done[name, code, kind] for code in codes}

    found = {}
    for name in sets:
        dataset = generated[name]
        pairs = {
            (p.need, p.candidate): p for p in label(dataset.truths, dataset.needs, known, mechanics)
        }
        runs_ = part(name, "runs")
        scored = {need: s for run in runs_.values() for need, s in run.offers.items()}
        needs = [n for n in offered[name] if n.form.specialization in codes]
        data = DatasetRuns(
            dataset,
            runs_,
            part(name, "before"),
            part(name, "cold"),
            pairs,
            protection=part(name, "protection") if protection is not None else {},
            fit=part(name, "fit") if name in FIT_SETS else {},
            twins=doubles[name],
            offers=tuple(make_offers(dataset, needs, scored, mechanics, HOLDOUT_PAIRS)),
        )
        if baselines is not None:
            data = score_baselines(data, known, baselines)
        found[name] = data
    tuning = {code: done["d3", code, "tuning"] for code in codes} if protection else {}
    return Runs(
        mechanics,
        known,
        scale,
        codes,
        found,
        protection or PLAN_PROTECTION,
        tuning,  # type: ignore[arg-type]
    )


def prepared(
    name: str, mechanics: Mechanics, scale: Scale, codes: Sequence[str], known: Catalog
) -> tuple[Generator, Dataset, tuple[Twin, ...]]:
    """Набор `name` в масштабе прогона — только специализации `codes`, — его генератор и
    двойники."""
    params = DATASETS[name]
    if scale.candidates is not None:
        params = replace(params, candidates_per_specialization=scale.candidates)
    generator = Generator(params, mechanics, known)
    dataset = generator.generate()
    dataset = replace(
        dataset,
        observed=tuple(o for o in dataset.observed if o.specialization in codes),
        truths=tuple(t for t in dataset.truths if t.specialization in codes),
        needs=tuple(n for n in dataset.needs if n.form.specialization in codes),
    )
    return generator, dataset, twins(dataset, known)


def baseline_pairs(
    dataset: Dataset, doubles: Sequence[Twin], catalog_: Catalog
) -> dict[str, list[tuple[uuid.UUID, uuid.UUID, Document, Document]]]:
    """По специализации — пары, которые ранжируют базовые линии: весь пул каждой потребности,
    двойники M3 — со своей потребностью, двойники M5 — с каждой потребностью специализации."""
    resumes = {o.id: Document(str(o.id), resume_text(o)) for o in dataset.observed}
    resumes |= {tw.id: Document(str(tw.id), resume_text(tw.observed)) for tw in doubles}
    pool: dict[str, list[uuid.UUID]] = {}
    for o in dataset.observed:
        pool.setdefault(o.specialization, []).append(o.id)
    found: dict[str, list[tuple[uuid.UUID, uuid.UUID, Document, Document]]] = {}
    for need in dataset.needs:
        code = need.form.specialization
        doc = Document(str(need.id), need_text(need.form, catalog_))
        members = [
            *sorted(pool.get(code, [])),
            *(
                tw.id
                for tw in doubles
                if tw.observed.specialization == code and tw.need in (None, need.id)
            ),
        ]
        found.setdefault(code, []).extend((need.id, c, doc, resumes[c]) for c in members)
    return found


def score_baselines(data: DatasetRuns, catalog_: Catalog, source: BaselineSource) -> DatasetRuns:
    """Скоры B1–B3 по парам `baseline_pairs`; базовая линия, у которой нет данных, источником не
    отдаётся. Корпус BM25 — резюме пула специализации без двойников."""
    corpus: dict[str, list[str]] = {}
    for o in data.dataset.observed:
        corpus.setdefault(o.specialization, []).append(resume_text(o))
    scores: dict[str, dict[tuple[uuid.UUID, uuid.UUID], float]] = {}
    b3: B3Run | None = None
    for code, pairs in sorted(baseline_pairs(data.dataset, data.twins, catalog_).items()):
        for ranker in source(data.dataset.params.name, data.dataset.params.seed, corpus[code]):
            prepare = getattr(ranker, "prepare", None)
            if prepare is not None:
                prepare(
                    {QUERY + n.text for _, _, n, _ in pairs}
                    | {PASSAGE + r.text for _, _, _, r in pairs}
                )
            own = scores.setdefault(ranker.name, {})
            for need, candidate, n, r in pairs:
                own[need, candidate] = ranker.score(n, r)
            if isinstance(ranker, LlmRanker):
                cache = ranker.cache
                b3 = B3Run(cache.model, cache.first, cache.last, len(cache.answers))
    return replace(data, scores=scores, b3=b3)


# --- Общие расчёты -----------------------------------------------------------------------------


def _grades(mechanics: Mechanics) -> list[str | None]:
    return [None, *grades_by_threshold(mechanics.grade_thresholds)]


def _rank(mechanics: Mechanics) -> dict[str | None, int]:
    return {g: i for i, g in enumerate(_grades(mechanics))}


def true_overall(truth: CandidateTruth, runs: Runs) -> float:
    """θ̄* — с весами тем оценки."""
    topics = [t.code for t in runs.catalog.specializations[truth.specialization].topics]
    prior = specialization_prior(topics, runs.mechanics)
    return sum(w * truth.level[t] for t, w in zip(prior.topics, prior.weights, strict=True))


def naive_grade(proportion: float, cutoffs: dict[str, float], mechanics: Mechanics) -> str | None:
    """B0: старший грейд, чья отсечка доли верных пройдена; ни одной — без категории."""
    passed = [
        g for g in grades_by_threshold(mechanics.grade_thresholds) if proportion >= cutoffs[g]
    ]
    return passed[-1] if passed else None


def outcomes(
    data: DatasetRuns, *, before: bool = False
) -> Iterable[tuple[SpecRun, uuid.UUID, Outcome]]:
    for run in (data.before if before else data.runs).values():
        for cid, outcome in run.outcomes.items():
            yield run, cid, outcome


def f(x: float | None, digits: int = 3) -> str:
    """Число отчёта: десятичная запятая, nan и нет значения — прочерк."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{digits}f}".replace(".", ",").replace("-", "−")


def mark(ok: bool | None) -> str:
    return "—" if ok is None else ("да" if ok else "нет")


def verdict_of(checks: Iterable[bool]) -> str:
    """Сравнение с nan ложно: часть без данных порог не проходит."""
    return PASSED if all(checks) else FAILED


def mean(values: Iterable[float]) -> float:
    """Среднее без nan; нет значений — nan."""
    kept = [v for v in values if not math.isnan(v)]
    return statistics.fmean(kept) if kept else math.nan


def spread(values: Sequence[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else math.nan


def judged(
    metric: str,
    body: str,
    sets: dict[str, str],
    figures: dict[str, str] | None = None,
    text: dict[str, str] | None = None,
) -> Section:
    """Раздел с вердиктом по каждому набору; `text` — вердикт словами, когда он подробнее."""
    verdict = "; ".join(f"{name.upper()} — {v}" for name, v in (text or sets).items())
    return Section(metric, body, verdict, figures or {}, sets)


def table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


# --- M9, M10 -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Repeat:
    agreement: float
    kappa: float
    correlation: float
    within_one: float
    pairs: int


def repeat(
    results: Sequence[tuple[str | None, str | None]],
    levels: Sequence[tuple[float, float]],
    mechanics: Mechanics,
) -> Repeat:
    rank = _rank(mechanics)
    n = len(results)
    return Repeat(
        agreement=sum(a == b for a, b in results) / n,
        kappa=cohen_kappa(results, _grades(mechanics)),
        correlation=pearson([a for a, _ in levels], [b for _, b in levels]),
        within_one=sum(abs(rank[a] - rank[b]) <= 1 for a, b in results) / n,
        pairs=n,
    )


def stability(data: DatasetRuns, mechanics: Mechanics) -> tuple[Repeat, Repeat]:
    """M9 нашего теста и B0 на парах повторного прохождения."""
    ours_r, ours_l, naive_r, naive_l = [], [], [], []
    for run, _, o in outcomes(data):
        if o.second is None:
            continue
        ours_r.append((o.first.grade, o.second.grade))
        ours_l.append((o.first.overall.mean, o.second.overall.mean))
        one, two = o.naive
        naive_r.append(
            (
                naive_grade(one, run.naive_cutoffs, mechanics),
                naive_grade(two, run.naive_cutoffs, mechanics),
            )
        )
        naive_l.append((one, two))
    return repeat(ours_r, ours_l, mechanics), repeat(naive_r, naive_l, mechanics)


M9_ROWS = (
    ("r(θ̄₁, θ̄₂)", "correlation", 0.85),
    ("Совпадение категорий", "agreement", 0.65),
    ("Каппа Коэна", "kappa", 0.55),
    ("Разница не больше грейда", "within_one", 0.99),
)


@section("M9")
def m9(runs: Runs) -> Section:
    found = {name: stability(data, runs.mechanics) for name, data in runs.sets.items()}
    rows, verdicts = [], {}
    for label_, attr, threshold in M9_ROWS:
        row = [label_, f"≥ {f(threshold, 2)}"]
        for ours, naive in found.values():
            row += [f(getattr(ours, attr)), f(getattr(naive, attr))]
        rows.append(row)
    for name, (ours, _) in found.items():
        verdicts[name] = verdict_of(getattr(ours, a) >= t for _, a, t in M9_ROWS)
    header = ["Показатель", "Порог"]
    for name in found:
        header += [f"{name.upper()}", f"B0 {name.upper()}"]
    pairs = ", ".join(f"{name.upper()} — {ours.pairs}" for name, (ours, _) in found.items())
    body = (
        f"Честные кандидаты проходят первичное определение дважды, с независимыми экземплярами "
        f"и шумом ответа; пар: {pairs}. Категория «без категории» — тоже категория. B0 — наивный "
        "тест: общий фиксированный бланк из `test_max_items` семейств, доля верных и грейд по "
        "отсечкам доли верных (отсечка грейда — ожидаемая доля верных на его пороге по экспертным "
        "параметрам бланка); r для B0 — между долями верных. Заявленный грейд при повторе не "
        "меняется — его стабильность 1 по построению и о тесте ничего не говорит.\n\n"
        + table(header, rows)
    )
    return judged("M9", body, verdicts)


@dataclass(frozen=True)
class Truthfulness:
    exact: float
    over: float
    under: float
    within_one: float
    # Точное совпадение среди заявивших грейд не ниже истинного.
    exact_claimed: float
    n: int


def truthfulness(
    pairs: Sequence[tuple[str | None, str | None, str]], mechanics: Mechanics
) -> Truthfulness:
    """Пары (истинный, присвоенный, заявленный)."""
    rank = _rank(mechanics)
    n = len(pairs)
    claimed_ok = [(t, a) for t, a, c in pairs if rank[c] >= rank[t]]
    return Truthfulness(
        exact=sum(rank[a] == rank[t] for t, a, _ in pairs) / n,
        over=sum(rank[a] > rank[t] for t, a, _ in pairs) / n,
        under=sum(rank[a] < rank[t] for t, a, _ in pairs) / n,
        within_one=sum(abs(rank[a] - rank[t]) <= 1 for t, a, _ in pairs) / n,
        exact_claimed=sum(rank[a] == rank[t] for t, a in claimed_ok) / len(claimed_ok)
        if claimed_ok
        else math.nan,
        n=n,
    )


def honest_grades(
    data: DatasetRuns, mechanics: Mechanics
) -> dict[str, list[tuple[str | None, str | None, str]]]:
    """Честные кандидаты: (истинный, присвоенный, заявленный) у теста, B0 и заявки."""
    truth = data.truth()
    found: dict[str, list[tuple[str | None, str | None, str]]] = {
        "ours": [],
        "naive": [],
        "claimed": [],
    }
    for run, cid, o in outcomes(data):
        t = truth[cid]
        if t.persona != Persona.honest:
            continue
        found["ours"].append((t.grade, o.first.grade, t.claimed))
        found["naive"].append(
            (t.grade, naive_grade(o.naive[0], run.naive_cutoffs, mechanics), t.claimed)
        )
        found["claimed"].append((t.grade, t.claimed, t.claimed))
    return found


def matrix(rows: Sequence[tuple[str | None, str | None, str]], runs: Runs) -> str:
    grades = _grades(runs.mechanics)
    counts = Counter((t, a) for t, a, _ in rows)

    def name(g: str | None, none: str) -> str:
        return runs.catalog.grades[g].name if g else none

    header = ["Истинный \\ присвоенный", *(name(g, "без категории") for g in grades), "Всего"]
    body = []
    for t in grades:
        cells = [counts[t, a] for a in grades]
        body.append(
            [name(t, "ниже стажёра")]
            + [f"**{c}**" if a == t else str(c) for a, c in zip(grades, cells, strict=True)]
            + [str(sum(cells))]
        )
    return table(header, body)


@section("M10")
def m10(runs: Runs) -> Section:
    found = {
        name: {
            k: truthfulness(v, runs.mechanics)
            for k, v in honest_grades(data, runs.mechanics).items()
        }
        for name, data in runs.sets.items()
    }
    spec = (
        ("Завышение", "over", "≤ 0,05 и ≤ ½ завышения B0"),
        ("Не дальше одного грейда", "within_one", "≥ 0,98"),
        ("Точное совпадение", "exact", "≥ 0,55"),
        ("Точное среди заявивших не ниже истинного", "exact_claimed", "≥ 0,60"),
        ("Занижение", "under", "—"),
    )
    header = ["Показатель", "Порог"]
    for name in found:
        header += [name.upper(), f"B0 {name.upper()}", f"Заявка {name.upper()}"]
    rows = []
    for label_, attr, threshold in spec:
        row = [label_, threshold]
        for by in found.values():
            row += [f(getattr(by[k], attr)) for k in ("ours", "naive", "claimed")]
        rows.append(row)
    verdicts = {}
    for name, by in found.items():
        ours, naive = by["ours"], by["naive"]
        verdicts[name] = verdict_of(
            [
                ours.over <= 0.05 and ours.over <= naive.over / 2,
                ours.within_one >= 0.98,
                ours.exact >= 0.55,
                ours.exact_claimed >= 0.60,
            ]
        )
    matrices = "\n\n".join(
        f"**Матрица «истинный грейд × присвоенный», {name.upper()}** — честные кандидаты, "
        f"{len(grades['ours'])}; на диагонали — точное совпадение.\n\n"
        + matrix(grades["ours"], runs)
        for name, data in runs.sets.items()
        for grades in [honest_grades(data, runs.mechanics)]
    )
    body = (
        "Истинный грейд — полоса θ̄* = Σ w_t θ*_t; присвоенный — итог первичного определения "
        "честного кандидата набора, тест на заявленный грейд и каскад вниз. B0 — тот же наивный "
        "тест, что в M9; «заявка» — грейд, который кандидат заявил сам.\n\n"
        + matrices
        + "\n\n"
        + table(header, rows)
    )
    return judged("M10", body, verdicts)


# --- M1, M2 ------------------------------------------------------------------------------------


# Порядок блоков нашей выдачи; вне выдачи — после всех.
BLOCK_RANK = {"exact": 0, "nearby": 1, "unconfirmed": 2}
OURS = "ours"
NAIVE = "B0"


def ranked_lists(
    data: DatasetRuns, method: str = OURS, *, within: bool = False
) -> Iterable[tuple[str, uuid.UUID, list[uuid.UUID], list[uuid.UUID]]]:
    """По потребности: пул в порядке ранжирования и пул по id.

    Наша выдача — точная категория, близкие, нижний блок, затем остальные пула по id; B0 — весь
    пул по доле верных наивного теста; B1–B3 — весь пул по своему скору, а `within` — внутри
    блоков нашей выдачи (точные, близкие, нижний блок, остальные). Ничьи — по id."""
    scores = data.scores.get(method, {})
    for run in data.runs.values():
        pool = sorted(run.outcomes)
        for need, rows in run.placed.items():
            if method == OURS:
                listed = {p.candidate for p in rows}
                ranked = [*(p.candidate for p in rows), *(c for c in pool if c not in listed)]
            elif method == NAIVE:
                ranked = sorted(pool, key=lambda c: (-run.outcomes[c].naive[0], c))
            elif within:
                block = {p.candidate: BLOCK_RANK[p.block] for p in rows}
                ranked = sorted(
                    pool, key=lambda c: (block.get(c, len(BLOCK_RANK)), -scores[need, c], c)
                )
            else:
                ranked = sorted(pool, key=lambda c: (-scores[need, c], c))
            yield run.specialization, need, ranked, pool


@dataclass(frozen=True)
class Ranking:
    precision: float
    ndcg: float


def ranking_quality(
    data: DatasetRuns,
    specialization: str | None = None,
    method: str = OURS,
    *,
    within: bool = False,
) -> Ranking | None:
    """M1 и M2 ранжирования `method`; базовой линии без данных — None."""
    if method not in (OURS, NAIVE) and method not in data.scores:
        return None
    lists = [
        (
            [data.pairs[need, c].grade for c in ranked],
            [data.pairs[need, c].grade for c in pool],
        )
        for code, need, ranked, pool in ranked_lists(data, method, within=within)
        if specialization in (None, code)
    ]
    return Ranking(
        mean(precision_at(r, TOP) for r, _ in lists),
        mean(ndcg_at(r, p, TOP) for r, p in lists),
    )


def quality(
    data: DatasetRuns,
    attr: str,
    specialization: str | None = None,
    method: str = OURS,
    *,
    within: bool = False,
) -> float | None:
    """Показатель `attr` ранжирования — `precision` или `ndcg`."""
    found = ranking_quality(data, specialization, method, within=within)
    return None if found is None else float(getattr(found, attr))


def comparison(
    ours: float, found: dict[str, float | None], threshold: float, margin: float, lower: bool
) -> tuple[str, str]:
    """Вердикт порога «абсолютная часть и сравнение с лучшей из B1–B3» и он словами. `lower` —
    меньше лучше: сравнительная часть — не выше доли лучшей базовой линии; иначе — не ниже
    лучшей плюс запас. Сравнение уже не выполнено на имеющихся базовых линиях — «не выполнен»,
    хоть одной нет — «ожидает данных»."""
    have = {k: v for k, v in found.items() if v is not None and not math.isnan(v)}
    absolute = ours <= threshold if lower else ours >= threshold
    if have:
        best_name, best = (min if lower else max)(have.items(), key=lambda kv: kv[1])
        bound = best * margin if lower else best + margin
        relative: bool | None = ours <= bound if lower else ours >= bound
        against = f"лучшая — {best_name}, {f(best)}, граница {f(bound)}"
    else:
        relative, against = None, "базовых линий нет"
    missing = [k for k in found if k not in have]
    parts = f"абсолютная часть {'выполнена' if absolute else 'не выполнена'}"
    if relative is False or not absolute:
        rel_text = "не выполнена" if relative is False else "выполнена" if relative else WAITING
        return FAILED, f"{parts}, сравнительная — {rel_text} ({against})"
    if missing:
        return WAITING, (
            f"{parts}, сравнительная — {WAITING}: нет {', '.join(missing)}; по имеющимся — "
            f"{'выполнена' if relative else WAITING} ({against})"
        )
    return PASSED, f"{parts}, сравнительная — выполнена ({against})"


def _ranking_section(
    runs: Runs, metric: str, attr: str, threshold: float, margin: float
) -> Section:
    methods = (OURS, NAIVE, *BASELINES)
    names = {OURS: "Наша", NAIVE: "B0"}
    header = ["Специализация"]
    for name in runs.sets:
        header += [f"{names.get(m, m)} {name.upper()}" for m in methods]
    rows = []
    for code in (*runs.specializations, None):
        row = [runs.catalog.specializations[code].name if code else "**Все потребности**"]
        for data in runs.sets.values():
            row += [f(quality(data, attr, code, m)) for m in methods]
        rows.append(row)
    within_header = ["Базовая линия"]
    for name in runs.sets:
        within_header += [f"Весь пул {name.upper()}", f"В наших блоках {name.upper()}"]
    within_rows = []
    for m in BASELINES:
        row = [m]
        for data in runs.sets.values():
            row += [f(quality(data, attr, None, m)), f(quality(data, attr, None, m, within=True))]
        within_rows.append(row)
    verdicts, text = {}, {}
    for name, data in runs.sets.items():
        ours = quality(data, attr)
        assert ours is not None
        found = {m: quality(data, attr, None, m) for m in BASELINES}
        verdicts[name], text[name] = comparison(ours, found, threshold, margin, lower=False)
    needs = sum(len(r.placed) for r in next(iter(runs.sets.values())).runs.values())
    body = (
        f"Порог: не ниже {f(threshold, 2)} и не ниже лучшей из B1–B3 плюс {f(margin, 2)}. Выдача "
        "— подборка платформы по потребности набора: точная категория по скору, затем «близкие» "
        "и нижний блок, затем остальные кандидаты пула. Пул потребности — все кандидаты набора "
        "её специализации, включая персонажей-атакующих; эталон — градация rel из истины. "
        f"Потребностей в наборе: {needs}. B0 ранжирует весь пул по доле верных наивного теста — "
        "для ориентира, в порог не входит. B1–B3 ранжируют весь пул по тексту резюме (раздел "
        "«Базовые линии» выше); прочерк — базовой линии на наборе нет.\n\n"
        + table(header, rows)
        + "\n\n**Вклад отсечения и скора.** Те же B1–B3 внутри блоков нашей выдачи: порядок "
        "блоков — наш (точные, близкие, нижний блок, остальные), внутри блока — скор базовой "
        "линии. Рост против всего пула — вклад отсечения по категории, разница с нашей выдачей — "
        "вклад нашего скора внутри блока. Все потребности.\n\n"
        + table(within_header, within_rows)
        + naive_note(runs, attr)
    )
    return judged(metric, body, verdicts, text=text)


def underestimate(data: DatasetRuns, mechanics: Mechanics) -> float:
    return truthfulness(honest_grades(data, mechanics)["ours"], mechanics).under


def naive_note(runs: Runs, attr: str) -> str:
    """Разбор, когда B0 ранжирует лучше нашей выдачи: на каких наборах и сколько занижает грейд
    правило уверенности (M10)."""
    worse = [
        name
        for name, data in runs.sets.items()
        if (quality(data, attr, None, NAIVE) or 0) > (quality(data, attr) or 0)
    ]
    if not worse:
        return ""
    under = ", ".join(
        f"{name.upper()} — {f(underestimate(data, runs.mechanics), 2)}"
        for name, data in runs.sets.items()
        if name in worse
    )
    return (
        f"\n\n**B0 выше нашей выдачи** на {', '.join(n.upper() for n in worse)} — отрицательный "
        "результат. Выдача сначала отсекает по категории, а категорию правило уверенности "
        f"присваивает консервативно: доля честных с заниженным грейдом (M10): {under}. Кандидат, "
        "чей истинный уровень выше требования, но категория ниже грейда потребности, попадает в "
        "«близкие» под всех точных, а B0 ставит его по доле верных без отсечения. Похоже, это "
        "цена отсечения по категории при консервативном грейде, а не скора внутри категории — "
        "вклад отсечения и скора разделяет таблица B1–B3 в наших блоках выше."
    )


@section("M1")
def m1(runs: Runs) -> Section:
    return _ranking_section(runs, "M1", "precision", 0.70, 0.15)


@section("M2")
def m2(runs: Runs) -> Section:
    return _ranking_section(runs, "M2", "ndcg", 0.75, 0.10)


# --- M3, M5 ------------------------------------------------------------------------------------


def place_keys(rows: Sequence[Placed]) -> dict[uuid.UUID, float]:
    """Ключ места в нашей выдаче: выше — больше; вне выдачи ключа нет — ниже всех."""
    return {p.candidate: float(len(rows) - i) for i, p in enumerate(rows)}


def keys_of(
    data: DatasetRuns, method: str, need: uuid.UUID, rows: Sequence[Placed]
) -> Callable[[uuid.UUID], float]:
    if method == OURS:
        ours = place_keys(rows)
        return lambda c: ours.get(c, -math.inf)
    scores = data.scores[method]
    return lambda c: scores[need, c]


class Places:
    """Процентильное место в пуле: 100 · (ниже + ½ · вровень) / (пул − 1) — 0–100, больше —
    выше. Сам кандидат, которого заменяет двойник, в счёт не идёт."""

    def __init__(self, keys: Iterable[float]) -> None:
        self.keys = sorted(keys)

    def of(self, value: float, replaced: float) -> float:
        lower = bisect.bisect_left(self.keys, value)
        equal = bisect.bisect_right(self.keys, value) - lower
        if replaced < value:
            lower -= 1
        elif replaced == value:
            equal -= 1
        others = len(self.keys) - 1
        return 100 * (lower + equal / 2) / others if others > 0 else math.nan


def methods_of(data: DatasetRuns, *baselines: str) -> list[str]:
    return [OURS, *(m for m in baselines if m in data.scores)]


@dataclass(frozen=True)
class Lift:
    # Ранжирование → Δ процентильного места двойника против кандидата по парам.
    deltas: dict[str, list[float]]
    # S двойника − S кандидата — в парах, где скор есть у обоих.
    gains: list[float]
    # Пар, где двойник в точной категории, а кандидат — нет.
    promoted: int
    pairs: int


def lift(data: DatasetRuns) -> Lift:
    """M3: пара — потребность и честный кандидат, двойник дописал под неё резюме."""
    by_need: dict[uuid.UUID, list[Twin]] = {}
    for tw in data.twins:
        if tw.kind == TwinKind.inflated and tw.need is not None:
            by_need.setdefault(tw.need, []).append(tw)
    methods = methods_of(data, *BASELINES)
    deltas: dict[str, list[float]] = {m: [] for m in methods}
    gains: list[float] = []
    promoted = pairs = 0
    exact = SelectionBlock.exact.value
    for run in data.runs.values():
        pool = sorted(run.outcomes)
        for need, rows in run.twin_placed.items():
            own = by_need.get(need, [])
            for m in methods:
                key = keys_of(data, m, need, rows)
                places = Places(key(c) for c in pool)
                for tw in own:
                    source = key(tw.source)
                    deltas[m].append(places.of(key(tw.id), source) - places.of(source, source))
            placed = {p.candidate: p for p in rows}
            for tw in own:
                pairs += 1
                a, b = placed.get(tw.source), placed.get(tw.id)
                if a and b and a.score is not None and b.score is not None:
                    gains.append(b.score - a.score)
                promoted += bool(b and b.block == exact) and not (a and a.block == exact)
    return Lift(deltas, gains, promoted, pairs)


@section("M3")
def m3(runs: Runs) -> Section:
    cap = runs.mechanics.self_reported_stack_cap
    found = {name: lift(data) for name, data in runs.sets.items()}
    names = {OURS: "Наша выдача"}
    header = ["Ранжирование"]
    for name in found:
        header += [f"Медиана Δ {name.upper()}", f"p90 Δ {name.upper()}"]
    rows = []
    for m in (OURS, *BASELINES):
        row = [names.get(m, m)]
        for lf in found.values():
            values = lf.deltas.get(m) or []
            row += [f(median(values), 1) if values else "—", f(quantile(values, 0.9), 1)]
        rows.append(row)
    checks_header = ["Проверка нашей выдачи", *(name.upper() for name in found)]
    checks = [
        [f"Прирост S ≤ λ = {f(cap, 2)}, доля пар"]
        + [
            f(sum(g <= cap + 1e-9 for g in lf.gains) / len(lf.gains)) if lf.gains else "—"
            for lf in found.values()
        ],
        ["Пар со скором у обоих"] + [f"{len(lf.gains)} из {lf.pairs}" for lf in found.values()],
        ["Наибольший прирост S"] + [f(max(lf.gains, default=math.nan)) for lf in found.values()],
        ["Переходов в точную категорию"] + [str(lf.promoted) for lf in found.values()],
    ]
    verdicts, text = {}, {}
    for name, lf in found.items():
        ours = median(lf.deltas[OURS]) if lf.deltas[OURS] else math.nan
        medians = {m: median(lf.deltas[m]) if lf.deltas.get(m) else None for m in BASELINES}
        verdict, said = comparison(ours, medians, 5.0, 0.25, lower=True)
        capped = all(g <= cap + 1e-9 for g in lf.gains)
        if not capped or lf.promoted:
            broken = ([] if capped else ["прирост S выше λ"]) + (
                ["переход в точную категорию"] if lf.promoted else []
            )
            verdict, said = FAILED, f"{said}; не выполнено: {', '.join(broken)}"
        verdicts[name], text[name] = verdict, said
    panels = [
        (name.upper(), [(names.get(m, m), lf.deltas.get(m, [])) for m in (OURS, *BASELINES)])
        for name, lf in found.items()
    ]
    figure = "m3-lift.svg"
    pairs = ", ".join(f"{name.upper()} — {lf.pairs}" for name, lf in found.items())
    body = (
        "Порог: медиана Δ не выше 5 п. п. и не выше четверти наименьшей медианы среди B1–B3; "
        "прирост скора не больше λ = `self_reported_stack_cap` в 100 % пар; накрутчик не "
        "переходит в точную категорию ни в одной паре. Двойник честного кандидата дописал в "
        "самоописание и стек весь стек потребности и её название; тест, профиль и категория у "
        "него те же. Δ — изменение процентильного места в выдаче потребности, 0–100, больше — "
        "выше: место двойника среди остальных кандидатов пула против места самого кандидата. "
        f"Пар: {pairs} — по {M3_PER_NEED} честных кандидатов на потребность. Вне нашей выдачи "
        "кандидаты стоят вровень ниже всех.\n\n"
        + table(header, rows)
        + "\n\n"
        + table(checks_header, checks)
        + f"\n\n![M3, распределение Δ]({FIGURES}/{figure})"
    )
    svg = ecdf_svg("M3, распределение Δ процентильного места", panels, "Δ, п. п.")
    return judged("M3", body, verdicts, {figure: svg}, text)


# Признаки M5: название сравнения «группа / остальные» и кто в группе.
PROTECTED: tuple[tuple[str, Callable[[Person], bool]], ...] = (
    ("Пол: женщины / мужчины", lambda p: p.gender == Gender.female),
    ("Возраст: 35 лет и старше / младше", lambda p: p.older),
    ("Вуз: региональный / ведущий", lambda p: not p.leading),
)


@dataclass(frozen=True)
class Bias:
    # Доля пар «потребность — кандидат» с тем же блоком и тем же S у двойника.
    identical: float
    pairs: int
    # Ранжирование → признак → отношение долей в топ-10.
    ratios: dict[str, dict[str, float]]


def bias(data: DatasetRuns) -> Bias:
    """M5. Мир 0 — кандидаты выборки со своими признаками, мир 1 — вместо них двойники: каждый
    кандидат выборки показан один раз в каждой группе признака, и распределение истины у групп
    одно. Доля группы в топ-10 — сколько её показов попало в топ-10 потребности из всех её
    показов в пуле."""
    people = {o.id: o.person for o in data.dataset.observed}
    sample = [tw for tw in data.twins if tw.kind == TwinKind.protected]
    methods = methods_of(data, "B2", "B3")
    shown = {m: {a: Counter[bool]() for a, _ in PROTECTED} for m in methods}
    top = {m: {a: Counter[bool]() for a, _ in PROTECTED} for m in methods}
    same = pairs = 0
    for run in data.runs.values():
        pool = sorted(run.outcomes)
        own = [tw for tw in sample if tw.source in run.outcomes]
        for need, rows in run.twin_placed.items():
            placed = {p.candidate: p for p in rows}
            for tw in own:
                a, b = placed.get(tw.source), placed.get(tw.id)
                pairs += 1
                same += (a is None and b is None) or (
                    a is not None and b is not None and (a.block, a.score) == (b.block, b.score)
                )
            for m in methods:
                key = keys_of(data, m, need, rows)
                for world in (0, 1):
                    keys = {c: (-key(c), c) for c in pool}
                    person = {tw.source: people[tw.source] for tw in own}
                    if world:
                        for tw in own:
                            keys[tw.source] = (-key(tw.id), tw.id)
                            person[tw.source] = tw.observed.person
                    # Вне нашей выдачи кандидата в топ-10 нет, как бы ни легла ничья.
                    listed = [c for c in pool if keys[c][0] != math.inf]
                    best = set(heapq.nsmallest(TOP, listed, key=keys.__getitem__))
                    for source, p in person.items():
                        for attr, member in PROTECTED:
                            shown[m][attr][member(p)] += 1
                            top[m][attr][member(p)] += source in best
    ratios = {
        m: {attr: ratio(top[m][attr], shown[m][attr]) for attr, _ in PROTECTED} for m in methods
    }
    return Bias(same / pairs if pairs else math.nan, pairs, ratios)


def ratio(top: Counter[bool], shown: Counter[bool]) -> float:
    """Доля группы в топ-10 к доле остальных; без показов или попаданий остальных — nan."""
    if not (shown[True] and shown[False] and top[False]):
        return math.nan
    return (top[True] / shown[True]) / (top[False] / shown[False])


@section("M5")
def m5(runs: Runs) -> Section:
    found = {name: bias(data) for name, data in runs.sets.items()}
    names = {OURS: "Наша выдача"}
    columns = (OURS, "B2", "B3")
    header = ["Признак"]
    for name in found:
        header += [f"{names.get(m, m)} {name.upper()}" for m in columns]
    rows = []
    for attr, _ in PROTECTED:
        row = [attr]
        for b in found.values():
            row += [f(b.ratios[m][attr]) if m in b.ratios else "—" for m in columns]
        rows.append(row)
    identical = [
        "Тождественны S и блок, доля пар (пар всего)",
        *(f"{f(b.identical)} ({b.pairs})" for b in found.values()),
    ]
    verdicts, text = {}, {}
    for name, b in found.items():
        ours = list(b.ratios[OURS].values())
        outside = [r for r in ours if not math.isnan(r) and not 0.8 <= r <= 1.25]
        if b.identical < 1 or outside:
            verdicts[name] = FAILED
            text[name] = (
                f"{FAILED}: S тождественны в доле пар {f(b.identical)}, отношений вне 0,8–1,25 — "
                f"{len(outside)}"
            )
            continue
        verdicts[name] = WAITING
        unknown = any(math.isnan(r) for r in ours)
        text[name] = (
            "часть S выполнена"
            + (", отношение долей без данных у части признаков" if unknown else "")
            + f"; P(принятия) — {WAITING}"
        )
    samples = sum(tw.kind == TwinKind.protected for tw in next(iter(runs.sets.values())).twins)
    body = (
        "Порог: S и P(принятия) тождественны в 100 % пар; отношение долей в топ-10 — от 0,8 до "
        "1,25. Двойник отличается от кандидата только полом (по имени), группой возраста и вузом "
        f"в тексте резюме; кандидатов с двойниками — {samples} на набор, поровну по "
        "специализациям, пары — с каждой потребностью их специализации. Отношение долей — доля "
        "показов группы, попавших в топ-10, к той же доле остальных: каждый кандидат выборки "
        "показан один раз в каждой группе (мир с кандидатами и мир с двойниками), истина у групп "
        "одна. B2 и B3 — на тех же двойниках, в порог не входят. P(принятия) — "
        f"{WAITING}: модели принятия на стенде нет.\n\n"
        + table(["Показатель", *(n.upper() for n in found)], [identical])
        + "\n\n"
        + table(header, rows)
    )
    return judged("M5", body, verdicts, text=text)


# --- M4 ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Calibration:
    # (а) вероятности по темам: вся популяция и только честные.
    topics: tuple[list[float], list[float]]
    topics_honest: tuple[list[float], list[float]]
    # (б) уверенность грейда у честных.
    grade: tuple[list[float], list[float]]
    # (в) навыковая часть скора против M*.
    skill: tuple[list[float], list[float]]
    # z общего уровня честных на конце определения — по специализациям.
    z: dict[str, list[float]]


def calibration(data: DatasetRuns, runs: Runs, *, before: bool) -> Calibration:
    truth = data.truth()
    thresholds = runs.mechanics.grade_thresholds
    snaps: dict[str, list[tuple[uuid.UUID, NeedSnapshot]]] = {}
    for need in data.dataset.needs:
        snaps.setdefault(need.form.specialization, []).append(
            (need.id, snapshot(need, runs.catalog, runs.mechanics))
        )
    topics: tuple[list[float], list[float]] = ([], [])
    honest: tuple[list[float], list[float]] = ([], [])
    grade: tuple[list[float], list[float]] = ([], [])
    skill: tuple[list[float], list[float]] = ([], [])
    z: dict[str, list[float]] = {}
    levels = {
        code: sorted({s.topics[0].requirement for _, s in own}) for code, own in snaps.items()
    }
    for run, cid, o in outcomes(data, before=before):
        t = truth[cid]
        own = snaps[run.specialization]
        is_honest = t.persona == Persona.honest
        if is_honest:
            overall = true_overall(t, runs)
            z.setdefault(run.specialization, []).append(
                (o.first.overall.mean - overall) / o.first.overall.sd
            )
            if o.first.grade is not None:
                c = thresholds[o.first.grade]
                grade[0].append(o.first.overall.prob_at_least(c))
                grade[1].append(float(overall >= c))
        if not o.profile:
            continue
        for topic, level in sorted(o.profile.items()):
            for req in levels[run.specialization]:
                p, hit = level.prob_at_least(req), float(t.level[topic] >= req)
                topics[0].append(p)
                topics[1].append(hit)
                if is_honest:
                    honest[0].append(p)
                    honest[1].append(hit)
        for need_id, snap in own:
            if any(r.topic.code not in o.profile for r in snap.topics):
                continue
            skill[0].append(
                sum(
                    r.weight * o.profile[r.topic.code].prob_at_least(r.requirement)
                    for r in snap.topics
                )
            )
            skill[1].append(data.pairs[need_id, cid].share)
    return Calibration(topics, honest, grade, skill, z)


@section("M4")
def m4(runs: Runs) -> Section:
    kappa = runs.mechanics.level_sd_inflation
    figures, rows, z_rows, verdicts = {}, [], [], {}
    parts = (
        ("(а) вероятности по темам, все", "topics"),
        ("(а) только честные, описательно", "topics_honest"),
        ("(б) уверенность грейда, честные", "grade"),
        ("(в) навыковая часть скора против M*", "skill"),
    )
    found = {
        name: (calibration(data, runs, before=True), calibration(data, runs, before=False))
        for name, data in runs.sets.items()
    }
    for label_, attr in parts:
        row = [label_]
        for before, after in found.values():
            row += [f(ece(*getattr(before, attr))), f(ece(*getattr(after, attr)))]
        rows.append(row)
    for name, (before, after) in found.items():
        verdicts[name] = verdict_of(
            ece(*getattr(after, a)) <= 0.05 for a in ("topics", "grade", "skill")
        )
        panels = [
            Panel(
                title,
                "предсказано",
                "наблюдаемо",
                [
                    Series("κ = 1 — до поправки", reliability(*getattr(before, attr))),
                    Series(f"κ = {kappa} — после поправки", reliability(*getattr(after, attr))),
                ],
            )
            for title, attr in (
                ("(а) P(θ_t ≥ req_t)", "topics"),
                ("(б) P(θ̄ ≥ c_g) при присвоении", "grade"),
                ("(в) Σ v_t P против M*", "skill"),
            )
        ]
        figures[f"m4-reliability-{name}.svg"] = reliability_svg(
            f"M4, надёжностная диаграмма, {name.upper()}", panels
        )
    for code in runs.specializations:
        row = [runs.catalog.specializations[code].name]
        for before, after in found.values():
            row += [f(spread(before.z.get(code, []))), f(spread(after.z.get(code, [])))]
        z_rows.append(row)
    header = ["Часть"]
    off = [
        f"{name.upper()} {runs.catalog.specializations[code].name} "
        f"({f(spread(after.z.get(code, [])), 2)})"
        for name, (_, after) in found.items()
        for code in runs.specializations
        if not 0.9 <= spread(after.z.get(code, [])) <= 1.1
    ]
    outside = (
        f"С поправкой вне 0,9–1,1: {', '.join(off)}. Там погрешность общего уровня остаётся "
        "заниженной (sd(z) > 1 — вероятности грейдов и тем слишком уверенные) или завышенной."
        if off
        else "С поправкой sd(z) в пределах 0,9–1,1 у всех специализаций."
    )
    z_header = ["Специализация"]
    for name in found:
        header += [f"{name.upper()}, κ = 1", f"{name.upper()}, κ = {f(kappa, 2)}"]
        z_header += [f"{name.upper()}, κ = 1", f"{name.upper()}, κ = {f(kappa, 2)}"]
    images = "\n\n".join(
        f"![M4, надёжностная диаграмма, {name.upper()}]({FIGURES}/m4-reliability-{name}.svg)"
        for name in runs.sets
    )
    body = (
        f"ECE на 10 равных корзинах, порог — каждая из трёх частей не выше 0,05; вердикт — по κ из "
        f"`config/mechanics.yaml` ({f(kappa, 2)}), κ = 1 — та же механика без поправки "
        "погрешности, банк прогрет заново. (а) и (в) — по профилю навыков на всей популяции "
        "набора, включая персонажей-атакующих; требования — пороги грейдов потребностей набора. "
        "Профиль стенда — только тест: ФСП в профиль на стенде не подаётся. (б) — уверенность "
        "грейда при присвоении у честных кандидатов.\n\n"
        + table(header, rows)
        + "\n\n"
        + images
        + "\n\n**Честность погрешности общего уровня.** sd(z), z = (θ̂ − θ̄*) / σ̂ на конце "
        "определения у честных кандидатов; правило подбора κ ждёт 0,9–1,1 по каждой "
        "специализации.\n\n" + table(z_header, z_rows) + "\n\n" + outside
    )
    return judged("M4", body, verdicts, figures)


# --- M11 ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Discrimination:
    code: str
    specialization: str
    topic: str
    grade: str
    a: float
    r_pb: float

    def ok(self) -> bool:
        return self.a >= 0.5 and not math.isnan(self.r_pb) and self.r_pb >= 0.2


def discrimination(data: DatasetRuns) -> list[Discrimination]:
    """â_f — параметр семейства после прогрева банка; r_pb — по ответам честных кандидатов набора
    на экземпляр каждого семейства банка (наблюдаемое набора) против доли верных на остальных
    семействах банка: уровень, оценённый без этого семейства."""
    truth = data.truth()
    seen = {o.id: o for o in data.dataset.observed}
    found = []
    for run in data.runs.values():
        honest = [seen[c] for c in sorted(run.outcomes) if truth[c].persona == Persona.honest]
        totals = [sum(r.correct for r in o.answers.values()) for o in honest]
        size = len(run.families)
        for fam in (f_ for f_ in run.families if not f_.anchor):
            correct = [float(o.answers[fam.code].correct) for o in honest]
            rest = [(t - c) / (size - 1) for t, c in zip(totals, correct, strict=True)]
            found.append(
                Discrimination(
                    fam.code,
                    run.specialization,
                    fam.topic,
                    fam.grade,
                    fam.discrimination,
                    point_biserial(correct, rest),
                )
            )
    return found


@section("M11")
def m11(runs: Runs) -> Section:
    found = {name: discrimination(data) for name, data in runs.sets.items()}
    rows, verdicts = [], {}
    header = ["Специализация"]
    for name in found:
        header += [f"Семейств {name.upper()}", f"Прошли {name.upper()}"]
    for code in (*runs.specializations, None):
        row = [runs.catalog.specializations[code].name if code else "**Все**"]
        for items in found.values():
            own = [d for d in items if code in (None, d.specialization)]
            row += [str(len(own)), f(sum(d.ok() for d in own) / len(own))]
        rows.append(row)
    for name, items in found.items():
        verdicts[name] = verdict_of([sum(d.ok() for d in items) / len(items) >= 0.9])
    failing = []
    for name, items in found.items():
        bad = [d for d in items if not d.ok()]
        lines = (
            table(
                ["Семейство", "Тема", "Грейд", "â_f", "r_pb"],
                ([f"`{d.code}`", d.topic, d.grade, f(d.a, 2), f(d.r_pb, 2)] for d in bad),
            )
            if bad
            else "Нет."
        )
        failing.append(f"**Кандидаты на замену, {name.upper()}** — {len(bad)}.\n\n{lines}")
    body = (
        "Порог: не меньше 0,90 семейств с â_f ≥ 0,5 и r_pb ≥ 0,2; якорные семейства не "
        "считаются — их параметры известны и не оцениваются. â_f — разделяющая сила после "
        "прогрева банка на честных кандидатах набора; r_pb — точечно-бисериальная корреляция "
        "верности ответа с долей верных на остальных семействах банка у честных кандидатов "
        "набора: каждый из них ответил на экземпляр каждого семейства. На синтетике метрика "
        "проверяет конвейер и банк при допущениях симулятора; на живых ответах — D8.\n\n"
        + table(header, rows)
        + "\n\n"
        + "\n\n".join(failing)
    )
    return judged("M11", body, verdicts)


# --- M12, M13 ----------------------------------------------------------------------------------


def residual_summary(data: DatasetRuns) -> str:
    """Итог разбора остатка M12 на 200 ответах: шум или смещение — по доле систематической
    части."""
    points = [
        next((c for c in run.checkpoints if c.responses == 200), run.checkpoints[-1])
        for run in data.runs.values()
    ]
    share = statistics.fmean(1 - c.residual_sd**2 / c.rmse**2 for c in points)
    slope = statistics.fmean(c.slope for c in points)
    bias = statistics.fmean(c.bias for c in points)
    kind = (
        "остаток — в основном шум вокруг прямой: оценка Эло не дошла до истины по разбросу, а не "
        "по смещению"
        if share < 0.5
        else "остаток — в основном систематический: оценка не уходит от экспертной b₀ полностью "
        "или сдвинута вся шкала"
    )
    return (
        f"Итог на {points[0].responses} ответах: систематическая часть — в среднем {f(share, 2)} "
        f"MSE, наклон e(d) — {f(slope, 2)}, средняя e — {f(bias, 2)}; {kind}."
    )


@section("M12")
def m12(runs: Runs) -> Section:
    verdicts, parts = {}, []
    for name, data in runs.sets.items():
        points = [c.responses for c in next(iter(data.runs.values())).checkpoints]
        header = ["Специализация", *(f"{n}: r / RMSE" for n in points), "RMSE b₀"]
        rows, ok = [], []
        for code, run in data.runs.items():
            rows.append(
                [runs.catalog.specializations[code].name]
                + [f"{f(c.r)} / {f(c.rmse)}" for c in run.checkpoints]
                + [f(run.checkpoints[0].expert_rmse)]
            )
            at = next((c for c in run.checkpoints if c.responses == 200), None)
            ok.append(
                at is not None
                and at.r >= 0.95
                and at.rmse <= 0.25
                and at.rmse <= at.expert_rmse / 2
            )
        verdicts[name] = verdict_of(ok)
        decomposition = []
        for code, run in data.runs.items():
            for c in run.checkpoints:
                if c.responses not in (200, runs.scale.warm):
                    continue
                systematic = 1 - c.residual_sd**2 / c.rmse**2
                decomposition.append(
                    [
                        runs.catalog.specializations[code].name,
                        str(c.responses),
                        f(c.rmse),
                        f(c.bias),
                        f(c.slope),
                        f(c.residual_sd),
                        f(systematic, 2),
                    ]
                )
        parts.append(
            f"**{name.upper()}.**\n\n"
            + table(header, rows)
            + "\n\nРазбор остатка: ошибка e = b̂ − b* против отклонения истины от эксперта "
            "d = b* − b₀. Наклон прямой e(d) около −1 — оценка осталась у экспертной b₀ "
            "(недокоррекция переоценки), около 0 — смещение от эксперта ушло; средняя ошибка — "
            "общий сдвиг шкалы; sd остатка — шум Эло вокруг прямой. Доля систематической части — "
            "1 − sd остатка² / RMSE².\n\n"
            + table(
                [
                    "Специализация",
                    "Ответов",
                    "RMSE",
                    "Средняя e",
                    "Наклон e(d)",
                    "sd остатка",
                    "Доля систематической",
                ],
                decomposition,
            )
            + "\n\n"
            + residual_summary(data)
        )
    body = (
        "Порог на 200 ответах на семейство: r(b̂, b*) ≥ 0,95; RMSE не выше 0,25 и не выше половины "
        "RMSE экспертных b₀. Банк калибруется на потоке честных кандидатов набора — с "
        "угадыванием и промахами модели ответа, а не по 2PL оценки; якорные семейства не "
        "считаются.\n\n" + "\n\n".join(parts)
    )
    return judged("M12", body, verdicts)


@section("M13")
def m13(runs: Runs) -> Section:
    verdicts, parts = {}, []
    k = runs.mechanics.exposure_top_k
    for name, data in runs.sets.items():
        rows, ok = [], []
        for code, run in data.runs.items():
            warm_, cold = run.adaptivity, data.cold[code]
            assert warm_ is not None
            ok.append(warm_.ratio <= 0.75)
            per_cell = Counter((fam.topic, fam.grade) for fam in run.families)
            rows.append(
                [
                    runs.catalog.specializations[code].name,
                    f"{f(cold.adaptive_median, 1)} / {f(cold.common_median, 1)}",
                    f(cold.ratio, 2),
                    f"{f(warm_.adaptive_within, 2)} / {f(warm_.common_within, 2)}",
                    f"{f(warm_.adaptive_median, 1)} / {f(warm_.common_median, 1)}",
                    f"**{f(warm_.ratio, 2)}**",
                    f"{f(warm_.adaptive_sd_20)} / {f(warm_.common_sd_20)}",
                    f"{min(per_cell.values())}–{max(per_cell.values())}",
                ]
            )
        verdicts[name] = verdict_of(ok)
        parts.append(
            f"**{name.upper()}.**\n\n"
            + table(
                [
                    "Специализация",
                    "Холодный: адаптивный / бланк",
                    "Отношение",
                    "Прогретый: доля до лимита, адаптивный / бланк",
                    "Прогретый: адаптивный / бланк",
                    "Отношение",
                    "σ̄ на 20: адаптивный / бланк",
                    "Семейств на грейд темы",
                ],
                rows,
            )
        )
    body = (
        "Медиана числа заданий до σ̄ ≤ `test_stop_sd` у адаптивного теста и общего фиксированного "
        "бланка с тем же покрытием тем, на тех же кандидатах, без лимита заданий. Порог — "
        "отношение медиан на прогретом банке не выше 0,75; холодный банк — экспертные параметры, "
        "для сравнения. Доля до лимита — доля кандидатов, дошедших до порога за "
        "`test_max_items` заданий.\n\n"
        + "\n\n".join(parts)
        + f"\n\n**Предел от размера банка.** Адаптивный выбор берёт одно из `exposure_top_k` = {k} "
        "самых информативных семейств темы под потолком показов. Когда на грейд темы приходится "
        "2–3 семейства, выбирать почти не из чего: в окрестности текущей оценки адаптивный тест "
        "берёт те же семейства, что бланк, собранный вокруг середины шкалы, и выигрыш "
        "адаптивности ограничен сверху размером банка, а не правилом выбора."
    )
    return judged("M13", body, verdicts)


# --- M14–M17: защита ---------------------------------------------------------------------------


def _protection(data: DatasetRuns) -> list[ProtectionRun]:
    return list(data.protection.values())


def _attack(runs_: Sequence[ProtectionRun], scheme: str, leak: float, rho: float) -> list[Twins]:
    return [
        t
        for run in runs_
        for a in run.attacks
        if (a.scheme, a.leak, a.rho) == (scheme, leak, rho)
        for t in a.twins
    ]


def _leak_cell(summary: AttackSummary) -> str:
    return f"{f(summary.gain, 2)} · {f(summary.excess, 2)}"


@section("M14")
def m14(runs: Runs) -> Section:
    if not any(d.protection for d in runs.sets.values()):
        return pending("M14")
    mechanics = runs.mechanics
    verdicts, parts, figures = {}, [], {}
    for name, data in runs.sets.items():
        found = _protection(data)
        if not found:
            continue
        summaries = {
            (scheme, leak, rho): summarize(_attack(found, scheme, leak, rho), mechanics)
            for scheme in SCHEMES
            for leak, rho in [(leak, MAIN_RHO) for leak in LEAKS]
            + [(MAIN_LEAK, rho) for rho in RHOS]
        }
        twins = len(_attack(found, "S3", MAIN_LEAK, MAIN_RHO))
        main = {s: summaries[s, MAIN_LEAK, MAIN_RHO] for s in SCHEMES}
        s1, s2, s3 = main["S1"], main["S2"], main["S3"]
        checks = [
            ("избыточная доля S3 ≤ 0,10", s3.excess <= 0.10),
            ("прирост S3 ≤ 0,25", s3.gain <= 0.25),
            ("прирост S3 ≤ ½ S2", s3.gain <= s2.gain / 2),
            ("прирост S3 ≤ ¼ S1", s3.gain <= s1.gain / 4),
        ]
        verdicts[name] = verdict_of(ok for _, ok in checks)
        curve = table(
            ["Схема", *(f"слито {round(leak * 100)} %" for leak in LEAKS)],
            (
                [scheme, *(_leak_cell(summaries[scheme, leak, MAIN_RHO]) for leak in LEAKS)]
                for scheme in SCHEMES
            ),
        )
        sensitivity = table(
            ["Схема", *(f"ρ = {f(rho, 2)}" for rho in RHOS)],
            (
                [scheme, *(_leak_cell(summaries[scheme, MAIN_LEAK, rho]) for rho in RHOS)]
                for scheme in SCHEMES
            ),
        )
        detail = table(
            ["Схема", "Прирост θ̄", "Выше двойника", "Повтор двойника выше", "Избыточная доля"],
            (
                [s, f(v.gain, 2), f(v.raised, 3), f(v.baseline, 3), f(v.excess, 3)]
                for s, v in main.items()
            ),
        )
        early = [run.early for run in found if run.early is not None]
        leaked = sum(e.leaked for e in early)
        clean = sum(e.clean for e in early)
        caught = sum(e.leaked_caught for e in early)
        clean_caught = sum(e.clean_caught for e in early)
        figure = f"m14-{name}.svg"
        figures[figure] = curves_svg(
            f"M14, {name.upper()}: атака утечкой, ρ = {f(MAIN_RHO, 2)}",
            [
                CurvePanel(
                    "Прирост θ̄ читера",
                    "доля слитого банка",
                    "прирост θ̄",
                    [
                        Curve(s, [(leak, summaries[s, leak, MAIN_RHO].gain) for leak in LEAKS])
                        for s in SCHEMES
                    ],
                    threshold=0.25,
                ),
                CurvePanel(
                    "Избыточная доля повышенных",
                    "доля слитого банка",
                    "доля",
                    [
                        Curve(s, [(leak, summaries[s, leak, MAIN_RHO].excess) for leak in LEAKS])
                        for s in SCHEMES
                    ],
                    threshold=0.10,
                ),
            ],
        )
        parts.append(
            f"**{name.upper()}.** Пар «читер — двойник» в условии: {twins}.\n\n"
            f"Кривая атаки при ρ = {f(MAIN_RHO, 2)} — в ячейке прирост θ̄ · избыточная доля:\n\n"
            f"{curve}\n\n![M14, {name.upper()}]({FIGURES}/{figure})\n\n"
            f"Слито {round(MAIN_LEAK * 100)} %, ρ = {f(MAIN_RHO, 2)} — по чему судит порог:\n\n"
            f"{detail}\n\n"
            + "; ".join(f"{label_} — {mark(ok)}" for label_, ok in checks)
            + f".\n\nЧувствительность к ρ при {round(MAIN_LEAK * 100)} %:\n\n{sensitivity}\n\n"
            f"Утечка до калибровки — 20 % читеров со слитыми {round(MAIN_LEAK * 100)} % банка с "
            f"самого прогрева: сверка опорной сложности с экспертной вывела из выдачи {caught} из "
            f"{leaked} слитых семейств ({f(caught / leaked if leaked else math.nan, 2)}) и "
            f"{clean_caught} из {clean} неслитых "
            f"({f(clean_caught / clean if clean else math.nan, 2)})."
        )
    body = (
        "Схемы: S1 — общий фиксированный тест, одни экземпляры у всех, грейд по доле верных с "
        "отсечками B0; S2 — общий бланк семейств со своими экземплярами, оценка IRT и правило "
        "уверенности; S3 — наш тест целиком: определение с каскадом, детектор дрейфа на потоке, "
        "флаги и проверочный блок, грейд — категория после блока. Банк прогрет на честных и "
        "заморожен, утечка — после разогрева; у S1 слита доля заданий бланка, у S2 и S3 — доля "
        "семейств банка. Читер решает слитый экземпляр всегда, свежий экземпляр слитого семейства "
        "— с p' = p + ρ(1 − p), остальное — как честный. На каждого читера — честный двойник с "
        "той же истиной и повтор двойника; у S3 в потоке ещё два честных попутчика на читера — "
        "читеров 20 %. Прирост θ̄ — среднее θ̂ читера минус θ̂ двойника; избыточная доля — доля "
        "читеров с категорией выше двойника минус та же доля у повтора двойника. Порог — для S3 "
        "при 30 % и ρ = 0,5.\n\n"
        + "\n\n".join(parts)
        + "\n\n**Разбор.** S3 сдерживает категорию лучше S2 — избыточная доля ниже, правило "
        "уверенности и каскад не дают слабому приросту превратиться в грейд, — но прирост θ̄ у S3 "
        "почти такой же, как у S2: утечку семейства в S3 должен снимать детектор дрейфа, а при "
        "пороге, подобранном на D3, он слитые семейства почти не ловит (M15). Проверочный блок "
        "читера не останавливает: сигналы блока — быстрые ответы и события вставки и фокуса, а "
        "читер со слитым банком отвечает в обычном темпе. Невиданные кандидатом семейства блока — "
        "не то же, что неслитые: при утечке 30 % банка часть заданий блока тоже слита. S1 сильнее "
        "всех теряет на утечке — слитый экземпляр решается всегда, — поэтому порог «прирост S3 не "
        "выше четверти S1» не проходит из-за абсолютного прироста S3, а не из-за S1."
    )
    return judged("M14", body, verdicts, figures)


@section("M15")
def m15(runs: Runs) -> Section:
    if not any(d.protection for d in runs.sets.values()):
        return pending("M15")
    h = runs.mechanics.drift_cusum_h
    window_leak = runs.protection_scale.leak_responses
    window_honest = runs.protection_scale.honest_responses
    verdicts, parts = {}, []
    for name, data in runs.sets.items():
        found = _protection(data)
        if not found:
            continue
        leaked = [d for run in found for d in run.leak_drift if d.leaked]
        honest = [d for run in found for d in run.honest_drift]
        tpr = drift_flagged(leaked, h, window_leak)
        fpr = drift_flagged(honest, h, window_honest)
        verdicts[name] = verdict_of([tpr >= 0.80, fpr <= 0.05])
        rows = [
            [
                runs.catalog.specializations[run.specialization].name,
                f(drift_flagged([d for d in run.leak_drift if d.leaked], h, window_leak), 2),
                str(sum(d.leaked for d in run.leak_drift)),
                f(drift_flagged(run.honest_drift, h, window_honest), 3),
                str(len(run.honest_drift)),
            ]
            for run in found
        ]
        short_leak = sum(d.responses < window_leak for d in leaked)
        short_honest = sum(d.responses < window_honest for d in honest)
        parts.append(
            f"**{name.upper()}.** TPR — {f(tpr, 2)} ({len(leaked)} слитых семейств), FPR — "
            f"{f(fpr, 3)} ({len(honest)} семейств).\n\n"
            + table(
                [
                    "Специализация",
                    "TPR",
                    "Слитых семейств",
                    "FPR",
                    "Семейств в честном потоке",
                ],
                rows,
            )
            + f"\n\nНе набрали окна: слитых — {short_leak} из {len(leaked)} (меньше "
            f"{window_leak} ответов), в честном потоке — {short_honest} из {len(honest)} (меньше "
            f"{window_honest}). Не набравшее окна и не сработавшее семейство в долю не входит: "
            "у него не было возможности сработать."
        )
    tuning = ""
    if runs.tuning:
        honest_d3 = [d for run in runs.tuning.values() for d in run.honest_drift]
        chosen = tune_threshold(honest_d3, window_honest)
        grid = [g for g in DRIFT_GRID if g <= max(h, chosen or h) + 1.0]
        tuning = (
            "\n\nПодбор порога на D3 (сид 7, только честные): наименьшее значение сетки с FPR не "
            f"выше 0,05 — **{f(chosen, 1) if chosen is not None else 'нет'}**, в конфиге — "
            f"{f(h, 1)}.\n\n"
            + table(
                ["`drift_cusum_h`", *(f(g, 1) for g in grid)],
                [["FPR на D3", *(f(drift_flagged(honest_d3, g, window_honest), 3) for g in grid)]],
            )
        )
    body = (
        f"Детектор — risk-adjusted Bernoulli CUSUM от опорных параметров, `drift_cusum_h` = "
        f"{f(h, 1)}, `drift_shift` = {f(runs.mechanics.drift_shift, 1)}. TPR — доля слитых "
        f"семейств, у которых CUSUM превысил порог в первых "
        f"{runs.protection_scale.leak_responses} ответах после утечки: поток попыток с 20 % "
        f"читеров, слито {round(MAIN_LEAK * 100)} % банка, ρ = {f(MAIN_RHO, 2)}. FPR — доля "
        f"семейств с тревогой за {runs.protection_scale.honest_responses} ответов, когда "
        "отвечают только честные кандидаты набора. CUSUM считается по записанным ответам той же "
        "функцией, что у детектора, без вывода семейств из выдачи: так один поток даёт результат "
        "при любом пороге. Детектор работает только у семейств с опорными параметрами — после "
        "переоценки, у якорей — замороженными. Порог плана: TPR не ниже 0,80, FPR не выше 0,05.\n\n"
        + "\n\n".join(parts)
        + tuning
        + "\n\n"
        "**Разбор.** Детектор не отличает утечку от ошибки самих опорных параметров. При 20 %"
        " читеров и ρ = 0,5 слитое семейство становится легче в среднем на несколько "
        "процентных пунктов доли верных — это сдвиг порядка 0,2–0,3 логита. Опорная сложность"
        " после переоценки на `calibration_refit_min_responses` ответах ошибается на столько "
        "же: RMSE около 0,25 (M12). Модель ответа стенда к тому же не 2PL — угадывание и "
        "промахи, — и честное семейство с такой ошибкой копит CUSUM так же, как слитое. "
        f"Порог, при котором ложных тревог за {window_honest} ответов не больше 5 %, — "
        f"{f(h, 1)} вместо прежних 4, и при нём за {window_leak} ответов срабатывает малая доля "
        "слитых семейств. Детектор ловит "
        "крупную утечку — большую долю читеров или почти полное знание семейства; против "
        "утечки, размазанной по многим кандидатам, нужен сигнал по кандидату, а не по "
        "семейству — согласие попытки с моделью (M22)."
    )
    return judged("M15", body, verdicts)


def _overestimated(helpers: Sequence[Helper], mechanics: Mechanics, attr: str) -> list[Helper]:
    rank = rank_of(mechanics)
    return [h for h in helpers if rank[getattr(h, attr)] > rank[h.truth]]


@section("M16")
def m16(runs: Runs) -> Section:
    data = runs.sets.get("d1")
    if data is None or not data.protection:
        return pending("M16")
    mechanics = runs.mechanics
    found = _protection(data)
    online = [h for run in found for h in run.helpers]
    offline = [h for run in found for h in run.helpers_offline]
    over = _overestimated(online, mechanics, "before")
    flagged = sum(h.flagged for h in over) / len(over) if over else math.nan
    after_with = len(_overestimated(online, mechanics, "after")) / len(online)
    after_without = len(_overestimated(offline, mechanics, "after")) / len(offline)
    ok = flagged >= 0.70
    part_a = (
        "**(а) Персонаж D1.** Помощник решает задание с P = σ(1,5 (1 − b*)) за время около "
        f"25 секунд. Попыток: {len(online)}; категория выше истины до проверочного блока — "
        f"{f(len(over) / len(online), 3)}; среди них помечено — **{f(flagged, 3)}** (порог — не "
        f"ниже 0,70: {mark(ok)}). Завышение после блока: помощник доступен и в блоке — "
        f"{f(after_with, 3)}; в блоке помощи нет — {f(after_without, 3)}. Если помощник доступен "
        "и в блоке, блок его почти не ловит — это ожидаемое ограничение неподнадзорной "
        "проверки.\n\n"
        "**Разбор.** Завышение у помощника — у кандидатов с истинным уровнем стажёра и ниже: "
        "помощник решает задания примерно до middle, и тест поднимает их до junior. Задания у "
        "такой оценки лёгкие, честный ответ на них и так быстрый, и 25 секунд аномалией не "
        "выглядят; флаг времени срабатывает только на верный ответ на трудное для кандидата "
        "задание. Помечаются попытки, где тест успел дать помощнику трудные задания.\n\n"
        + table(
            ["Истинный грейд", "Попыток", "Завышено до блока", "Помечено", "Завышено после блока"],
            _helper_rows(online, mechanics),
        )
    )
    part_b = "**(б) D7 — Claude Sonnet через Claude Agent SDK.** " + _d7(runs)
    body = part_a + "\n\n" + part_b
    return Section("M16", body, f"(а) {PASSED if ok else FAILED}; (б) без порога", {}, {})


def _helper_rows(helpers: Sequence[Helper], mechanics: Mechanics) -> list[list[str]]:
    rank = rank_of(mechanics)
    rows = []
    for grade in [None, *grades_by_threshold(mechanics.grade_thresholds)]:
        group = [h for h in helpers if h.truth == grade]
        if not group:
            continue
        over = [h for h in group if rank[h.before] > rank[h.truth]]
        rows.append(
            [
                grade or "ниже стажёра",
                str(len(group)),
                str(len(over)),
                str(sum(h.flagged for h in over)),
                str(sum(rank[h.after] > rank[h.truth] for h in group)),
            ]
        )
    return rows


def _d7(runs: Runs) -> str:
    data = runs.sets.get("d1")
    found = list(data.protection.values()) if data else []
    attempts = [a for run in found for a in run.llm]
    missing = sum(run.llm_missing for run in found)
    if not attempts:
        return f"{WAITING.capitalize()}: нет записи ответов модели — команда `llm --record`."
    model = next((run.llm_model for run in found if run.llm_model), "модель")
    counts = Counter((a.specialization, a.before, a.after, a.flagged) for a in attempts)
    flagged = sum(a.flagged for a in attempts) / len(attempts)
    rows = [
        [
            runs.catalog.specializations[code].name,
            before or "без категории",
            "да" if flag else "нет",
            after or "без категории",
            str(n),
        ]
        for (code, before, after, flag), n in sorted(
            counts.items(), key=lambda item: (item[0][0], str(item[0][1]), str(item[0][2]))
        )
    ]
    note = (
        f" В записи не нашлось ответов на {missing} заданий — они засчитаны неверными, запись "
        "надо дописать."
        if missing
        else ""
    )
    return (
        f"Модель {model} из записи ответов, время — время ответа модели плюс 10 секунд на "
        f"копирование. Попыток: {len(attempts)}, по {len(attempts) // 2} на специализацию, "
        f"заявлен {CLAIMED}. Помечено и отправлено на проверочный блок — **{f(flagged, 2)}**. "
        "Цифры — как есть, без порога: истинного уровня у модели нет. Модель отвечает "
        "уверенно и быстро на трудные задания, поэтому флаги времени ставятся почти всегда, но "
        "проверочный блок она решает так же, как тест, и категория после блока остаётся. Против "
        "сильной модели неподнадзорный блок не защищает — это ограничение из mechanics.md, §8; "
        "противовес — уровни доверия и ФСП."
        + note
        + "\n\n"
        + table(
            ["Специализация", "Грейд до блока", "Помечено", "Категория после блока", "Попыток"],
            rows,
        )
    )


@section("M17")
def m17(runs: Runs) -> Section:
    if not any(d.protection for d in runs.sets.values()):
        return pending("M17")
    verdicts, rows = {}, []
    for name, data in runs.sets.items():
        found = _protection(data)
        if not found:
            continue
        attempts = sum(run.honest_blocks.attempts for run in found)
        blocks = sum(run.honest_blocks.blocks for run in found)
        mismatches = sum(run.honest_blocks.mismatches for run in found)
        block_share, mismatch_share = blocks / attempts, mismatches / attempts
        verdicts[name] = verdict_of([block_share <= 0.10, mismatch_share <= 0.01])
        rows.append([name.upper(), str(attempts), f(block_share, 3), f(mismatch_share, 3)])
    body = (
        "Честные определения из потока S3 M14 (слито 30 %, ρ = 0,5): двойники и попутчики "
        "читеров. Доля определений с проверочным блоком и доля расхождений среди всех честных "
        "определений. Порог: блок не чаще 0,10, расхождение не чаще 0,01.\n\n"
        + table(["Набор", "Честных определений", "С блоком", "Расхождение"], rows)
    )
    return judged("M17", body, verdicts)


# --- M22 ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FitShares:
    """Доли определений, помеченных флагами времени, l_z и хотя бы одним из них."""

    count: int
    time: float
    misfit: float
    any: float


def fit_shares(rows: Sequence[tuple[int, float | None]], mechanics: Mechanics) -> FitShares | None:
    """`rows` — (флагов времени, l_z) определений. Событий фокуса на стенде нет: согласия на них
    синтетика не даёт."""
    if not rows:
        return None
    time = [flags >= mechanics.rt_flags_for_verification for flags, _ in rows]
    misfit = [fit is not None and fit <= -mechanics.person_fit_lz for _, fit in rows]
    n = len(rows)
    return FitShares(
        n,
        sum(time) / n,
        sum(misfit) / n,
        sum(a or b for a, b in zip(time, misfit, strict=True)) / n,
    )


@section("M22")
def m22(runs: Runs) -> Section:
    if not any(d.protection for d in runs.sets.values()):
        return pending("M22")
    mechanics = runs.mechanics
    rank = rank_of(mechanics)
    verdicts, rows = {}, []
    for name, data in runs.sets.items():
        found = _protection(data)
        signals = [s for run in found for s in run.signals]
        if not signals:
            continue
        honest = [s for s in signals if s.persona == Persona.honest]
        fpr = sum(
            s.person_fit is not None and s.person_fit <= -mechanics.person_fit_lz for s in honest
        ) / max(1, len(honest))
        cheaters = fit_shares(
            [
                (s.time_flags, s.person_fit)
                for s in signals
                if s.persona == Persona.bank_leak and rank[s.result] > rank[s.truth]
            ],
            mechanics,
        )
        helpers = fit_shares(
            [
                (h.time_flags, h.person_fit)
                for run in found
                for h in run.helpers
                if rank[h.before] > rank[h.truth]
            ],
            mechanics,
        )
        added = cheaters.any - cheaters.time if cheaters else math.nan
        verdicts[name] = verdict_of([fpr <= 0.05, added >= 0.10])
        for who, shares in (("читеры, слито 30 %", cheaters), ("LLM-помощник", helpers)):
            rows.append(
                [
                    name.upper(),
                    who,
                    f(fpr, 3),
                    "0" if shares is None else str(shares.count),
                    "—" if shares is None else f(shares.time, 3),
                    "—" if shares is None else f(shares.misfit, 3),
                    "—" if shares is None else f(shares.any, 3),
                ]
            )
    if not rows:
        return pending("M22")
    body = (
        f"$l_z$ определения на остановке, порог `person_fit_lz` = {f(mechanics.person_fit_lz, 1)} "
        "должен быть подобран на D3 (`uv run python -m validation person-fit`). "
        "До подтверждения порога и пользы M22 `person_fit_enabled=false`: статистика не влияет "
        "на присвоение категории. FPR — доля честных определений "
        "потока S3 M14 с $l_z$ не выше −порога. Ниже — определения с завышением категории до "
        "проверочного блока: у читеров со слитыми 30 % банка (ρ = 0,5) и у LLM-помощника — доля "
        "помеченных флагами времени, $l_z$ и хотя бы одним из них. Событий фокуса на стенде нет. "
        "Порог: FPR не выше 0,05; у читеров $l_z$ добавляет к флагам времени не меньше 0,10; у "
        "помощника — без порога.\n\n"
        + table(
            [
                "Набор",
                "Кто",
                "FPR честных",
                "Определений с завышением",
                "Флаги времени",
                "$l_z$",
                "Хотя бы один",
            ],
            rows,
        )
        + "\n\n"
        + resume_part(runs.mechanics)
    )
    return judged("M22", body, verdicts)


# Записи ответов моделей и таймаут модели — как у команд стенда.
RECORDED_DIR = BACKEND_DIR / "validation" / "data" / "recorded"
MODEL_TIMEOUT = Settings.model_fields["text_understanding_timeout_seconds"].default


def resume_measures(mechanics: Mechanics) -> list[resume_parsing.Measured]:
    """Разбор резюме на D6: правила и модель из записи, если она есть."""
    found = [resume_parsing.measure(mechanics, None, MODEL_TIMEOUT)]
    recording = Recording(RECORDED_DIR / "d6.agent_sdk.json")
    if recording.answers:
        measured = resume_parsing.measure(mechanics, recording, MODEL_TIMEOUT)
        if not measured.missing:
            found.append(measured)
    return found


def resume_part(mechanics: Mechanics) -> str:
    found = resume_measures(mechanics)
    pending, total = resume_parsing.pending_review()
    lines = [
        "**Разбор резюме на D6.** Видимый текст PDF портом продукта, разбор и проверка черновика "
        "сценарием; модель — из записи `validation/data/recorded/d6.agent_sdk.json`, откат на "
        "правила — как в проде. ФИО, email, телефон, роли и стаж — доля точных совпадений на "
        f"чистых резюме, стек — F1 по кодам. Порог: не ниже {f(resume_parsing.FIELD_THRESHOLD)} "
        "по каждому полю. Время — p95 разбора: у правил — CPU, у модели — записанное время ответа "
        "модели разработки поверх правил; локальная модель сдачи на D6 не мерилась.",
        "",
        resume_parsing.markdown(found, exact=False).split("\n\n")[0],
    ]
    if pending:
        lines += [
            "",
            f"Разметка D6 ждёт проверки человеком ({pending} из {total} записей): цифры — "
            "против черновой разметки генератора, вердикт части — после проверки.",
        ]
    return "\n".join(lines)


@section("M18")
def m18(runs: Runs) -> Section:
    found = resume_measures(runs.mechanics)
    ok = all(i.same_fields and i.same_stack for m in found for i in m.injections)
    body = (
        "Варианты D6 с инъекциями против своих чистых двойников: все поля разбора совпадают, и "
        "самоописанный стек — единственное, что резюме даёт подборке, — тот же, поэтому выдачи "
        "по всем потребностям не меняются. Скрытый текст продукт отбрасывает до разбора, видимая "
        "инструкция остаётся данными: схема ответа модели — только значения справочника. Сетевых "
        "вызовов наружу нет: правила локальны, модель отвечает из записи, адаптер локальной модели "
        "ходит только на адрес из конфига (`tests/test_text_llama.py`). Порог — 100 %.\n\n"
        + resume_parsing.markdown(found, exact=False).split("\n\n")[1]
    )
    pending, _ = resume_parsing.pending_review()
    if pending:
        body += f"\n\nРазметка D6 ждёт проверки человеком: {pending} записей."
        return Section("M18", body, f"{PASSED if ok else FAILED}; разметка не проверена человеком")
    return Section("M18", body, PASSED if ok else FAILED)


# --- M20, D4 -----------------------------------------------------------------------------------


def scored_pairs(data: DatasetRuns) -> dict[str, list[tuple[uuid.UUID, uuid.UUID, float]]]:
    """По специализации — пары нашей выдачи со скором: (потребность, кандидат, S)."""
    return {
        code: [
            (need, p.candidate, p.score)
            for need, rows in run.placed.items()
            for p in rows
            if p.score is not None
        ]
        for code, run in data.runs.items()
    }


def level_scale(runs: Runs) -> str:
    thresholds = runs.mechanics.grade_thresholds
    bands = ", ".join(
        f"{runs.catalog.grades[g].name} — от {f(thresholds[g], 2)}"
        for g in grades_by_threshold(thresholds)
    )
    return f"Пороги грейдов на шкале уровня: {bands}."


FSP_RESULTS = {
    "winner": "победитель",
    "prize": "призёр",
    "finalist": "финалист",
    "participant": "участник",
}


def card(data: DatasetRuns, runs: Runs, item: d4.Item) -> d4.Card:
    """Карточка пары D4 — как её видит работодатель до принятия приглашения."""
    run = data.runs[item.specialization]
    need = next(n for n in data.dataset.needs if n.id == item.need)
    seen = next(o for o in data.dataset.observed if o.id == item.candidate)
    grade, levels = run.listed[item.candidate]
    spec = runs.catalog.specializations[item.specialization]
    category = f"{spec.name} · {runs.catalog.grades[grade].name}" if grade else "без категории"
    profile = [
        (t.name, levels[t.code].mean, levels[t.code].sd) for t in spec.topics if t.code in levels
    ]
    fsp = [
        f"{a['event']}, {a['date']}: {FSP_RESULTS.get(a['fsp_result'], a['fsp_result'])}"
        + (f", {a['place']} место" if a.get("place") else "")
        for a in data.dataset.registry.get(seen.fsp_sub or "", [])
    ]
    stack = ", ".join(runs.catalog.technologies[t].name for t in seen.stack)
    return d4.Card(need_text(need.form, runs.catalog), category, profile, fsp, stack)


def write_d4(runs: Runs, directory: Path | None = None) -> bool:
    """Выборка D4 и форма разметки по прогону D1 — только если выборки ещё нет: начатую
    разметку новая выборка не затирает. Возвращает, записана ли."""
    directory = directory or d4.D4_DIR
    data = runs.sets.get("d1")
    if data is None or (directory / d4.SAMPLE).exists():
        return False
    items = d4.draw(scored_pairs(data), data.dataset.params.seed)
    d4.write_sample(items, directory)
    cards = {it.number: card(data, runs, it) for it in items}
    (directory / d4.FORM).write_text(d4.form(items, cards, level_scale(runs)), encoding="utf-8")
    return True


def score_grade(score: float) -> int:
    """Градация скора — по тем же отсечкам, что эталон: 0,5, 0,7 и 0,9."""
    return next((3 - i for i, edge in enumerate(RELEVANCE_EDGES) if score >= edge), 0)


@section("M20")
def m20(runs: Runs) -> Section:
    data = runs.sets.get("d1")
    directory = d4.D4_DIR
    items = d4.load_sample(directory)
    if runs.scale != PLAN_SCALE:
        return Section(
            "M20",
            f"{WAITING.capitalize()}: выборка D4 — из прогона по плану, а этот прогон короче.",
            WAITING,
        )
    if data is None or items is None:
        return Section(
            "M20",
            f"{WAITING.capitalize()}: выборки D4 нет — её пишет команда `report` при прогоне по "
            "плану.",
            WAITING,
        )
    labels = {rater: d4.load_labels(directory, rater) for rater in d4.RATERS}
    numbers = [it.number for it in items]
    filled = {r: sum(n in own for n in numbers) for r, own in labels.items()}
    where = f"`backend/validation/data/d4/` ({d4.FORM}, оценки — labels-a.csv и labels-b.csv)"
    if any(v < len(numbers) for v in filled.values()):
        done = ", ".join(f"{r.upper()} — {v} из {len(numbers)}" for r, v in filled.items())
        return Section(
            "M20",
            f"Ожидает разметки: выборка D4 и форма — {where}; размечено: {done}. Расчёт готов и "
            "сработает, когда оба файла оценок заполнены целиком.",
            WAITING,
        )
    a, b = labels["a"], labels["b"]
    placed = {
        (need, p.candidate): p.score
        for run in data.runs.values()
        for need, rows in run.placed.items()
        for p in rows
    }
    kept = [it for it in items if placed.get((it.need, it.candidate)) is not None]
    ours = [placed[it.need, it.candidate] or 0.0 for it in kept]
    consensus = [(a[it.number] + b[it.number]) / 2 for it in kept]
    raters = weighted_kappa([(a[n], b[n]) for n in numbers], d4.SCALE)
    rho = spearman(ours, consensus)
    model = weighted_kappa(
        [(score_grade(s), math.floor(c + 0.5)) for s, c in zip(ours, consensus, strict=True)],
        d4.SCALE,
    )
    found: dict[str, float | None] = {
        m: spearman([data.scores[m][it.need, it.candidate] for it in kept], consensus)
        if m in data.scores
        else None
        for m in BASELINES
    }
    verdict, said = comparison(rho, found, 0.5, 0.0, lower=False)
    broken = [
        text
        for ok, text in (
            (raters >= 0.6, "κ_AB ниже 0,60"),
            (model >= 0.5, "каппа модели ниже 0,50"),
        )
        if not ok
    ]
    if broken:
        verdict, said = FAILED, f"{said}; не выполнено: {', '.join(broken)}"
    rows = [
        ["κ_AB размечающих, квадратичная", "≥ 0,60", f(raters)],
        ["ρ(S, консенсус)", "≥ 0,50 и ≥ лучшей B1–B3", f(rho)],
        *([f"ρ({m}, консенсус)", "—", f(v)] for m, v in found.items()),
        ["Каппа градации S и округлённого консенсуса", "≥ 0,50", f(model)],
    ]
    note = (
        "\n\n**κ_AB ниже 0,60** — рубрика неоднозначна: размечающие расходятся сильнее, чем "
        "позволяет сравнение с моделью. Сравнение всё равно опубликовано."
        if raters < 0.6
        else ""
    )
    body = (
        f"Пары D4 — {len(numbers)} из D1, по специализациям поровну и по квинтилям нашего скора; "
        f"форма и оценки — {where}. Консенсус — среднее двух оценок; со скором в выдаче — "
        f"{len(kept)} пар.\n\n" + table(["Показатель", "Порог", "Значение"], rows) + note
    )
    return Section("M20", body, f"D1 — {verdict}: {said}", {}, {"d1": verdict})


# --- Базовые линии -----------------------------------------------------------------------------


def baselines_note(runs: Runs) -> str:
    """Раздел отчёта о базовых линиях: как устроены и чем и когда считались на наборах."""

    def b3_on(name: str, data: DatasetRuns) -> str:
        if data.b3 is None:
            return f"{name.upper()} — прогона нет, сравнение с B3 — «{WAITING}»"
        dates = (
            data.b3.first if data.b3.first == data.b3.last else f"{data.b3.first}–{data.b3.last}"
        )
        return f"{name.upper()} — {data.b3.model}, {dates}, ответов {data.b3.answers}"

    b2 = ", ".join(n.upper() for n, d in runs.sets.items() if "B2" in d.scores) or "нет"
    b3 = "; ".join(b3_on(n, d) for n, d in runs.sets.items())
    prompt = "\n".join("    " + line for line in B3_SYSTEM.splitlines())
    return (
        "## Базовые линии\n\n"
        f"Определения — [план, «Базовые линии»]({PLAN}#базовые-линии). B0 — наивный тест, см. M9. "
        "B1–B3 ранжируют по тексту: резюме кандидата из наблюдаемого — имя, возраст, вуз, стаж и "
        "самоописание со стеком; вакансия — название, направление и грейд, стек, формат и вилка. "
        "Истины, теста и нашего скора они не видят.\n\n"
        f"- **B1 — BM25 Okapi**, k1 = {f(BM25_K1, 1)}, b = {f(BM25_B, 2)}; слова в нижнем "
        "регистре без лемматизации; IDF и средняя длина — по резюме пула специализации.\n"
        f"- **B2 — эмбеддинги** `{E5_MODEL}`, ревизия `{E5_REVISION[:12]}`, ONNX на CPU: среднее "
        "скрытых состояний по токенам, косинус векторов «query: вакансия» и «passage: резюме». "
        f"Наборы: {b2}.\n"
        "- **B3 — LLM-ранжировщик** через Claude Agent SDK, только синтетика: без инструментов "
        "и настроек с диска, структурированный ответ — целое 0–10 на пару. Ответы кэшируются в "
        "`backend/validation/data/recorded/b3.<набор>.json` по ключу пары и хэшу запроса; отчёт "
        "пересобирается из кэша без сети и ключа API, пары без ответа в кэше — ошибка сборки. "
        f"Модель и дата прогона: {b3}. Системный промпт:\n\n{prompt}"
    )


# --- M7 ----------------------------------------------------------------------------------------


@section("M7")
def m7(runs: Runs) -> Section:
    model, baselines = load_model(Settings().acceptance_model_file), load_baselines()
    if model is None or baselines is None:
        return pending("M7")
    verdicts, parts = {}, []
    for name, data in runs.sets.items():
        if not data.offers:
            continue
        e = evaluate(model, baselines, data.offers)
        mono = e.monotonicity
        verdicts[name] = verdict_of(
            [e.model.roc_auc >= 0.75, e.model.ece <= 0.05, mono.share == 1.0]
        )
        parts.append(
            f"**{name.upper()}.** Пар {e.pairs}, доля принятий {f(e.accepted)}.\n\n"
            + table(
                ["Модель", "ROC-AUC", "ECE"],
                [
                    ["CatBoost", f"**{f(e.model.roc_auc)}**", f"**{f(e.model.ece)}**"],
                    [
                        "Логистическая регрессия по вилке к ожиданию",
                        f(e.logistic.roc_auc),
                        f(e.logistic.ece),
                    ],
                    [
                        "Константа — доля принятий обучения",
                        f(e.constant.roc_auc),
                        f(e.constant.ece),
                    ],
                ],
            )
            + f"\n\nМонотонность: вилка — {mono.salary_ok} из {mono.salary_total} соседних точек "
            f"сетки, загрузка — {mono.load_ok} из {mono.load_total}; всего "
            f"**{f(math.floor(1000 * mono.share) / 10, 1)} %**."
        )
    if not parts:
        return pending("M7")
    body = (
        "Модель — CatBoost из файла `backend/app/adapter/acceptance_model.cbm`, обученная "
        "командой `uv run python -m validation acceptance` на своём сиде; базовые линии — на тех "
        "же обучающих парах. Отложенные пары — подборки по потребностям набора: top-K по S и "
        "случайные кандидаты сверх них, решения — по правилу синтетического кандидата из скрытой "
        "склонности, которой модель не видит. ECE — 10 равных корзин. Сетка монотонности — "
        "отношение середины вилки к ожиданию 0,5–2,0 шагом 0,05 и открытые приглашения 0–10 на "
        "первых 50 парах. Порог: ROC-AUC не ниже 0,75, ECE не выше 0,05, монотонность в 100 % "
        "точек.\n\n" + "\n\n".join(parts)
    )
    return judged("M7", body, verdicts)


# --- M6 ----------------------------------------------------------------------------------------


@section("M6")
def m6(runs: Runs) -> Section:
    verdicts, parts = {}, []
    for name, data in runs.sets.items():
        if not all(run.market for run in data.runs.values()):
            continue
        pool = [c for run in data.runs.values() for c in run.pool]

        def share(need: uuid.UUID, candidate: uuid.UUID, data: DatasetRuns = data) -> float:
            return data.pairs[need, candidate].share

        found = {
            strategy: market_metrics(
                [s for run in data.runs.values() for s in run.market[strategy]], pool, share
            )
            for strategy in STRATEGIES
        }
        a, b = found["A"], found["B"]
        ratio = b.accepted_share / a.accepted_share if a.accepted_share else math.inf
        match_ratio = (
            b.true_match / a.true_match
            if a.true_match is not None and b.true_match is not None and a.true_match > 0
            else math.nan
        )
        checks = [ratio >= 1.2, b.gini <= a.gini, match_ratio >= 0.95]
        verdicts[name] = verdict_of(checks)
        rows = [
            [
                label,
                str(m.sent),
                str(m.accepted),
                f(m.accepted_share),
                f(m.gini),
                "—" if m.true_match is None else f(m.true_match),
            ]
            for label, m in (("A — по S", a), ("B — по S × P(принятия)", b))
        ]
        parts.append(
            f"**{name.upper()}.** Кандидатов в пуле {len(pool)}.\n\n"
            + table(
                ["Стратегия", "Отправлено", "Принято", "Доля принятых", "Джини", "Средний M*"],
                rows,
            )
            + f"\n\nДоля принятых B / A — **{f(ratio)}** (порог ≥ 1,2); Джини B "
            f"{'не выше' if checks[1] else 'выше'}, чем A; средний M* B / A — "
            f"**{f(match_ratio)}** (порог ≥ 0,95)."
        )
    if not parts:
        return pending("M6")
    mechanics = runs.mechanics
    body = (
        f"Восемь недель рынка по каждой специализации набора. Компания перестраивает подборку по "
        f"своей потребности каждую неделю и шлёт приглашения сверху выдачи: бюджет недели "
        f"`invitation_weekly_budget` = {mechanics.invitation_weekly_budget} делится поровну между "
        f"потребностями компании. Стратегия A — порядок «только соответствие» (по S), B — "
        f"сохранённый порядок по S × P(принятия) с моделью из `acceptance_model.cbm`, обученной "
        f"на своём сиде; обе — из той же подборки продукта. Одно открытое приглашение компании "
        f"кандидату, срок ответа `invitation_ttl_days` = {mechanics.invitation_ttl_days} дней, "
        f"задержка ответа — экспонента со средним "
        f"{f(DATASETS['d1'].market_response_mean_days, 1)} дня. Решение — правило синтетики по "
        f"скрытой склонности, вилке против ожиданий, загрузке открытыми приглашениями на момент "
        f"ответа, формату и городу. Джини — по числу приглашений на кандидата пула, включая "
        f"неприглашённых. Порог: доля принятых у B не ниже 1,2 доли у A; Джини у B не выше, чем "
        f"у A; средний M* принятых у B не ниже 0,95 от A.\n\n" + "\n\n".join(parts)
    )
    return judged("M6", body, verdicts)


# --- M19 ---------------------------------------------------------------------------------------


@section("M19")
def m19(runs: Runs) -> Section:
    if not {"d1", "d2"} <= set(runs.sets):
        return Section("M19", "Нужны оба набора, D1 и D2.", WAITING)
    d1, d2 = runs.sets["d1"], runs.sets["d2"]
    ndcg = quality(d1, "ndcg") or math.nan, quality(d2, "ndcg") or math.nan
    exact = (
        truthfulness(honest_grades(d1, runs.mechanics)["ours"], runs.mechanics).exact,
        truthfulness(honest_grades(d2, runs.mechanics)["ours"], runs.mechanics).exact,
    )
    rows, ok = [], []
    for label_, (one, two) in (("nDCG@10", ndcg), ("Точное совпадение грейда", exact)):
        drop = (one - two) / one
        ok.append(drop <= 0.2)
        rows.append([label_, f(one), f(two), f(drop, 2), mark(drop <= 0.2)])
    shifted = {
        m: computed(runs, m).sets.get("d2", WAITING)
        for m in ("M1", "M2", "M3", "M4", "M9", "M10", "M14", "M15")
    }
    failed = [m for m, v in shifted.items() if v == FAILED]
    rows += [[f"Порог {m} на D2", "", "", "", mark(v != FAILED)] for m, v in shifted.items()]
    body = (
        "Порог: пороги метрик M1–M4, M9, M10, M14, M15 выполняются и на D2; относительная "
        "деградация nDCG@10 и точного совпадения грейда не больше 20 %.\n\n"
        + table(["Показатель", "D1", "D2", "Деградация", "Выполнено"], rows)
    )
    if failed or not all(ok):
        reasons = [*(f"порог {m} на D2" for m in failed)]
        reasons += ["деградация больше 20 %"] if not all(ok) else []
        return Section("M19", body, f"{FAILED}: {', '.join(reasons)}")
    waiting = [m for m, v in shifted.items() if v == WAITING]
    return Section("M19", body, f"{WAITING}: {', '.join(waiting)}")


# --- M21 ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Share:
    hits: int
    total: int

    @property
    def value(self) -> float:
        return self.hits / self.total if self.total else math.nan

    def __str__(self) -> str:
        return f"{f(self.value, 2)} ({self.hits} из {self.total})"


def flagged_share(families: Iterable[FamilyFit]) -> Share:
    """Доля отмеченных проверкой согласия среди переоценённых семейств."""
    checked = [x for x in families if x.refitted]
    return Share(sum(x.flagged for x in checked), len(checked))


@section("M21")
def m21(runs: Runs) -> Section:
    mech = runs.mechanics
    verdicts, parts = {}, []
    for name, data in runs.sets.items():
        if not data.fit:
            continue
        rows = []
        for code, run in data.fit.items():
            bad = [x for x in run.families if x.corruption is not None]
            good = [x for x in run.families if x.corruption is None]
            rows.append(
                [
                    runs.catalog.specializations[code].name,
                    str(flagged_share(bad)),
                    str(flagged_share(x for x in good if x.choice)),
                    str(flagged_share(x for x in good if not x.choice)),
                    f"{f(run.rmse_in)} / {f(run.rmse_checked)} / {f(run.rmse_clean)}",
                ]
            )
        families = [x for run in data.fit.values() for x in run.families]
        bad = [x for x in families if x.corruption is not None]
        good = [x for x in families if x.corruption is None]
        tpr = flagged_share(bad)
        fpr_choice = flagged_share(x for x in good if x.choice)
        fpr_value = flagged_share(x for x in good if not x.choice)
        kinds = {
            Corruption.key: "ошибка эталона",
            Corruption.flat: "ответ не зависит от уровня",
        }
        by_kind = "; ".join(
            f"{label} — {flagged_share(x for x in bad if x.corruption == kind)}"
            for kind, label in kinds.items()
        )
        rmse = [
            mean(r.rmse_in for r in data.fit.values()),
            mean(r.rmse_checked for r in data.fit.values()),
            mean(r.rmse_clean for r in data.fit.values()),
        ]
        unchecked = sum(not x.refitted for x in families)
        ok = [tpr.value >= 0.80, fpr_choice.value <= 0.05, fpr_value.value <= 0.05]
        measured = all(share.total for share in (tpr, fpr_choice, fpr_value))
        verdicts[name] = verdict_of(ok) if measured else WAITING
        parts.append(
            f"**{name.upper()}.**\n\n"
            + table(
                [
                    "Специализация",
                    "TPR",
                    "FPR, выбор из вариантов",
                    "FPR, вычисляемый ответ",
                    "RMSE θ̄: в выдаче / после переоценки / без испорченных",
                ],
                rows,
            )
            + "\n\n"
            + table(
                ["Мера", "Значение", "Порог", "Выполнен"],
                [
                    ["TPR", str(tpr), "≥ 0,80", mark(tpr.value >= 0.80)],
                    [
                        "FPR, выбор из вариантов",
                        str(fpr_choice),
                        "≤ 0,05",
                        mark(fpr_choice.value <= 0.05),
                    ],
                    [
                        "FPR, вычисляемый ответ",
                        str(fpr_value),
                        "≤ 0,05",
                        mark(fpr_value.value <= 0.05),
                    ],
                    ["RMSE θ̄, испорченные в выдаче", f(rmse[0]), "—", "—"],
                    ["RMSE θ̄, выдача после переоценки", f(rmse[1]), "—", "—"],
                    ["RMSE θ̄, выведены все испорченные", f(rmse[2]), "—", "—"],
                ],
            )
            + f"\n\nTPR по видам порчи: {by_kind}. Не набрали ответов на переоценку и в долях "
            f"не считаются: {unchecked} семейств из {len(families)}. Испорчено по "
            f"{f(CORRUPTED_SHARE * 100, 0)} % неякорных семейств специализации, округлено до "
            "чётного, поровну двух видов, по кругу тем и грейдов."
        )
    if not parts:
        return Section("M21", "Нужен прогон D1 с испорченными семействами.", WAITING)
    body = (
        "Семейство отмечено, если проверка согласия после пакетной переоценки выводит его из "
        f"выдачи: переоценённая â ниже `item_fit_discrimination_min` = "
        f"{f(mech.item_fit_discrimination_min, 2)} или модель с потолком объясняет ответы лучше "
        f"2PL больше чем на `item_fit_ceiling_gain_max` = {f(mech.item_fit_ceiling_gain_max, 2)} "
        "нат ([mechanics.md](mechanics.md) §7); оба числа подобраны на D3 командой `fit`. Банк "
        "набора плюс испорченные семейства — только в скрытой истине: ошибка эталона — у половины "
        "экземпляров верный ответ засчитывается неверным; ответ не зависит от уровня — "
        "P(верно) = 0,5. Банк прогревается на честных кандидатах набора, переоценка — на "
        f"`calibration_refit_min_responses` = {mech.calibration_refit_min_responses} "
        "ответах на семейство; якоря не портятся и в доли не входят. RMSE общего уровня — у "
        f"честных кандидатов набора ({runs.scale.fit} на специализацию) на замороженном банке "
        "в трёх состояниях, на одних и тех же случайных числах ответа: испорченные в выдаче; "
        "выдача, как её оставила переоценка, — проверки согласия и дрейфа, с их ложными "
        "срабатываниями; сверх того выведены все испорченные.\n\n"
        "Результаты прежней проверки — RMSD против переоценённых (a, b) — на D1 видели до выбора "
        "новой (журнал изменений плана); новая и её числа выбраны на D3 по правилу, записанному "
        "до прогона D3.\n\n"
        + "\n\n".join(parts)
        + "\n\nРазбор потребности (D5) — вторая часть M21 — считается командой `parsing` и в "
        "этот отчёт не сведён."
    )
    text = {
        n: f"{v} (согласие семейств); разбор потребности — {WAITING}" for n, v in verdicts.items()
    }
    return judged("M21", body, verdicts, text=text)


# --- Отчёт -------------------------------------------------------------------------------------


def pending(metric: str) -> Section:
    return Section(
        metric, f"{WAITING.capitalize()}: {PENDING.get(metric, 'метрика не считается')}.", WAITING
    )


def render(runs: Runs, sections: dict[str, Section]) -> str:
    """Markdown отчёта: шапка прогона, сводка вердиктов, разделы в порядке `order`."""
    m = runs.mechanics
    scale = runs.scale
    sizes = ", ".join(
        f"{name.upper()} — сид {data.dataset.params.seed}, кандидатов {len(data.dataset.truths)}, "
        f"потребностей {len(data.dataset.needs)}"
        for name, data in runs.sets.items()
    )
    head = [
        "# Отчёт валидации",
        "",
        f"Отчёт собран командой стенда по [плану валидации]({PLAN}) — правки руками не вносятся: "
        "`uv run python -m validation report` из `backend/` перезаписывает его байт в байт.",
        "",
        f"Наборы: {sizes}. Банк каждой специализации прогрет до {scale.warm} ответов на семейство "
        f"на честных кандидатах набора; пар повторного прохождения на специализацию — "
        f"{scale.pairs}; кандидатов M13 — {scale.compare}. Механики — `config/mechanics.yaml`: "
        f"κ = {f(m.level_sd_inflation, 2)}, `test_stop_sd` = {f(m.test_stop_sd, 2)}, "
        f"`grade_confidence` = {f(m.grade_confidence, 2)}.",
        "",
        "Вердикт «выполнен» — выполнены все части порога метрики на наборе; «ожидает данных» — "
        "метрику этот прогон не считает. Отрицательный результат — как есть, с разбором причины.",
        "",
        "## Сводка",
        "",
        table(
            ["Метрика", "Вердикт"],
            (
                [f"[{metric}. {METRICS[metric][0]}](#{_anchor(metric)})", sections[metric].verdict]
                for metric in order(sections)
            ),
        ),
    ]
    parts = [baselines_note(runs)]
    for metric in order(sections):
        title, plan_anchor = METRICS[metric]
        s = sections[metric]
        parts.append(
            f"## {metric}. {title}\n\n"
            f"Определение — [план, {metric}]({PLAN}#{plan_anchor}). Вердикт: {s.verdict}.\n\n"
            f"{s.body}"
        )
    return "\n".join(head) + "\n\n" + "\n\n".join(parts) + "\n"


def _anchor(metric: str) -> str:
    title = METRICS[metric][0].lower()
    kept = "".join(ch for ch in f"{metric.lower()} {title}" if ch.isalnum() or ch in " -")
    return kept.replace(" ", "-")


def computed(runs: Runs, metric: str) -> Section:
    """Раздел метрики — один раз на прогон: M19 читает вердикты других разделов."""
    if metric not in runs.memo:
        runs.memo[metric] = SECTIONS[metric](runs) if metric in SECTIONS else pending(metric)
    return runs.memo[metric]


def build(runs: Runs, figures_dir: str = FIGURES) -> tuple[str, dict[str, str]]:
    """Текст отчёта и картинки; ссылки на картинки — в каталог `figures_dir` рядом с отчётом."""
    sections = {metric: computed(runs, metric) for metric in METRICS}
    figures = {name: svg for s in sections.values() for name, svg in s.figures.items()}
    text = render(runs, sections).replace(f"]({FIGURES}/", f"]({figures_dir}/")
    return text, figures


def write_report(runs: Runs, path: Path = REPORT) -> None:
    """Отчёт в `path`, картинки — в каталог его имени рядом: короткий прогон в другой файл не
    затирает картинки основного отчёта."""
    text, figures = build(runs, path.stem)
    path.write_text(text, encoding="utf-8")
    directory = path.parent / path.stem
    directory.mkdir(exist_ok=True)
    for name, svg in sorted(figures.items()):
        (directory / name).write_text(svg, encoding="utf-8")
