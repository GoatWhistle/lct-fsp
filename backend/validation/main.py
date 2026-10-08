"""Сборка стенда валидации — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md).

Здесь только выбор реализаций портов: in-memory репозитории и единица работы, часы симулятора и
seed прогона. Сценарии из них собирает та же проводка `composition`, что и прод: стенд вызывает
те же сценарии, что HTTP. Каждый процесс прогона собирает свой стенд — хранилище между
процессами не передаётся.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.adapter import irt
from app.adapter.acceptance import NoAcceptanceModel
from app.adapter.catalog_file import load_catalog
from app.adapter.clock import SimulatedClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.seed import DerivedSeeds
from app.adapter.text_rules import RulesTextUnderstanding, load_synonyms
from app.domain.catalog import Catalog as CatalogData
from app.domain.catalog import Grade, Specialization, Technology
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.selection import MemoryCandidatePool, MemoryNeeds, MemorySelections
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.interface import (
    AcceptanceModel,
    ItemSelector,
    SeedSource,
    SkillModel,
    TextUnderstanding,
)
from app.usecase.need_draft import NeedDrafts
from app.usecase.selection import Selections
from composition import Repositories, Usecases, build_usecases, item_selector
from settings import CATALOG_FILE, SYNONYMS_FILE, Mechanics

# Начало времени стенда: попытки идут от него шагами часов.
START = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Catalog:
    """Справочник доменными типами — из того же `catalog.yaml`, что у прода."""

    specializations: dict[str, Specialization]
    grades: dict[str, Grade]
    technologies: dict[str, Technology]


def catalog(loaded: CatalogData | None = None) -> Catalog:
    loaded = loaded or load_catalog(CATALOG_FILE)
    return Catalog(
        specializations={s.code: s for s in loaded.specializations},
        grades={g.code: g for g in loaded.grades},
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
    understanding: TextUnderstanding
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

    def need_drafts(self) -> NeedDrafts:
        return self.usecases.need_drafts(self.uow)

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
            understanding=self.understanding,
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
    understanding: TextUnderstanding | None = None,
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
    understanding = understanding or RulesTextUnderstanding(load_synonyms(SYNONYMS_FILE))
    loaded = load_catalog(CATALOG_FILE)
    MemoryCatalog(store).put(loaded)
    known = catalog(loaded)
    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](
            attempts=lambda uow: _attempts(uow.store, known, mechanics),
            calibration=lambda uow: MemoryCalibrationRepository(uow.store),
            needs=lambda uow: MemoryNeeds(uow.store),
            catalog=lambda uow: MemoryCatalog(uow.store),
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
        text_understanding=understanding,
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
        understanding=understanding,
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
