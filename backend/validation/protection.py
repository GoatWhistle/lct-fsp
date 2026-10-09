"""Эксперименты защиты теста на стенде (docs/validation-plan.md, M14–M17): атака утечкой по трём
схемам теста, детектор утечки, LLM-помощник персонажем набора и проверочный блок у честных.

Задача — одна специализация набора: банк прогревается на честных кандидатах набора до
`calibration_refit_min_responses` и дальше, затем заморожен; каждое условие эксперимента идёт на
своей копии прогретого банка (`Market.fork`) — утечка одного условия не трогает другое. Схема S3
— наш тест целиком: определение с каскадом, детектор дрейфа на замороженном банке, флаги и
проверочный блок, — через те же сценарии, что HTTP. S1 и S2 — базовые линии плана на том же
банке без сценариев теста.

Детектор утечки (M15) меряется на потоке попыток без порога: стенд читает записанные ответы на
семейство и считает CUSUM той же функцией, что адаптер детектора, от тех же опорных параметров и
связки. Пик CUSUM в окне ответов говорит, сработал бы детектор при любом пороге, — по нему
порог подбирается на D3 и TPR и FPR считаются на D1 и D2.

Истину знает только эта часть стенда: какие семейства слиты, кто читер. Сценарии видят ответы.
"""

import math
import random
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from app.adapter.code_runner import InProcessCodeRunner
from app.domain.bank import get_family
from app.domain.calibration import Parameters
from app.domain.determination import grade_probabilities, grades_by_threshold
from app.domain.protection import cusum_step
from app.domain.skill import Normal, Observation
from app.repository.memory.attempt import FAMILY_PRESENTATIONS
from settings import Mechanics
from validation.llm_attack import ATTEMPTS, SPECIALIZATIONS, Answering, LlmAttempt, run_attempts
from validation.main import catalog
from validation.market import TUNING_SEED, Market, mean_responses
from validation.population import D1, Generator, GeneratorParams, as_candidate
from validation.recorded import Answer
from validation.simulate import Determined, naive_cutoffs, warm_source
from validation.truth import CandidateTruth, Persona, guessing, respond

# Доли слитого банка и прибавка читера на свежем экземпляре слитого семейства (M14).
LEAKS = (0.1, 0.3, 0.5)
RHOS = (0.25, 0.5, 0.75)
MAIN_LEAK, MAIN_RHO = 0.3, 0.5
# Доля читеров в потоке попыток (M14, M15).
CHEATER_SHARE = 0.2
SCHEMES = ("S1", "S2", "S3")
RUNNER = InProcessCodeRunner()
# Настроечный набор: сид плана, только честные кандидаты, модель ответа D1.
D3 = replace(D1, name="d3", seed=TUNING_SEED, persona_shares=((Persona.honest, 1.0),))


@dataclass(frozen=True)
class ProtectionScale:
    """Размер экспериментов. По умолчанию — план: 2000 попыток M14 с 20 % читеров — по 80
    читеров на специализацию; окна M15 — 300 ответов на слитое семейство после утечки и 1000
    на семейство у честных."""

    cheaters: int = 80
    leak_responses: int = 300
    honest_responses: int = 1000
    # Потолок попыток потока M15: редко выбираемые семейства окна могут не набрать.
    max_attempts: int = 6000
    # Ответов на семейство в прогреве банка.
    warm: int = 500
    # LLM-помощников набора на специализацию; None — все.
    helpers: int | None = None


@dataclass(frozen=True)
class Twins:
    """Читер и два честных прохождения той же истины: двойник и повтор двойника. Грейд — итог
    схемы: категория после проверочного блока у S3, грейд по правилу схемы у S1 и S2."""

    cheater: Determined
    honest: Determined
    again: Determined


@dataclass(frozen=True)
class Attack:
    scheme: str
    leak: float
    rho: float
    twins: tuple[Twins, ...]


@dataclass(frozen=True)
class Drift:
    """Пик CUSUM семейства в окне ответов и сколько ответов в окне набралось."""

    family: str
    leaked: bool
    peak: float
    responses: int


@dataclass(frozen=True)
class Helper:
    """LLM-помощник (M16 а): истинный грейд, грейд результата до проверочного блока, помечен ли
    результат, категория после блока."""

    truth: str | None
    before: str | None
    flagged: bool
    after: str | None


@dataclass(frozen=True)
class HonestBlocks:
    """Проверочный блок у честных (M17): определений, из них с блоком и с расхождением."""

    attempts: int
    blocks: int
    mismatches: int


@dataclass(frozen=True)
class EarlyLeak:
    """Утечка до калибровки: слитых и прочих семейств и сколько из них сверка с экспертной
    сложностью вывела из выдачи после прогрева с читерами."""

    leaked: int
    leaked_caught: int
    clean: int
    clean_caught: int


@dataclass(frozen=True)
class ProtectionRun:
    dataset: str
    specialization: str
    attacks: tuple[Attack, ...] = ()
    # Поток с утечкой — окно `leak_responses` после утечки; честный поток — `honest_responses`.
    leak_drift: tuple[Drift, ...] = ()
    honest_drift: tuple[Drift, ...] = ()
    # M16 а: помощник доступен и в блоке; в блоке помощи нет.
    helpers: tuple[Helper, ...] = ()
    helpers_offline: tuple[Helper, ...] = ()
    honest_blocks: HonestBlocks = field(default_factory=lambda: HonestBlocks(0, 0, 0))
    early: EarlyLeak | None = None
    # M16 б, D7: попытки модели из записи ответов; заданий, ответа на которые в записи нет.
    llm: tuple[LlmAttempt, ...] = ()
    llm_missing: int = 0
    llm_model: str | None = None


@dataclass(frozen=True)
class ProtectionJob:
    params: GeneratorParams
    specialization: str
    mechanics: Mechanics
    scale: ProtectionScale
    # LLM-помощники набора этой специализации.
    helpers: tuple[CandidateTruth, ...] = ()
    # Полный прогон; иначе — только честный поток детектора (подбор порога на D3).
    full: bool = True
    # Запись ответов модели D7 по ключу запроса — у D1 специализаций D7; None — нет записи.
    llm_answers: dict[str, Answer] | None = None
    llm_model: str | None = None


def run_protection(job: ProtectionJob) -> ProtectionRun:
    """Задача пула процессов: эксперименты специализации набора — см. описание модуля."""
    params, code, mechanics, scale = job.params, job.specialization, job.mechanics, job.scale
    m = warmed(params, code, mechanics, scale.warm)
    llm: list[LlmAttempt] = []
    missing = 0
    if job.llm_answers is not None and code in SPECIALIZATIONS:
        # Первым, на нетронутом прогретом банке: так же, как при записи.
        answering = Answering(job.llm_answers)
        llm = run_attempts(m, code, range(ATTEMPTS), answering)
        missing = answering.missing
    generator = Generator(params, mechanics, catalog())
    rng = generator.rng(f"protection:{code}")

    def honest() -> CandidateTruth:
        return generator.truth(code, Persona.honest, rng)

    honest_drift = drift_stream(
        m.fork(_seed(params, code, "honest-stream")),
        honest,
        leaked=frozenset(),
        window=scale.honest_responses,
        max_attempts=scale.max_attempts,
    )
    if not job.full:
        return ProtectionRun(params.name, code, honest_drift=honest_drift)

    families = [f.code for f in m.families]
    leaks = {
        share: frozenset(rng.sample(families, round(share * len(families)))) for share in LEAKS
    }
    conditions = [(leak, MAIN_RHO) for leak in LEAKS] + [
        (MAIN_LEAK, rho) for rho in RHOS if rho != MAIN_RHO
    ]
    truths = [honest() for _ in range(scale.cheaters)]
    attacks: list[Attack] = []
    blocks = HonestBlocks(0, 0, 0)
    for leak, rho in conditions:
        leaked = leaks[leak]
        attacks.append(Attack("S1", leak, rho, fixed_common(m, truths, leak, rho, items=True)))
        attacks.append(Attack("S2", leak, rho, fixed_common(m, truths, leak, rho, leaked=leaked)))
        fork = m.fork(_seed(params, code, f"s3:{leak}:{rho}"))
        fork.response_model = replace(fork.response_model, leak_rho=rho)
        twins, found = adaptive(fork, truths, leaked, honest)
        attacks.append(Attack("S3", leak, rho, twins))
        if (leak, rho) == (MAIN_LEAK, MAIN_RHO):
            blocks = found

    leak_fork = m.fork(_seed(params, code, "leak-stream"))
    leak_fork.response_model = replace(leak_fork.response_model, leak_rho=MAIN_RHO)
    leak_drift = drift_stream(
        leak_fork,
        honest,
        leaked=leaks[MAIN_LEAK],
        window=scale.leak_responses,
        max_attempts=scale.max_attempts,
    )

    helpers = list(job.helpers[: scale.helpers] if scale.helpers is not None else job.helpers)
    with_help = m.fork(_seed(params, code, "helpers"))
    offline = m.fork(_seed(params, code, "helpers"))
    return ProtectionRun(
        params.name,
        code,
        tuple(attacks),
        leak_drift,
        honest_drift,
        tuple(helper_runs(with_help, helpers, block_help=True)),
        tuple(helper_runs(offline, helpers, block_help=False)),
        blocks,
        early_leak(params, code, mechanics, scale.warm, generator),
        tuple(llm),
        missing,
        job.llm_model if llm else None,
    )


def warmed(params: GeneratorParams, code: str, mechanics: Mechanics, responses: int) -> Market:
    """Банк, прогретый честными кандидатами набора до `responses` ответов на семейство, —
    заморожен, детектор дрейфа ведётся. Прогрев идёт без детектора: утечка в плане — после
    разогрева, и детектор начинает с прогретого банка. Иначе порог детектора менял бы сам банк,
    на котором его подбирают, и путь теста D7, записанный по ответам модели."""
    quiet = mechanics.model_copy(update={"drift_cusum_h": math.inf})
    m = Market(code, quiet, params.seed, params.response)
    source = warm_source(params, code, quiet)
    while mean_responses(m) < responses:
        m.attempt(source())
    m.calibrate = False
    warm = m.fork(_seed(params, code, "warmed"), mechanics)
    warm.watch = True
    return warm


def _seed(params: GeneratorParams, code: str, stream: str) -> int:
    return random.Random(f"{params.seed}:{code}:{stream}").getrandbits(32)


def _cheater(truth: CandidateTruth, leaked: frozenset[str]) -> CandidateTruth:
    return replace(truth, persona=Persona.bank_leak, leaked=leaked)


# --- M14: схемы S1 и S2 ------------------------------------------------------------------------


def fixed_common(
    m: Market,
    truths: Sequence[CandidateTruth],
    leak: float,
    rho: float,
    *,
    items: bool = False,
    leaked: frozenset[str] = frozenset(),
) -> tuple[Twins, ...]:
    """Общий бланк семейств с тем же покрытием тем, что у M13. `items` — S1: одни экземпляры у
    всех, слита доля `leak` заданий, грейд — по доле верных с отсечками B0. Иначе — S2: свой
    экземпляр у каждого, слиты семейства `leaked`, грейд — правилом уверенности по оценке IRT.
    Банк — тот же прогретый, ответы не калибруют его."""
    mechanics = m.mechanics
    blank = list(m.fixed(as_candidate(truths[0]), mechanics.test_max_items, target=0.0).shown)
    params = m.parameters()
    model = replace(m.response_model, leak_rho=rho)
    rng = random.Random(f"{m.seed}:{m.specialization}:{'S1' if items else 'S2'}:{leak}:{rho}")
    shared = {code: get_family(code).instance(i, RUNNER) for i, code in enumerate(blank)}
    leaked_items = frozenset(rng.sample(blank, round(leak * len(blank)))) if items else frozenset()
    cutoffs = naive_cutoffs(m, blank)
    grades = grades_by_threshold(mechanics.grade_thresholds)

    def take(truth: CandidateTruth) -> Determined:
        answers = []
        for code in blank:
            family = get_family(code)
            instance = shared[code] if items else None
            guess = guessing(instance, model) if instance is not None else m.guess_of(code)
            reply = respond(
                truth,
                code,
                family.topic,
                m.truth[code],
                guess,
                model,
                rng,
                leaked_instance=items
                and truth.persona == Persona.bank_leak
                and code in leaked_items,
            )
            p = params[code]
            answers.append(Observation(family.topic, reply.correct, p.discrimination, p.difficulty))
        overall = m.stand.skill_model.estimate(m.prior, answers).overall()
        if items:
            share = sum(a.correct for a in answers) / len(answers)
            passed = [g for g in grades if share >= cutoffs[g]]
        else:
            probabilities = grade_probabilities(overall, mechanics.grade_thresholds)
            passed = [g for g in grades if probabilities[g] >= mechanics.grade_confidence]
        return Determined(passed[-1] if passed else None, overall)

    return tuple(
        Twins(
            take(_cheater(t, frozenset() if items else leaked)),
            take(t),
            take(t),
        )
        for t in truths
    )


# --- M14 S3 и M17: наш тест --------------------------------------------------------------------


def adaptive(
    m: Market,
    truths: Sequence[CandidateTruth],
    leaked: frozenset[str],
    honest: Callable[[], CandidateTruth],
) -> tuple[tuple[Twins, ...], HonestBlocks]:
    """S3 — поток определений: на каждого читера — честный двойник, повтор двойника и два
    честных попутчика, читеров в потоке 20 %. Детектор дрейфа ведётся по всему потоку; результат
    читера, как и честного, — категория после проверочного блока. Честные определения потока —
    заодно M17."""
    twins = []
    attempts = blocks = mismatches = 0

    def determine(truth: CandidateTruth) -> Determined:
        nonlocal attempts, blocks, mismatches
        d = m.determine(as_candidate(truth))
        honest_run = truth.persona == Persona.honest
        attempts += honest_run
        if d.pending is None:
            return Determined(d.grade, d.overall)
        verified = m.verify(d.user, truth)
        blocks += honest_run
        mismatches += honest_run and not verified.confirmed
        return Determined(verified.grade, d.overall)

    for truth in truths:
        determine(honest())
        cheater = determine(_cheater(truth, leaked))
        first = determine(truth)
        determine(honest())
        again = determine(truth)
        twins.append(Twins(cheater, first, again))
    return tuple(twins), HonestBlocks(attempts, blocks, mismatches)


# --- M15: детектор утечки ----------------------------------------------------------------------


def drift_stream(
    m: Market,
    honest: Callable[[], CandidateTruth],
    *,
    leaked: frozenset[str],
    window: int,
    max_attempts: int,
) -> tuple[Drift, ...]:
    """Поток попыток с 20 % читеров (без утечки — только честные) до `window` ответов на
    каждое семейство с опорными параметрами или до `max_attempts`; детектор не выводит семейства
    из выдачи — стенд считает CUSUM по записанным ответам сам. Пик — в первых `window` ответах
    после начала потока."""
    m.watch = False
    store = m.stand.store
    start = {
        f.code: len(store.collection(FAMILY_PRESENTATIONS).get(f.code, [])) for f in m.families
    }
    references = _references(m)
    every = round(1 / CHEATER_SHARE)
    for i in range(max_attempts):
        if _answered_since(m, start, references) >= window:
            break
        truth = honest()
        if leaked and i % every == every - 1:
            truth = _cheater(truth, leaked)
        m.attempt(as_candidate(truth))
    with m.stand.uow:
        link = m.stand.calibration.links(m.specialization)[0]
    found = []
    for code, reference in references.items():
        answered = [
            p
            for p in store.collection(FAMILY_PRESENTATIONS).get(code, [])[start[code] :]
            if p.correct is not None
        ][:window]
        cusum = peak = 0.0
        for p in answered:
            level = link.apply(Normal(p.topic_theta_before, p.topic_theta_sd_before))
            cusum = cusum_step(cusum, reference, level, p.correct, shift=m.mechanics.drift_shift)
            peak = max(peak, cusum)
        found.append(Drift(code, code in leaked, peak, len(answered)))
    return tuple(found)


def _references(m: Market) -> dict[str, Parameters]:
    """Опорные параметры семейств, по которым работает детектор: после переоценки, у якоря —
    замороженные."""
    rows = m.calibrated()
    found = {}
    for f in m.families:
        row = rows.get(f.code)
        if row is None:
            continue
        reference = row.parameters if f.anchor else row.reference
        if reference is not None:
            found[f.code] = reference
    return found


def _answered_since(m: Market, start: dict[str, int], references: dict[str, Parameters]) -> int:
    """Наименьшее число ответов с начала потока среди 90 % семейств с опорными параметрами:
    редкие семейства, которые адаптивный выбор почти не берёт, поток не держат."""
    index = m.stand.store.collection(FAMILY_PRESENTATIONS)
    counts = sorted(len(index.get(code, [])) - start[code] for code in references)
    if not counts:
        return 0
    return counts[math.floor(0.1 * len(counts))]


# --- M16 а: LLM-помощник -----------------------------------------------------------------------


def helper_runs(m: Market, truths: Sequence[CandidateTruth], *, block_help: bool) -> list[Helper]:
    """Помощник проходит определение на заявленный грейд; подозрительный результат — через
    проверочный блок: с помощником (`block_help`) или без него — как при очной сдаче блока."""
    found = []
    for truth in truths:
        d = m.determine(as_candidate(truth))
        before = d.pending or d.grade
        after = d.grade
        if d.pending is not None:
            in_block = truth if block_help else replace(truth, persona=Persona.honest)
            after = m.verify(d.user, in_block).grade
        found.append(Helper(truth.grade, before, d.pending is not None, after))
    return found


# --- M14: утечка до калибровки -----------------------------------------------------------------


def early_leak(
    params: GeneratorParams, code: str, mechanics: Mechanics, responses: int, generator: Generator
) -> EarlyLeak:
    """Банк прогревается с нуля потоком, где 20 % — читеры со слитыми 30 % банка: утечка попадает
    в сами опорные параметры. Сколько слитых семейств сверка с экспертной сложностью выводит из
    выдачи — и сколько прочих."""
    m = Market(code, mechanics, params.seed, replace(params.response, leak_rho=MAIN_RHO))
    rng = generator.rng(f"early:{code}")
    families = [f.code for f in m.families]
    leaked = frozenset(rng.sample(families, round(MAIN_LEAK * len(families))))
    every = round(1 / CHEATER_SHARE)
    i = 0
    while mean_responses(m) < responses:
        truth = generator.truth(code, Persona.honest, rng)
        if i % every == every - 1:
            truth = _cheater(truth, leaked)
        m.attempt(as_candidate(truth))
        i += 1
    rows = m.calibrated()
    caught = {c for c, row in rows.items() if not row.in_rotation}
    regular = [f.code for f in m.families if not f.anchor]
    return EarlyLeak(
        sum(c in leaked for c in regular),
        sum(c in leaked and c in caught for c in regular),
        sum(c not in leaked for c in regular),
        sum(c not in leaked and c in caught for c in regular),
    )


# --- Сводки для отчёта -------------------------------------------------------------------------


def rank_of(mechanics: Mechanics) -> dict[str | None, int]:
    return {g: i for i, g in enumerate([None, *grades_by_threshold(mechanics.grade_thresholds)])}


@dataclass(frozen=True)
class AttackSummary:
    """M14 по условию: средний прирост θ̄ читера против двойника и избыточная доля повышенных
    категорий — доля читеров с категорией выше двойника минус та же доля у пар «двойник —
    повтор»."""

    gain: float
    raised: float
    baseline: float

    @property
    def excess(self) -> float:
        return self.raised - self.baseline


def summarize(twins: Sequence[Twins], mechanics: Mechanics) -> AttackSummary:
    rank = rank_of(mechanics)
    return AttackSummary(
        statistics.fmean(t.cheater.overall.mean - t.honest.overall.mean for t in twins),
        statistics.fmean(rank[t.cheater.grade] > rank[t.honest.grade] for t in twins),
        statistics.fmean(rank[t.again.grade] > rank[t.honest.grade] for t in twins),
    )


def flagged_share(drift: Sequence[Drift], threshold: float, window: int = 0) -> float:
    """Доля семейств, у которых CUSUM в окне превысил порог, — среди тех, у кого была
    возможность: набрали `window` ответов или сработали раньше."""
    eligible = [d for d in drift if d.responses >= window or d.peak > threshold]
    return statistics.fmean(d.peak > threshold for d in eligible) if eligible else math.nan


# Сетка подбора `drift_cusum_h` на D3 — шаг 0,5.
DRIFT_GRID = tuple(round(1 + 0.5 * i, 1) for i in range(39))


def tune_threshold(drift: Sequence[Drift], window: int, *, fpr: float = 0.05) -> float | None:
    """Правило плана: наименьшее значение сетки с долей ложных тревог не выше `fpr`."""
    return next((h for h in DRIFT_GRID if flagged_share(drift, h, window) <= fpr), None)
