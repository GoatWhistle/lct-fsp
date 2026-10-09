"""Команды стенда: замеры на синтетическом рынке и отчёты таблицами Markdown.

- `report` — прогон D1 и D2 по сидам плана и отчёт `docs/validation-report.md`
  (`validation.report`);
- `report_honesty` — честность погрешности уровня и стабильность грейда при повторе на прогретом
  банке D1;
- `tune_inflation` — подбор поправки погрешности `level_sd_inflation` на настроечном наборе D3
  по правилу плана валидации;
- `report_parsing` — M21, точность разбора потребности из текста по полям на размеченном наборе:
  правилами или моделью из записи её ответов (`validation.recorded`);
- `write_market` — синтетический рынок D1 или D2 файлами: истина, наблюдаемое, потребности и
  эталон пар (`validation.population`);
- `b3` — пары B3 по наборам: сколько вызовов модели и во что обойдётся живой прогон, а с
  `--record` — сам прогон с записью ответов в кэш (`validation.baselines`).

Прогоны специализаций идут в пуле процессов; каждый процесс собирает свой стенд из seed прогона.
"""

import argparse
import logging
import os
import statistics
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from app.adapter.catalog_file import load_catalog
from app.adapter.text_llama import LlamaCompletion
from app.adapter.text_model import ModelError, ModelRequest
from app.adapter.text_rules import load_synonyms
from app.domain.determination import grades_by_threshold
from composition import model_understanding, named_completion
from settings import CATALOG_FILE, MECHANICS_FILE, SYNONYMS_FILE, Mechanics, Settings
from validation.baselines import B3_SYSTEM, Document, LlmRanker, ScoreCache, record
from validation.isolated import IsolatedCompletion
from validation.main import B3_DIR, b3_cache_path, baseline_source, build_stand, catalog
from validation.market import (
    SEED,
    TUNING_SEED,
    WARM_RESPONSES,
    Market,
    market,
    true_grade,
    warm,
)
from validation.metrics import cohen_kappa, median, pearson
from validation.parsing import LabeledText, load_labeled, parsing_table, run_parsing
from validation.population import DATASETS, Generator, GeneratorParams, write
from validation.recorded import Recording, Replay
from validation.recorded import record as record_model
from validation.report import (
    PLAN_SCALE,
    REPORT,
    SETS,
    baseline_pairs,
    collect,
    prepared,
    write_d4,
    write_report,
)
from validation.simulate import Scale

# Набор D5 — тексты вакансий с разметкой; формат — validation/data/need_texts.md.
DATA_DIR = Path(__file__).resolve().parent / "data"
D5_FILE = DATA_DIR / "d5_need_texts.yaml"
# Записи ответов моделей для M21: `<набор>.<модель>.json`.
RECORDED_DIR = DATA_DIR / "recorded"
# Таймаут модели в отчёте — как у прода по умолчанию; запись идёт с запасом, без отката.
MODEL_TIMEOUT = Settings.model_fields["text_understanding_timeout_seconds"].default
RECORD_TIMEOUT = 600.0

# Каталог наборов D1 и D2: файлы воспроизводятся по seed и в репо не хранятся.
MARKET_DIR = DATA_DIR / "market"

# Сетка подбора поправки погрешности κ — шаг 0,05.
INFLATION_GRID = tuple(round(1 + 0.05 * i, 2) for i in range(11))


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
        run = m.attempt(c)
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
    """Каждое определение пары — новый кандидат с той же истиной: повтор первичного определения,
    а не смена грейда, и прошлых показов у него нет."""
    grades: list[str | None] = [None, *grades_by_threshold(m.mechanics.grade_thresholds)]
    rank = {g: i for i, g in enumerate(grades)}
    results: list[tuple[str | None, str | None]] = []
    levels: list[tuple[float, float]] = []
    over = exact = both_true = 0
    for _ in range(pairs):
        c = m.candidate()
        truth = rank[true_grade(m, c)]
        one, two = m.determine(c), m.determine(c)
        first, second = one.grade, two.grade
        results.append((first, second))
        levels.append((one.overall.mean, two.overall.mean))
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
    specializations = [s.code for s in load_catalog(CATALOG_FILE).specializations]
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
    specializations = [s.code for s in load_catalog(CATALOG_FILE).specializations]
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


def recording_path(dataset: Path, model: str) -> Path:
    return RECORDED_DIR / f"{dataset.stem}.{model}.json"


class _Capture:
    """`Completion`, который только запоминает запросы и отвечает сбоем: так стенд узнаёт, о чём
    сценарий спросит модель, не повторяя сборку запроса."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> str:
        self.requests.append(request)
        raise ModelError("запрос записан")


def _record(
    mechanics: Mechanics, labeled: list[LabeledText], model: str, recording: Recording, workers: int
) -> None:
    synonyms = load_synonyms(SYNONYMS_FILE)
    capture = _Capture()
    understanding = model_understanding(capture, synonyms, timeout=RECORD_TIMEOUT)
    capturing = build_stand(mechanics, understanding=understanding).need_drafts()
    for item in labeled:
        capturing.parse(item.text)
    settings = Settings()
    live = (
        LlamaCompletion(settings.llama_url, settings.llama_model, RECORD_TIMEOUT)
        if model == "llama"
        else named_completion(model, RECORD_TIMEOUT)
    )
    added = record_model(
        recording, capture.requests, live, workers=workers, model=getattr(live, "model", None)
    )
    print(f"Записано ответов модели: {added}, файл {recording.path.name}\n")


def report_parsing(
    mechanics: Mechanics,
    dataset: Path,
    model: str | None = None,
    *,
    timeout: float = MODEL_TIMEOUT,
    record_workers: int = 0,
) -> None:
    """M21 по набору `dataset` — тем же сценарием разбора, что HTTP: правилами или моделью
    `model` с откатом на правила, как в проде. Модель отвечает из записи; `record_workers` —
    сначала дописать в запись недостающие ответы, спросив модель столькими потоками."""
    if not dataset.exists():
        raise SystemExit(f"нет набора {dataset}: формат — validation/data/need_texts.md")
    labeled = load_labeled(dataset)
    print(f"## M21 — разбор потребности: {dataset.name}, текстов {len(labeled)}\n")
    if model is None:
        print("Разбор: правила и словарь синонимов.\n")
        print(parsing_table(run_parsing(labeled, build_stand(mechanics).need_drafts().parse)))
    else:
        recording = Recording(recording_path(dataset, model))
        if record_workers:
            _record(mechanics, labeled, model, recording, record_workers)
        if not recording.answers:
            raise SystemExit(f"нет записи {recording.path}: запустите с --record")
        replay = Replay(recording, timeout)
        understanding = model_understanding(replay, load_synonyms(SYNONYMS_FILE), timeout=timeout)
        drafts = build_stand(mechanics, understanding=understanding).need_drafts()
        report = run_parsing(labeled, drafts.parse, replay.take_ms)
        if replay.missing:
            raise SystemExit(
                f"в {recording.path.name} нет ответов на {replay.missing} текстов: запрос "
                "изменился или запись неполная — допишите её с --record"
            )
        print(
            f"Разбор: модель {recording.model or model} из записи {recording.path.name}, "
            f"таймаут {timeout:g} с, откат на правила — {replay.failed} из {len(labeled)}.\n"
        )
        print(parsing_table(report))
    if any(t.checked_by == "model" for t in labeled):
        print(
            "\nРазметка набора — модели, без проверки человеком: её ошибки сдвигают точность в "
            "неизвестную сторону (docs/validation-plan.md, M21)."
        )


# Цена Claude Sonnet 5.5, $ за миллион токенов: вход и выход.
B3_PRICE = (2.0, 10.0)
# Прикидка токенов на пару: текст запроса — символов на токен для русского текста; Agent SDK —
# два хода модели на пару (ответ и структурированный вывод), на каждый — инструкция вывода и схема
# сверх запроса и короткий ответ.
CHARS_PER_TOKEN = 2.5
TURNS = 2
TURN_OVERHEAD_TOKENS = 400
TURN_OUTPUT_TOKENS = 60


def b3_pairs(
    mechanics: Mechanics, name: str
) -> tuple[GeneratorParams, list[tuple[Document, Document]], Counter[str]]:
    """Пары B3 набора `name` по плану и сколько их по видам: пул, двойники M3, двойники M5."""
    known = catalog()
    dataset, doubles = prepared(name, mechanics, PLAN_SCALE, tuple(known.specializations), known)
    kinds = {str(tw.id): tw.kind.value for tw in doubles}
    found, counts = [], Counter[str]()
    for pairs in baseline_pairs(dataset, doubles, known).values():
        for _, _, need, resume in pairs:
            found.append((need, resume))
            counts[kinds.get(resume.key, "pool")] += 1
    return dataset.params, found, counts


def b3(mechanics: Mechanics, sets: Sequence[str], record_workers: int, model: str) -> None:
    """Без `record_workers` — только подсчёт: живой прогон B3 запускается после согласия команды
    на число вызовов и стоимость."""
    total_in = total_out = 0.0
    print("| Набор | Пул | Двойники M3 | Двойники M5 | Всего | Уже в кэше |")
    print("|---|---|---|---|---|---|")
    plans = {}
    for name in sets:
        params, pairs, counts = b3_pairs(mechanics, name)
        cache = ScoreCache(b3_cache_path(B3_DIR, name), params.seed)
        ranker = LlmRanker(cache)
        cached = sum(ranker.cached(n, r) for n, r in pairs)
        plans[name] = (ranker, pairs)
        chars = sum(len(B3_SYSTEM) + len(n.text) + len(r.text) + 20 for n, r in pairs)
        # Каждый ход заново получает весь запрос.
        total_in += TURNS * (chars / CHARS_PER_TOKEN + TURN_OVERHEAD_TOKENS * len(pairs))
        total_out += TURNS * TURN_OUTPUT_TOKENS * len(pairs)
        print(
            f"| {name.upper()} | {counts['pool']} | {counts['m3']} | {counts['m5']} | "
            f"{len(pairs)} | {cached} |"
        )
    cost = (total_in * B3_PRICE[0] + total_out * B3_PRICE[1]) / 1e6
    print(
        f"\nПрикидка: входных токенов {total_in / 1e6:.1f} млн, выходных {total_out / 1e6:.1f} млн "
        f"— около ${cost:,.0f} по цене Sonnet 5.5 (${B3_PRICE[0]:g} / ${B3_PRICE[1]:g} за "
        "миллион). Без кэша промпта; кэш системного промпта прикидку снижает."
    )
    if not record_workers:
        return
    # Каждый поток — свой процесс CLI со своим конфигом: общий конфиг пользователя параллельные
    # вызовы портят (`validation.isolated`).
    model_id = getattr(named_completion(model, RECORD_TIMEOUT), "model", None)
    live = IsolatedCompletion(model, RECORD_TIMEOUT, record_workers, model_id)
    try:
        for name, (ranker, pairs) in plans.items():
            ranker = LlmRanker(ranker.cache, live)

            def progress(done: int, total: int, name: str = name) -> None:
                if done % 500 == 0 or done == total:
                    print(f"{name.upper()}: {done} из {total}", flush=True)

            added, failed = record(ranker, pairs, workers=record_workers, progress=progress)
            print(f"{name.upper()}: записано {added}, сбоев {failed} → {ranker.cache.path.name}")
    finally:
        live.close()


def write_market(
    mechanics: Mechanics, name: str, seed: int | None, candidates: int | None, out: Path
) -> None:
    """Набор `name` в `out/<name>`; `seed` и `candidates` (на специализацию) — вместо плановых."""
    params = DATASETS[name]
    if seed is not None:
        params = replace(params, seed=seed)
    if candidates is not None:
        params = replace(params, candidates_per_specialization=candidates)
    known = catalog()
    dataset = Generator(params, mechanics, known).generate()
    directory = out / name
    write(dataset, directory, known, mechanics)
    print(
        f"{name}: сид {params.seed}, кандидатов {len(dataset.truths)}, работодателей "
        f"{len(dataset.employers)}, потребностей {len(dataset.needs)} → {directory}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m validation")
    parser.add_argument(
        "command", nargs="?", choices=("report", "honesty", "tune", "parsing", "market", "b3")
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="сид для honesty и market, по умолчанию плановый"
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=None,
        help="кандидатов: для honesty и tune — тестов (1500), для market и report — на "
        "специализацию (600)",
    )
    parser.add_argument("--set", choices=sorted(DATASETS), default="d1", help="набор для market")
    parser.add_argument("--out", type=Path, default=MARKET_DIR, help="каталог наборов market")
    parser.add_argument(
        "--pairs", type=int, default=None, help="пар повтора: honesty — 1500, report — 200"
    )
    parser.add_argument(
        "--warm", type=int, default=None, help="report: ответов на семейство в прогреве (500)"
    )
    parser.add_argument(
        "--compare", type=int, default=None, help="report: кандидатов сравнения M13 (300)"
    )
    parser.add_argument(
        "--fit",
        type=int,
        default=None,
        help="report: честных кандидатов M21 на специализацию (200)",
    )
    parser.add_argument("--report", type=Path, default=REPORT, help="report: куда писать отчёт")
    parser.add_argument(
        "--model",
        help="для parsing: модель разбора по имени, как TEXT_UNDERSTANDING; без него — правила; "
        "для b3 — модель B3 по имени, по умолчанию agent_sdk",
    )
    parser.add_argument(
        "--record",
        type=int,
        default=0,
        metavar="N",
        help="для parsing с --model: дописать недостающие ответы модели в запись, N потоков; "
        "для b3 — спросить модель о парах без ответа в кэше, N потоков",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=MODEL_TIMEOUT,
        help="для parsing с --model: таймаут модели, после которого отвечают правила",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=D5_FILE,
        help="размеченные тексты для parsing, по умолчанию D5",
    )
    args = parser.parse_args()
    # Предупреждения сценариев о потолке показов и выводе семейств из выдачи на тысячах попыток
    # забили бы отчёт: сверх потолка стенд считает сам, в таблице.
    logging.basicConfig(level=logging.ERROR)
    mechanics = Mechanics.from_yaml(MECHANICS_FILE)
    match args.command:
        case "honesty":
            report_honesty(
                mechanics,
                SEED if args.seed is None else args.seed,
                1500 if args.candidates is None else args.candidates,
                1500 if args.pairs is None else args.pairs,
            )
        case "tune":
            tune_inflation(mechanics, 1500 if args.candidates is None else args.candidates)
        case "parsing":
            report_parsing(
                mechanics,
                args.dataset,
                args.model,
                timeout=args.timeout,
                record_workers=args.record,
            )
        case "market":
            write_market(mechanics, args.set, args.seed, args.candidates, args.out)
        case "b3":
            b3(mechanics, SETS, args.record, args.model or "agent_sdk")
        case _:
            scale = Scale(
                **{
                    k: v
                    for k, v in (
                        ("pairs", args.pairs),
                        ("warm", args.warm),
                        ("compare", args.compare),
                        ("fit", args.fit),
                        ("candidates", args.candidates),
                    )
                    if v is not None
                }
            )
            # Кэш B3 — пары прогона по плану: у короткого прогона другие пулы и двойники.
            b3_dir = B3_DIR if scale == PLAN_SCALE else None
            runs = collect(mechanics, scale, baselines=baseline_source(b3_dir=b3_dir))
            if scale == PLAN_SCALE and write_d4(runs):
                print("выборка D4 и форма разметки → validation/data/d4/")
            write_report(runs, args.report)
            print(f"отчёт → {args.report}")
