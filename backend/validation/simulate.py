"""Прогон набора D1 или D2 на стенде для отчёта (docs/validation-plan.md): то, что записала
платформа, — без истины.

Задача прогона — одна специализация набора с одним κ: банк прогревается на честных кандидатах
набора, затем каждый кандидат набора проходит первичное определение, часть честных — второй раз,
все — наивный тест B0; кандидаты идут в пул, по каждой потребности строится подборка. Результат —
`SpecRun`: категории, оценки и профили по id кандидата, порядок выдачи по потребности, состояние
банка. Истину с этим соединяет только код метрик (`validation.report`).

Истину знает здесь только симулятор — он отвечает за кандидата (`Market.answer`) и меряет
калибровку по истинным параметрам семейств (`calibration_quality`). Сценарии оценки и подбора
видят только ответы.
"""

import logging
import statistics
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.adapter import calibration
from app.adapter.code_runner import InProcessCodeRunner
from app.domain.skill import Normal, sigmoid
from app.usecase.selection import Selections
from settings import Mechanics
from validation.main import catalog
from validation.market import (
    Candidate,
    Market,
    calibration_quality,
    corrupted_families,
    mean_responses,
)
from validation.metrics import median, regression, rmse
from validation.population import Generator, GeneratorParams, SyntheticNeed, as_candidate
from validation.truth import CandidateTruth, Corruption, Persona
from validation.twins import Twin

# Точки сходимости калибровки M12 — ответов на семейство в среднем.
CHECKPOINTS = (50, 100, 200, 500)
# Работодатель стенда, от имени которого строятся подборки.
EMPLOYER = uuid.UUID(int=10**9)
# Доля испорченных семейств банка M21.
CORRUPTED_SHARE = 0.05


@dataclass(frozen=True)
class Scale:
    """Размер прогона. По умолчанию — план: все кандидаты набора, 1000 пар M9 (по 200 на
    специализацию), прогретый банк — 500 ответов на семейство, 300 кандидатов M13."""

    pairs: int = 200
    warm: int = 500
    compare: int = 300
    # Честных кандидатов M21 на специализацию: 1000 на пять.
    fit: int = 200
    # Кандидатов набора на специализацию; None — все.
    candidates: int | None = None


@dataclass(frozen=True)
class Determined:
    grade: str | None
    overall: Normal


@dataclass(frozen=True)
class Outcome:
    """Что платформа записала о кандидате набора."""

    first: Determined
    # Повтор первичного определения с независимыми экземплярами (M9); None — без повтора.
    second: Determined | None
    # Профиль навыков специализации по темам; пусто — профиля нет.
    profile: dict[str, Normal]
    # B0: доля верных на общем фиксированном бланке — первое и повторное прохождение.
    naive: tuple[float, ...]


@dataclass(frozen=True)
class Checkpoint:
    """Калибровка после `responses` ответов на семейство в среднем (M12): r(b̂, b*), RMSE и RMSE
    экспертных b₀; ошибка e = b̂ − b* против отклонения истины от эксперта d = b* − b₀ —
    наклон прямой e(d), средняя ошибка и sd остатка вокруг прямой."""

    responses: int
    r: float
    rmse: float
    expert_rmse: float
    bias: float
    slope: float
    residual_sd: float


@dataclass(frozen=True)
class FamilyState:
    """Семейство банка после прогрева: оценённые параметры и ответов в калибровке."""

    code: str
    topic: str
    grade: str
    anchor: bool
    discrimination: float
    difficulty: float
    responses: int


@dataclass(frozen=True)
class Adaptivity:
    """M13 — адаптивный тест против общего фиксированного бланка на тех же кандидатах."""

    # Медиана заданий до σ̄ ≤ `test_stop_sd`.
    adaptive_median: float
    common_median: float
    # Средняя σ̄ на длине 20.
    adaptive_sd_20: float
    common_sd_20: float
    # Доля дошедших до порога за `test_max_items`.
    adaptive_within: float
    common_within: float

    @property
    def ratio(self) -> float:
        return self.adaptive_median / self.common_median


@dataclass(frozen=True)
class Placed:
    """Строка выдачи: кандидат или двойник, блок и скор S; в нижнем блоке скора нет."""

    candidate: uuid.UUID
    block: str
    score: float | None


@dataclass(frozen=True)
class Scored:
    """Кандидат подборки со скором — точный или «близкий» блок: категория по тесту и S."""

    candidate: uuid.UUID
    # Грейд категории кандидата.
    grade: str
    match_score: float


@dataclass(frozen=True)
class SpecRun:
    dataset: str
    specialization: str
    inflation: float
    outcomes: dict[uuid.UUID, Outcome]
    # Потребность → кандидаты в порядке выдачи подборки.
    rankings: dict[uuid.UUID, tuple[uuid.UUID, ...]] = field(default_factory=dict)
    # Потребность → строки той же выдачи с блоком и скором.
    placed: dict[uuid.UUID, tuple[Placed, ...]] = field(default_factory=dict)
    # Потребность → выдача по пулу с двойниками M3 и M5: кандидаты и двойники вместе. Порядок
    # выдачи поточечный — блок, скор, соль по id, — и двойники не меняют порядок кандидатов
    # между собой.
    twin_placed: dict[uuid.UUID, tuple[Placed, ...]] = field(default_factory=dict)
    # Категория и профиль, с которыми кандидат попал в пул подборки, — после повтора M9, если
    # он был: так его видит работодатель.
    listed: dict[uuid.UUID, tuple[str | None, dict[str, Normal]]] = field(default_factory=dict)
    checkpoints: tuple[Checkpoint, ...] = ()
    families: tuple[FamilyState, ...] = ()
    # B0: отсечки доли верных по грейдам — ожидаемая доля на пороге грейда по экспертным
    # параметрам бланка.
    naive_cutoffs: dict[str, float] = field(default_factory=dict)
    adaptivity: Adaptivity | None = None
    # Потребность пар модели принятия → кандидаты её подборки со скором.
    offers: dict[uuid.UUID, tuple[Scored, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Job:
    params: GeneratorParams
    specialization: str
    mechanics: Mechanics
    scale: Scale
    truths: tuple[CandidateTruth, ...]
    needs: tuple[SyntheticNeed, ...]
    stack: dict[uuid.UUID, frozenset[str]]
    # Двойники кандидатов специализации (`validation.twins`).
    twins: tuple[Twin, ...] = ()
    # Полный прогон — с B0, повтором, подборками и M13; иначе только определения (M4 до поправки).
    full: bool = True
    # Потребности пар модели принятия (M7): подборка по каждой — кандидаты со скором.
    offer_needs: tuple[SyntheticNeed, ...] = ()


def warm_source(
    params: GeneratorParams, code: str, mechanics: Mechanics, stream: str = "warm"
) -> Callable[[], Candidate]:
    """Поток честных кандидатов набора для прогрева банка — свой поток случайности генератора
    `stream`: кандидаты набора его не сдвигают."""
    generator = Generator(params, mechanics, catalog())
    rng = generator.rng(f"{stream}:{code}")
    return lambda: as_candidate(generator.truth(code, Persona.honest, rng))


def warm(m: Market, source: Callable[[], Candidate], responses: int) -> tuple[Checkpoint, ...]:
    """Калибровка на потоке `source` до `responses` ответов на семейство; по дороге — точки M12.
    Дальше банк заморожен."""
    found = []
    for n in (*(c for c in CHECKPOINTS if c < responses), responses):
        while mean_responses(m) < n:
            m.attempt(source())
        found.append(checkpoint(m, n))
    m.calibrate = False
    return tuple(found)


def checkpoint(m: Market, responses: int) -> Checkpoint:
    r, error, start = calibration_quality(m)
    params = m.parameters()
    regular = [f for f in m.families if not f.anchor]
    gap = [m.truth[f.code].difficulty - m.expert(f.grade).difficulty for f in regular]
    miss = [params[f.code].difficulty - m.truth[f.code].difficulty for f in regular]
    line = regression(gap, miss)
    return Checkpoint(
        responses, r, error, start, statistics.fmean(miss), line.slope, line.residual_sd
    )


def compare(m: Market, candidates: int, source: Callable[[], Candidate]) -> Adaptivity:
    """Те же кандидаты проходят адаптивный тест и общий фиксированный бланк без лимита заданий:
    медиана заданий до σ̄ ≤ `test_stop_sd`; σ̄ на длине 20 — адаптивный ровно на 20 заданий.

    Без лимита и ровно 20 заданий — варианты стенда на том же банке: лимит заданий и порог
    остановки — числа механик, остальное — те же сценарии."""
    limit = m.mechanics.test_max_items
    bank = len(m.families)
    unlimited = m.stand.variant(m.mechanics.model_copy(update={"test_max_items": bank}))
    twenty = m.stand.variant(
        m.mechanics.model_copy(update={"test_max_items": 20, "test_stop_sd": 0.0})
    )
    target = m.mechanics.test_stop_sd
    adaptive, common, at_20 = [], [], []
    for _ in range(candidates):
        c = source()
        adaptive.append(m.items_to(m.attempt(c, stand=unlimited), target) or bank + 1)
        run = m.fixed(c, bank, target=0.0)
        common.append(m.items_to(run, target) or bank + 1)
        at_20.append(m.sd_after(run, 20))
    sd_20 = [m.attempt(source(), stand=twenty).overall.sd for _ in range(candidates)]
    return Adaptivity(
        adaptive_median=median(adaptive),
        common_median=median(common),
        adaptive_sd_20=statistics.fmean(sd_20),
        common_sd_20=statistics.fmean(at_20),
        adaptive_within=sum(n <= limit for n in adaptive) / candidates,
        common_within=sum(n <= limit for n in common) / candidates,
    )


def naive_cutoffs(m: Market, blank: Sequence[str]) -> dict[str, float]:
    """B0: отсечка грейда — ожидаемая доля верных на его пороге по экспертным параметрам бланка.
    Так выставил бы отсечки составитель теста без калибровки."""
    families = {f.code: f for f in m.families}
    thresholds = m.mechanics.grade_thresholds
    return {
        g: statistics.fmean(
            sigmoid(p.discrimination * (c - p.difficulty))
            for p in (m.expert(families[code].grade) for code in blank)
        )
        for g, c in thresholds.items()
    }


def _determined(
    job: Job,
) -> tuple[
    Market,
    Callable[[], Candidate],
    tuple[Checkpoint, ...],
    tuple[CandidateTruth, ...],
    dict[uuid.UUID, uuid.UUID],
    dict[uuid.UUID, Determined],
]:
    """Банк прогрет на честных кандидатах набора, каждый кандидат прошёл первичное определение:
    стенд, поток прогрева, точки M12, кандидаты, их учётки и определения."""
    params, code, mechanics, scale = job.params, job.specialization, job.mechanics, job.scale
    m = Market(code, mechanics, params.seed, params.response)
    source = warm_source(params, code, mechanics)
    checkpoints = warm(m, source, scale.warm)
    truths = job.truths[: scale.candidates] if scale.candidates else job.truths
    users: dict[uuid.UUID, uuid.UUID] = {}
    first: dict[uuid.UUID, Determined] = {}
    for t in truths:
        d = m.determine(as_candidate(t))
        users[t.id] = d.user
        first[t.id] = Determined(d.grade, d.overall)
    return m, source, checkpoints, truths, users, first


def offers(
    m: Market, job: Job, truths: Sequence[CandidateTruth], users: dict[uuid.UUID, uuid.UUID]
) -> dict[uuid.UUID, tuple[Scored, ...]]:
    """Подборки по потребностям пар модели принятия — кандидаты точного и «близкого» блоков со
    скором. Кандидаты уже в пуле стенда."""
    by_user = {u: t for t, u in users.items()}
    selections = m.stand.selections()
    found = {}
    for need in job.offer_needs:
        page = selections.build_draft(EMPLOYER, need.form, limit=len(truths))
        found[need.id] = tuple(
            Scored(by_user[e.candidate_id], e.grade.code, e.match_score)
            for e in page.entries
            if e.match_score is not None
        )
    return found


def run_offers(job: Job) -> dict[uuid.UUID, tuple[Scored, ...]]:
    """Задача пула процессов для обучения модели принятия: только определения и подборки по
    потребностям пар — без B0, повтора и M13."""
    m, _, _, truths, users, _ = _determined(job)
    for t in truths:
        m.enlist(users[t.id], stack=job.stack[t.id], claimed=t.claimed)
    return offers(m, job, truths, users)


def run_spec(job: Job) -> SpecRun:
    """Задача пула процессов: прогон специализации набора — см. описание модуля."""
    params, mechanics, scale = job.params, job.mechanics, job.scale
    m, source, checkpoints, truths, users, first = _determined(job)
    code = job.specialization
    profiles = {t.id: _profile(m, users[t.id]) for t in truths}
    if not job.full:
        outcomes = {t.id: Outcome(first[t.id], None, profiles[t.id], ()) for t in truths}
        return SpecRun(
            params.name, code, mechanics.level_sd_inflation, outcomes, checkpoints=checkpoints
        )

    pairs = [t for t in truths if t.persona == Persona.honest][: scale.pairs]
    second = {}
    for t in pairs:
        d = m.determine(as_candidate(t))
        second[t.id] = Determined(d.grade, d.overall)
    blank = m.fixed(as_candidate(truths[0]), mechanics.test_max_items, target=0.0).shown
    naive_runs: dict[uuid.UUID, tuple[float, ...]] = {}
    for t in truths:
        times = 2 if t.id in second else 1
        naive_runs[t.id] = tuple(_proportion(m, as_candidate(t)) for _ in range(times))
    outcomes = {
        t.id: Outcome(first[t.id], second.get(t.id), profiles[t.id], naive_runs[t.id])
        for t in truths
    }

    by_user = {u: t for t, u in users.items()}
    for t in truths:
        m.enlist(users[t.id], stack=job.stack[t.id], claimed=t.claimed)
    selections = m.stand.selections()
    placed = {need.id: _placed(selections, need, len(truths), by_user.get) for need in job.needs}
    rankings = {n: tuple(p.candidate for p in rows) for n, rows in placed.items()}

    listed = {t.id: _listed(m, users[t.id]) for t in truths}

    families = _families(m)
    adaptivity = compare(m, scale.compare, source)
    # Пары модели принятия — после замеров банка: их подборки не сдвигают сиды замеров выше.
    offered = offers(m, job, truths, users)
    # Двойники — последними: подборка берёт соль из того же источника seed, что и тест и пары
    # принятия, и лишние подборки до них сдвинули бы их.
    own_twins = [tw for tw in job.twins if tw.source in users]
    for tw in own_twins:
        m.twin(users[tw.source], tw.id, frozenset(tw.observed.stack))
    twin_placed = (
        {
            need.id: _placed(
                selections, need, len(truths) + len(own_twins), lambda c: by_user.get(c, c)
            )
            for need in job.needs
        }
        if own_twins
        else {}
    )
    return SpecRun(
        params.name,
        code,
        mechanics.level_sd_inflation,
        outcomes,
        rankings,
        placed=placed,
        twin_placed=twin_placed,
        listed=listed,
        checkpoints=checkpoints,
        families=families,
        naive_cutoffs=naive_cutoffs(m, blank),
        adaptivity=adaptivity,
        offers=offered,
    )


def _placed(
    selections: Selections,
    need: SyntheticNeed,
    limit: int,
    candidate: Callable[[uuid.UUID], uuid.UUID | None],
) -> tuple[Placed, ...]:
    """Выдача по потребности; `candidate` — id кандидата набора по id в пуле стенда."""
    page = selections.build_draft(EMPLOYER, need.form, limit=limit)
    found = []
    for e in page.entries:
        cid = candidate(e.candidate_id)
        assert cid is not None
        found.append(Placed(cid, e.block.value, e.match_score))
    return tuple(found)


def run_cold(job: Job) -> Adaptivity:
    """M13 на холодном банке — экспертные параметры, калибровки нет."""
    m = Market(job.specialization, job.mechanics, job.params.seed, job.params.response)
    m.calibrate = False
    return compare(m, job.scale.compare, warm_source(job.params, job.specialization, job.mechanics))


@dataclass(frozen=True)
class FamilyFit:
    """Неякорное семейство банка M21 после прогрева: что о нём знает истина и что решила
    проверка согласия."""

    code: str
    # Выбор из вариантов — есть варианты ответа; иначе вычисляемый ответ.
    choice: bool
    corruption: Corruption | None
    refitted: bool
    # Проверка согласия после переоценки вывела семейство из выдачи (mechanics.md, §7).
    flagged: bool


@dataclass(frozen=True)
class ItemFit:
    """M21 — проверка согласия на банке с испорченными семействами."""

    families: tuple[FamilyFit, ...]
    # RMSE(θ̄̂, θ̄*) честных кандидатов: испорченные в выдаче; выдача, как её оставила переоценка
    # (проверки согласия и дрейфа); выведены все испорченные.
    rmse_in: float
    rmse_checked: float
    rmse_clean: float


class _FitFlags(logging.Handler):
    """Задачи банку из журнала калибровки: семейства с плохим согласием."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.codes: set[str] = set()

    def emit(self, record: logging.LogRecord) -> None:
        code = getattr(record, calibration.ITEM_FIT_FAMILY, None)
        if code is not None:
            self.codes.add(code)


@contextmanager
def _fit_flags() -> Iterator[_FitFlags]:
    """Флаги согласия за время блока: уровень журнала калибровки закреплён — настройка журнала
    не обнуляет счёт."""
    flags = _FitFlags()
    level = calibration.log.level
    calibration.log.setLevel(logging.WARNING)
    calibration.log.addHandler(flags)
    try:
        yield flags
    finally:
        calibration.log.removeHandler(flags)
        calibration.log.setLevel(level)


def run_fit(job: Job) -> ItemFit:
    """M21 — задача пула процессов: банк набора плюс `CORRUPTED_SHARE` испорченных семейств в
    скрытой истине прогревается на честных кандидатах набора, переоценка проверяет согласие. Затем
    на замороженном банке одни и те же честные кандидаты проходят тест трижды, на одних и тех же
    случайных числах ответа: испорченные в выдаче; выдача, как её оставила переоценка; выведены
    все испорченные."""
    params, code, mechanics, scale = job.params, job.specialization, job.mechanics, job.scale
    m = Market(code, mechanics, params.seed, params.response)
    generator = Generator(params, mechanics, catalog())
    m.corrupted = corrupted_families(m.families, CORRUPTED_SHARE, generator.rng(f"corrupt:{code}"))
    source = warm_source(params, code, mechanics)
    with _fit_flags() as flags:
        while mean_responses(m) < scale.warm:
            m.attempt(source())
    m.calibrate = False
    rows = m.calibrated()
    runner = InProcessCodeRunner()
    families = tuple(
        FamilyFit(
            f.code,
            bool(f.instance(0, runner).options),
            m.corrupted.get(f.code),
            f.code in rows and rows[f.code].refitted_at is not None,
            f.code in flags.codes,
        )
        for f in m.families
        if not f.anchor
    )

    honest = warm_source(params, code, mechanics, "fit")
    candidates = [honest() for _ in range(scale.fit)]
    truth = [m.overall(c) for c in candidates]

    def error() -> float:
        m.rng.seed(f"{params.seed}:fit-answers:{code}")
        return rmse([m.attempt(c).overall.mean for c in candidates], truth)

    corrupted = set(m.corrupted)
    checked = {c: c not in rows or rows[c].in_rotation for c in corrupted}
    m.rotate(corrupted, True)
    rmse_in = error()
    m.rotate([c for c, kept in checked.items() if not kept], False)
    rmse_checked = error()
    m.rotate(corrupted, False)
    return ItemFit(families, rmse_in, rmse_checked, error())


def _proportion(m: Market, candidate: Candidate) -> float:
    run = m.fixed(candidate, m.mechanics.test_max_items, target=0.0)
    return sum(a.correct for a in run.answers) / len(run.answers)


def _profile(m: Market, user: uuid.UUID) -> dict[str, Normal]:
    with m.stand.uow:
        profile = m.stand.attempts.profile(user, m.specialization)
    if profile is None:
        return {}
    return {t.topic.code: Normal(t.level.theta, t.level.theta_sd) for t in profile.topics}


def _listed(m: Market, user: uuid.UUID) -> tuple[str | None, dict[str, Normal]]:
    with m.stand.uow:
        category = m.stand.attempts.state(user).category
    return (category.grade.code if category else None), _profile(m, user)


def _families(m: Market) -> tuple[FamilyState, ...]:
    rows = m.calibrated()
    params = m.parameters()
    return tuple(
        FamilyState(
            f.code,
            f.topic,
            f.grade,
            f.anchor,
            params[f.code].discrimination,
            params[f.code].difficulty,
            rows[f.code].responses if f.code in rows else 0,
        )
        for f in m.families
    )
