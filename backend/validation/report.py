"""Отчёт стенда валидации одной командой (docs/validation-plan.md, правило 7): прогон D1 и D2 по
сидам плана и `docs/validation-report.md` — по каждой метрике плана определение, значение на D1
и D2 рядом, порог и вердикт; не посчитанные здесь — «ожидает данных».

Прогон — `collect`: задачи `validation.simulate` в пуле процессов, по задаче на специализацию
набора. Метрики — здесь: только этот код соединяет записанное платформой со скрытой истиной
набора. Раздел метрики — функция `Runs → Section` под декоратором `section`: новый раздел
добавляется своей функцией, остальные не правятся. Первыми в отчёте — M9 и M10, их жюри
проверит руками, дальше — по номерам плана.
"""

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
from app.domain.selection import NeedSnapshot
from app.usecase.skill_profile import specialization_prior
from settings import BACKEND_DIR, Mechanics
from validation.figures import Curve, CurvePanel, Panel, Series, curves_svg, reliability_svg
from validation.llm_attack import CLAIMED
from validation.main import Catalog, catalog
from validation.metrics import (
    cohen_kappa,
    ece,
    ndcg_at,
    pearson,
    point_biserial,
    precision_at,
    reliability,
)
from validation.population import DATASETS, Dataset, Generator, Pair, label, snapshot
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
    flagged_share,
    rank_of,
    run_protection,
    summarize,
    tune_threshold,
)
from validation.recorded import Recording
from validation.simulate import Adaptivity, Job, Outcome, Scale, SpecRun, run_cold, run_spec
from validation.truth import CandidateTruth, Persona

DOCS = BACKEND_DIR.parent / "docs"
REPORT = DOCS / "validation-report.md"
# Картинки отчёта — рядом с ним, в каталоге его имени.
FIGURES = "validation-report"
PLAN = "validation-plan.md"
SETS = ("d1", "d2")
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
    "M3": "нет базовых линий B1–B3 и двойников-накрутчиков",
    "M5": "нет двойников по защищённым признакам и базовых линий B2, B3",
    "M6": "нет рыночной симуляции приглашений",
    "M7": "нет модели принятия и отложенной синтетики",
    "M8": "нет проверки вкладов объяснений на выдачах стенда",
    "M14": "прогон без экспериментов защиты",
    "M15": "прогон без экспериментов защиты",
    "M16": "прогон без экспериментов защиты",
    "M17": "прогон без экспериментов защиты",
    "M18": "нет набора D6",
    "M20": "нет ручной разметки D4 — ожидает разметки",
    "M21": "RMSD семейств на банке с испорченными семействами не считается; точность разбора "
    "потребности на D5 — команда `parsing`, в отчёт не сведена",
    "M22": "нет прогона l_z попытки; разбор резюме — нет набора D6",
    "M23": "нет замера времени подборки на 1000 кандидатах",
}

PASSED = "выполнен"
FAILED = "не выполнен"
WAITING = "ожидает данных"


@dataclass(frozen=True)
class DatasetRuns:
    """Набор и всё, что по нему записала платформа: κ из конфига и κ = 1 (до поправки)."""

    dataset: Dataset
    runs: dict[str, SpecRun]
    before: dict[str, SpecRun]
    cold: dict[str, Adaptivity]
    # (потребность, кандидат) → эталон из истины.
    pairs: dict[tuple[uuid.UUID, uuid.UUID], Pair]
    # Эксперименты защиты по специализациям (M14–M17); пусто — прогон без них.
    protection: dict[str, ProtectionRun] = field(default_factory=dict)

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
    futures: dict[
        tuple[str, str, str], Future[SpecRun] | Future[Adaptivity] | Future[ProtectionRun]
    ] = {}
    with ProcessPoolExecutor(workers or max(1, (os.cpu_count() or 2) - 1)) as pool:
        for name in sets:
            params = DATASETS[name]
            if scale.candidates is not None:
                params = replace(params, candidates_per_specialization=scale.candidates)
            dataset = generated[name] = Generator(params, mechanics, known).generate()
            stacks = {o.id: frozenset(o.stack) for o in dataset.observed}
            for code in codes:
                job = Job(
                    DATASETS[name],
                    code,
                    mechanics,
                    scale,
                    tuple(t for t in dataset.truths if t.specialization == code),
                    tuple(n for n in dataset.needs if n.form.specialization == code),
                    stacks,
                )
                futures[name, code, "runs"] = pool.submit(run_spec, job)
                light = replace(job, mechanics=before, full=False)
                futures[name, code, "before"] = pool.submit(run_spec, light)
                futures[name, code, "cold"] = pool.submit(run_cold, job)
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
        found[name] = DatasetRuns(
            dataset,
            part(name, "runs"),
            part(name, "before"),
            part(name, "cold"),
            pairs,
            part(name, "protection") if protection is not None else {},
        )
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


def ranked_lists(
    data: DatasetRuns, *, naive: bool = False
) -> Iterable[tuple[str, list[int], list[int]]]:
    """По потребности: градации эталона в порядке нашей выдачи (точная категория, близкие,
    нижний блок, затем остальные пула по id) или B0 (весь пул по доле верных) и градации всего
    пула."""
    for run in data.runs.values():
        pool = sorted(run.outcomes)
        for need, order_ in run.rankings.items():
            if naive:
                ranked = sorted(pool, key=lambda c: (-run.outcomes[c].naive[0], c))
            else:
                listed = set(order_)
                ranked = [*order_, *(c for c in pool if c not in listed)]
            yield (
                run.specialization,
                [data.pairs[need, c].grade for c in ranked],
                [data.pairs[need, c].grade for c in pool],
            )


@dataclass(frozen=True)
class Ranking:
    precision: float
    ndcg: float


def ranking_quality(
    data: DatasetRuns, specialization: str | None = None, *, naive: bool = False
) -> Ranking:
    lists = [
        (ranked, pool)
        for code, ranked, pool in ranked_lists(data, naive=naive)
        if specialization in (None, code)
    ]
    ndcg = [ndcg_at(r, p, TOP) for r, p in lists]
    return Ranking(
        mean(precision_at(r, TOP) for r, _ in lists),
        mean(ndcg),
    )


def _ranking_section(runs: Runs, metric: str, attr: str, threshold: float, margin: str) -> Section:
    header = ["Специализация"]
    for name in runs.sets:
        header += [name.upper(), f"B0 {name.upper()}"]
    rows = []
    for code in (*runs.specializations, None):
        row = [runs.catalog.specializations[code].name if code else "**Все потребности**"]
        for data in runs.sets.values():
            row += [
                f(getattr(ranking_quality(data, code), attr)),
                f(getattr(ranking_quality(data, code, naive=True), attr)),
            ]
        rows.append(row)
    verdicts, text = {}, {}
    for name, data in runs.sets.items():
        ok = getattr(ranking_quality(data), attr) >= threshold
        verdicts[name] = WAITING if ok else FAILED
        text[name] = (
            f"абсолютная часть {'выполнена' if ok else 'не выполнена'}, сравнительная — {WAITING}"
        )
    needs = sum(len(r.rankings) for r in next(iter(runs.sets.values())).runs.values())
    body = (
        f"Порог: не ниже {f(threshold, 2)} и не ниже лучшей из B1–B3 плюс {margin}. Сравнительная "
        "часть ждёт базовых линий B1–B3. Выдача — подборка платформы по потребности набора: "
        "точная категория по скору, затем «близкие» и нижний блок, затем остальные кандидаты "
        "пула. Пул потребности — все кандидаты набора её специализации, включая "
        f"персонажей-атакующих; эталон — градация rel из истины. Потребностей в наборе: {needs}. "
        "B0 ранжирует весь пул по доле верных наивного теста — для ориентира, в порог не входит."
        "\n\n" + table(header, rows) + naive_note(runs, attr)
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
        if getattr(ranking_quality(data, naive=True), attr) > getattr(ranking_quality(data), attr)
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
        "цена отсечения по категории при консервативном грейде, а не скора внутри категории; "
        "разделят вклад отсечения и скора базовые линии внутри наших категорий (план, «Пул и "
        "выдача»)."
    )


@section("M1")
def m1(runs: Runs) -> Section:
    return _ranking_section(runs, "M1", "precision", 0.70, "0,15")


@section("M2")
def m2(runs: Runs) -> Section:
    return _ranking_section(runs, "M2", "ndcg", 0.75, "0,10")


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
        "при 30 % и ρ = 0,5.\n\n" + "\n\n".join(parts)
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
        tpr = flagged_share(leaked, h, window_leak)
        fpr = flagged_share(honest, h, window_honest)
        verdicts[name] = verdict_of([tpr >= 0.80, fpr <= 0.05])
        rows = [
            [
                runs.catalog.specializations[run.specialization].name,
                f(flagged_share([d for d in run.leak_drift if d.leaked], h, window_leak), 2),
                str(sum(d.leaked for d in run.leak_drift)),
                f(flagged_share(run.honest_drift, h, window_honest), 3),
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
                [["FPR на D3", *(f(flagged_share(honest_d3, g, window_honest), 3) for g in grid)]],
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
        "Цифры — как есть, без порога: истинного уровня у модели нет."
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


# --- M19 ---------------------------------------------------------------------------------------


@section("M19")
def m19(runs: Runs) -> Section:
    if not {"d1", "d2"} <= set(runs.sets):
        return Section("M19", "Нужны оба набора, D1 и D2.", WAITING)
    d1, d2 = runs.sets["d1"], runs.sets["d2"]
    ndcg = ranking_quality(d1).ndcg, ranking_quality(d2).ndcg
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
        for m in ("M1", "M2", "M4", "M9", "M10", "M14", "M15")
    }
    failed = [m for m, v in shifted.items() if v == FAILED]
    rows += [[f"Порог {m} на D2", "", "", "", mark(v != FAILED)] for m, v in shifted.items()]
    body = (
        "Порог: пороги метрик M1–M4, M9, M10, M14, M15 выполняются и на D2; относительная "
        "деградация nDCG@10 и точного совпадения грейда не больше 20 %. M1 и M2 на D2 — по "
        "абсолютной части порога; M3 ждёт данных.\n\n"
        + table(["Показатель", "D1", "D2", "Деградация", "Выполнено"], rows)
    )
    if failed or not all(ok):
        reasons = [*(f"порог {m} на D2" for m in failed)]
        reasons += ["деградация больше 20 %"] if not all(ok) else []
        return Section("M19", body, f"{FAILED}: {', '.join(reasons)}")
    waiting = ["M3", *(m for m, v in shifted.items() if v == WAITING)]
    return Section("M19", body, f"{WAITING}: {', '.join(waiting)}")


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
    parts = []
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
