"""Сборка стенда валидации — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md).

Здесь только выбор реализаций портов: in-memory репозитории и единица работы, часы симулятора и
seed прогона. Сценарии из них собирает та же проводка `composition`, что и прод: стенд вызывает
те же сценарии, что HTTP. Каждый процесс прогона собирает свой стенд — хранилище между
процессами не передаётся.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.adapter.acceptance import NoAcceptanceModel
from app.adapter.clock import SimulatedClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.seed import DerivedSeeds
from app.assessment.catalog import load_catalog
from app.config import Mechanics
from app.domain.catalog import Grade, Specialization, Technology, Topic
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.selection import MemoryCandidatePool, MemoryNeeds, MemorySelections
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.skills import irt
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.interface import AcceptanceModel, ItemSelector, SeedSource, SkillModel
from app.usecase.selection import Selections
from composition import Repositories, Usecases, build_usecases, item_selector

# Начало времени стенда: попытки идут от него шагами часов.
START = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Catalog:
    """Справочник доменными типами — из того же `catalog.yaml`, что у прода."""

    specializations: dict[str, Specialization]
    grades: dict[str, Grade]
    technologies: dict[str, Technology]


def catalog() -> Catalog:
    loaded = load_catalog()
    return Catalog(
        specializations={
            s.code: Specialization(
                s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics)
            )
            for s in loaded.specializations
        },
        grades={g.code: Grade(g.code, g.name, g.rank) for g in loaded.grades},
        technologies={
            t.code: Technology(t.code, t.name, tuple(sorted(t.topics))) for t in loaded.technologies
        },
    )


@dataclass
class Stand:
    """Собранный стенд: сценарии на единице работы стенда и репозитории, через которые стенд
    кладёт кандидатов и потребности и читает записанное — как читал бы базу."""

    mechanics: Mechanics
    catalog: Catalog
    store: MemoryStore
    clock: SimulatedClock
    # Шаг часов перед каждой попыткой.
    step: timedelta
    seeds: SeedSource
    selector: ItemSelector
    skill_model: SkillModel
    acceptance: AcceptanceModel
    usecases: Usecases[MemoryUnitOfWork]
    uow: MemoryUnitOfWork = field(init=False)
    attempts: MemoryAttemptRepository = field(init=False)
    calibration: MemoryCalibrationRepository = field(init=False)
    needs: MemoryNeeds = field(init=False)
    pool: MemoryCandidatePool = field(init=False)

    def __post_init__(self) -> None:
        self.uow = MemoryUnitOfWork(self.store, rollback=False)
        self.attempts = _attempts(self.store, self.catalog, self.mechanics)
        self.calibration = MemoryCalibrationRepository(self.store)
        self.needs = MemoryNeeds(self.store)
        self.pool = MemoryCandidatePool(self.store)

    def candidate_path(self) -> CandidatePath:
        return self.usecases.candidate_path(self.uow)

    def answer_calibration(self) -> AnswerCalibration:
        return self.usecases.answer_calibration(self.uow)

    def selections(self) -> Selections:
        return self.usecases.selections(self.uow)

    def variant(self, mechanics: Mechanics) -> "Stand":
        """Стенд на тех же хранилище, часах, seed и портах, но с другими числами механик: тот же
        банк и окно показов, другой бланк теста."""
        return build_stand(
            mechanics,
            store=self.store,
            clock=self.clock,
            step=self.step,
            seeds=self.seeds,
            selector=self.selector,
            skill_model=self.skill_model,
            acceptance=self.acceptance,
        )


def build_stand(
    mechanics: Mechanics,
    *,
    seed: int = 0,
    step: timedelta | None = None,
    start: datetime = START,
    store: MemoryStore | None = None,
    clock: SimulatedClock | None = None,
    seeds: SeedSource | None = None,
    selector: ItemSelector | None = None,
    skill_model: SkillModel | None = None,
    acceptance: AcceptanceModel | None = None,
) -> Stand:
    """Стенд прогона `seed`. Шаг часов по умолчанию — больше ожидания смены грейда (§4): правило
    ожидания не мешает ни одной попытке. Переопределения портов — для экспериментов: модель
    принятия, выбор задания, модель навыка."""
    store = store or MemoryStore()
    clock = clock or SimulatedClock(start)
    seeds = seeds or DerivedSeeds(seed)
    selector = selector or item_selector(mechanics)
    skill_model = skill_model or irt
    acceptance = acceptance or NoAcceptanceModel()
    known = catalog()
    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](
            attempts=lambda uow: _attempts(uow.store, known, mechanics),
            calibration=lambda uow: MemoryCalibrationRepository(uow.store),
            needs=lambda uow: MemoryNeeds(uow.store),
            pool=lambda uow: MemoryCandidatePool(uow.store),
            selections=lambda uow: MemorySelections(uow.store),
        ),
        mechanics=mechanics,
        selector=selector,
        skill_model=skill_model,
        clock=clock,
        seeds=seeds,
        code_runner=InProcessCodeRunner(),
        acceptance=acceptance,
    )
    return Stand(
        mechanics=mechanics,
        catalog=known,
        store=store,
        clock=clock,
        step=step or timedelta(days=mechanics.grade_change_interval_days + 1),
        seeds=seeds,
        selector=selector,
        skill_model=skill_model,
        acceptance=acceptance,
        usecases=usecases,
    )


def _attempts(store: MemoryStore, known: Catalog, mechanics: Mechanics) -> MemoryAttemptRepository:
    return MemoryAttemptRepository(
        store,
        known.specializations,
        known.grades,
        mechanics.grade_thresholds,
        mechanics.grade_confidence,
    )
