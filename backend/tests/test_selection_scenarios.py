"""Сценарии подборки — «построить», «открыть», «список» — на портах (mechanics.md, §12–13).

Одни и те же тесты идут на in-memory репозиториях и на Postgres: кандидатов и потребности
обвязка кладёт прямо в хранилище, без HTTP и прохождения теста.
"""

import math
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from app.adapter.acceptance import NoAcceptanceModel
from app.adapter.clock import FrozenClock
from app.adapter.seed import DerivedSeeds
from app.assessment.catalog import load_catalog
from app.assessment.models import CandidateCategory, Survey, TestAttempt
from app.assessment.models import Technology as TechnologyRow
from app.config import BACKEND_DIR, Mechanics
from app.domain.catalog import Grade, Specialization, Technology, Topic
from app.domain.errors import NeedNotFound, SelectionNotFound
from app.domain.selection import (
    AcceptanceFeatures,
    Expectations,
    Need,
    PoolCandidate,
    SelectionBlock,
)
from app.domain.skill import Normal
from app.domain.work import SalaryRange, WorkFormat
from app.identity.models import Role, User
from app.matching.models import Need as NeedRow
from app.profile.models import CandidateProfile, candidate_technologies
from app.repository.memory.selection import MemoryCandidatePool, MemoryNeeds, MemorySelections
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.repository.selection import SqlCandidatePool, SqlNeeds, SqlSelections
from app.repository.unit_of_work import SqlUnitOfWork
from app.skills.models import SkillProfile, SkillProfileTopic
from app.usecase.interface import AcceptanceModel
from app.usecase.selection import Selections

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
CATALOG = load_catalog()
GRADES = {g.code: Grade(g.code, g.name, g.rank) for g in CATALOG.grades}
SPECIALIZATIONS = {
    s.code: Specialization(s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics))
    for s in CATALOG.specializations
}
TECHNOLOGIES = {
    t.code: Technology(t.code, t.name, tuple(sorted(t.topics))) for t in CATALOG.technologies
}
QA_TOPICS = [t.code for t in SPECIALIZATIONS["qa"].topics]
NEED_STACK = ["playwright", "postgresql", "pytest"]


class SalaryFit:
    """Тестовая модель принятия: логистическая функция от (середина вилки − ожидание) / ожидание.
    Монотонна по вилке; без вилки или без ожидания — константа."""

    def __init__(self) -> None:
        self.seen: list[AcceptanceFeatures] = []

    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        self.seen.extend(features)
        return [self.probability(f) for f in features]

    @staticmethod
    def probability(f: AcceptanceFeatures) -> float:
        if f.salary is None or f.expected_salary is None:
            return 0.5
        middle = (f.salary.low + f.salary.high) / 2
        return 1 / (1 + math.exp(-4 * (middle - f.expected_salary) / f.expected_salary))


@dataclass
class CandidateSeed:
    grade: str = "middle"
    # Тема → (уровень, погрешность); темы без записи — средний уровень с типичной погрешностью.
    levels: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Темы, которых нет в профиле: добавлены в справочник после пересчёта.
    absent: tuple[str, ...] = ()
    stack: tuple[str, ...] = ()
    expectations: Expectations | None = None
    specialization: str = "qa"
    last_signal_at: datetime = T0


@dataclass
class NeedSeed:
    grade: str = "middle"
    stack: tuple[str, ...] = tuple(NEED_STACK)
    salary: SalaryRange | None = None
    specialization: str = "qa"
    work_format: WorkFormat = WorkFormat.remote
    city: str | None = None


class Harness:
    """Сценарии подборки на одной реализации хранилищ и способ положить туда данные."""

    employer: uuid.UUID
    selections: Selections
    clock: FrozenClock

    def need(self, seed: NeedSeed | None = None, *, owner: uuid.UUID | None = None) -> uuid.UUID:
        raise NotImplementedError

    def candidate(self, seed: CandidateSeed) -> uuid.UUID:
        raise NotImplementedError

    def candidates(self, seeds: Sequence[CandidateSeed]) -> list[uuid.UUID]:
        return [self.candidate(s) for s in seeds]

    def user(self) -> uuid.UUID:
        return uuid.uuid4()


def _levels(seed: CandidateSeed) -> dict[str, Normal]:
    topics = [t.code for t in SPECIALIZATIONS[seed.specialization].topics]
    return {t: Normal(*seed.levels.get(t, (0.5, 0.5))) for t in topics if t not in seed.absent}


class MemoryHarness(Harness):
    def __init__(self, acceptance: AcceptanceModel, mechanics: Mechanics) -> None:
        store = MemoryStore()
        self.needs = MemoryNeeds(store)
        self.pool = MemoryCandidatePool(store)
        self.clock = FrozenClock(T0)
        self.employer = uuid.uuid4()
        self.selections = Selections(
            MemoryUnitOfWork(store),
            self.needs,
            self.pool,
            MemorySelections(store),
            acceptance,
            self.clock,
            DerivedSeeds(0),
            mechanics,
        )

    def need(self, seed: NeedSeed | None = None, *, owner: uuid.UUID | None = None) -> uuid.UUID:
        seed = seed or NeedSeed()
        need = Need(
            id=uuid.uuid4(),
            title="QA-инженер",
            specialization=SPECIALIZATIONS[seed.specialization],
            grade=GRADES[seed.grade],
            stack=tuple(sorted((TECHNOLOGIES[c] for c in seed.stack), key=lambda t: t.name)),
            edited_importance={},
            work_format=seed.work_format,
            city=seed.city,
            salary=seed.salary,
            updated_at=self.clock.now(),
        )
        self.needs.put(owner or self.employer, need)
        return need.id

    def candidate(self, seed: CandidateSeed) -> uuid.UUID:
        candidate = PoolCandidate(
            candidate_id=uuid.uuid4(),
            specialization=seed.specialization,
            grade=GRADES[seed.grade],
            levels=_levels(seed),
            stack=frozenset(seed.stack),
            last_signal_at=seed.last_signal_at,
            expectations=seed.expectations,
        )
        self.pool.add(candidate)
        return candidate.candidate_id


class PostgresHarness(Harness):
    def __init__(self, engine: Engine, acceptance: AcceptanceModel, mechanics: Mechanics) -> None:
        self.engine = engine
        self.uow = SqlUnitOfWork(Session(engine))
        session = self.uow.session
        self.clock = FrozenClock(T0)
        self.selections = Selections(
            self.uow,
            SqlNeeds(session),
            SqlCandidatePool(session),
            SqlSelections(session),
            acceptance,
            self.clock,
            DerivedSeeds(0),
            mechanics,
        )
        self.employer = self.user(Role.employer)

    def _write(self, write: Callable[[Session], object]) -> None:
        with Session(self.engine) as session, session.begin():
            write(session)

    def user(self, role: Role = Role.employer) -> uuid.UUID:
        user_id = uuid.uuid4()
        self._write(lambda s: s.execute(insert(User), [self._user_row(user_id, role)]))
        return user_id

    @staticmethod
    def _user_row(user_id: uuid.UUID, role: Role) -> dict[str, Any]:
        return {
            "id": user_id,
            "email": f"{role}-{user_id.hex}@example.com",
            "password_hash": "-",
            "role": role,
            "email_verified_at": T0,
            "created_at": T0,
        }

    def need(self, seed: NeedSeed | None = None, *, owner: uuid.UUID | None = None) -> uuid.UUID:
        seed = seed or NeedSeed()
        need_id = uuid.uuid4()

        def write(s: Session) -> None:
            s.add(
                NeedRow(
                    id=need_id,
                    user_id=owner or self.employer,
                    title="QA-инженер",
                    team_description="",
                    specialization_code=seed.specialization,
                    grade_code=seed.grade,
                    work_format=seed.work_format,
                    city=seed.city,
                    salary_from=seed.salary.low if seed.salary else None,
                    salary_to=seed.salary.high if seed.salary else None,
                    created_at=self.clock.now(),
                    updated_at=self.clock.now(),
                    stack=[s.get_one(TechnologyRow, c) for c in seed.stack],
                )
            )

        self._write(write)
        return need_id

    def candidate(self, seed: CandidateSeed) -> uuid.UUID:
        return self.candidates([seed])[0]

    def candidates(self, seeds: Sequence[CandidateSeed]) -> list[uuid.UUID]:
        tables: tuple[Any, ...] = (
            User,
            Survey,
            TestAttempt,
            CandidateCategory,
            SkillProfile,
            SkillProfileTopic,
            CandidateProfile,
            candidate_technologies,
        )
        rows: dict[Any, list[dict[str, Any]]] = {table: [] for table in tables}
        ids = []
        for seed in seeds:
            uid, survey, attempt, profile = (uuid.uuid4() for _ in range(4))
            ids.append(uid)
            at = seed.last_signal_at
            spec = seed.specialization
            rows[User].append(self._user_row(uid, Role.candidate))
            rows[Survey].append(
                {
                    "id": survey,
                    "user_id": uid,
                    "number": 1,
                    "specialization_code": spec,
                    "created_at": at,
                }
            )
            rows[TestAttempt].append(
                {
                    "id": attempt,
                    "user_id": uid,
                    "number": 1,
                    "survey_id": survey,
                    "specialization_code": spec,
                    "grade_code": seed.grade,
                    "started_at": at,
                }
            )
            rows[CandidateCategory].append(
                {
                    "user_id": uid,
                    "specialization_code": spec,
                    "grade_code": seed.grade,
                    "attempt_id": attempt,
                    "assigned_at": at,
                }
            )
            rows[SkillProfile].append(
                {
                    "id": profile,
                    "user_id": uid,
                    "specialization_code": spec,
                    "overall_theta": 0.5,
                    "overall_theta_sd": 0.4,
                    "observations": 20,
                    "last_signal_at": at,
                    "updated_at": at,
                }
            )
            rows[SkillProfileTopic].extend(
                {
                    "profile_id": profile,
                    "topic_code": topic,
                    "theta": level.mean,
                    "theta_sd": level.sd,
                }
                for topic, level in _levels(seed).items()
            )
            expectations = seed.expectations
            if expectations is None and seed.stack:
                raise ValueError("стек — часть профиля кандидата: нужны и ожидания")
            if expectations is not None:
                rows[CandidateProfile].append(
                    {
                        "user_id": uid,
                        "full_name": "Сидов Сид",
                        "contact_email": "s@example.com",
                        "about": "",
                        "job_roles": [],
                        "soft_skills": [],
                        "experience_years": 3,
                        "work_formats": [f.value for f in expectations.work_formats],
                        "city": expectations.city,
                        "relocation": expectations.relocation,
                        "salary_from": expectations.salary_from,
                        "updated_at": at,
                    }
                )
                rows[candidate_technologies].extend(
                    {"user_id": uid, "technology_code": t} for t in seed.stack
                )

        def write(s: Session) -> None:
            # По порядку ключей — родительские таблицы раньше дочерних.
            for table, values in rows.items():
                if values:
                    s.execute(insert(table), values)

        self._write(write)
        return ids


@pytest.fixture(params=["memory", "postgres"])
def make(request: pytest.FixtureRequest, mechanics: Mechanics) -> Iterator[Callable[..., Harness]]:
    opened: list[PostgresHarness] = []

    def harness(acceptance: AcceptanceModel | None = None) -> Harness:
        model = acceptance or NoAcceptanceModel()
        if request.param == "memory":
            return MemoryHarness(model, mechanics)
        opened.append(PostgresHarness(request.getfixturevalue("db_engine"), model, mechanics))
        return opened[-1]

    yield harness
    for h in opened:
        h.uow.close()


@pytest.fixture
def mechanics() -> Mechanics:
    """Механики из репозитория — in-memory тестам база не нужна."""
    return Mechanics.from_yaml(BACKEND_DIR / "config" / "mechanics.yaml")


def remote(salary_from: int) -> Expectations:
    return Expectations(salary_from, (WorkFormat.remote,), None, False)


def test_build_puts_exact_above_nearby_and_cuts_by_category(make: Callable[..., Harness]) -> None:
    h = make()
    junior, middle, intern, other = h.candidates(
        [
            CandidateSeed(grade="junior", levels=dict.fromkeys(QA_TOPICS, (3.0, 0.2))),
            CandidateSeed(grade="middle"),
            CandidateSeed(grade="intern"),
            CandidateSeed(specialization="backend"),
        ]
    )

    page = h.selections.build(h.employer, h.need(), limit=20)

    assert dict(page.totals) == {SelectionBlock.exact: 1, SelectionBlock.nearby: 1}
    # Сильный «близкий» всё равно ниже точного: блоки не смешиваются.
    assert [(e.candidate_id, e.block, e.rank, e.position) for e in page.entries] == [
        (middle, SelectionBlock.exact, 1, 1),
        (junior, SelectionBlock.nearby, 1, 2),
    ]
    assert page.entries[0].grade.code == "middle"
    assert intern not in {e.candidate_id for e in page.entries}
    assert other not in {e.candidate_id for e in page.entries}


def test_stub_acceptance_keeps_order_by_match(make: Callable[..., Harness]) -> None:
    h = make()
    ids = h.candidates([CandidateSeed(levels={"qa.api": (0.3 * i - 1, 0.4)}) for i in range(6)])

    page = h.selections.build(h.employer, h.need(), limit=20)

    assert [e.candidate_id for e in page.entries] == ids[::-1]
    for entry in page.entries:
        assert entry.acceptance_probability is None
        assert entry.mutual_score == entry.match_score


def test_test_acceptance_model_orders_by_match_times_acceptance(
    make: Callable[..., Harness],
) -> None:
    model = SalaryFit()
    h = make(model)
    strong = dict.fromkeys(QA_TOPICS, (1.2, 0.3))
    h.candidates(
        [
            # Сильный, но ждёт вдвое больше вилки — P(принятия) низкая.
            CandidateSeed(levels=strong, stack=("pytest",), expectations=remote(600_000)),
            CandidateSeed(expectations=remote(250_000)),
            CandidateSeed(levels={"qa.api": (1.0, 0.4)}, expectations=remote(200_000)),
            # Без профиля кандидата ожиданий нет — константа модели.
            CandidateSeed(),
            CandidateSeed(grade="senior", levels=strong, expectations=remote(280_000)),
            CandidateSeed(grade="junior", expectations=remote(150_000)),
        ]
    )
    need = h.need(NeedSeed(salary=SalaryRange(250_000, 350_000)))

    entries = h.selections.build(h.employer, need, limit=20).entries

    assert len(entries) == 6
    for entry in entries:
        assert entry.acceptance_probability is not None
        assert entry.mutual_score == pytest.approx(entry.match_score * entry.acceptance_probability)
        explanation = entry.explanation
        contributions = [t.contribution for t in explanation.topics]
        assert sum(contributions) + explanation.stack.contribution == pytest.approx(
            entry.match_score, abs=1e-12
        )
    for block in (SelectionBlock.exact, SelectionBlock.nearby):
        mutual = [e.mutual_score for e in entries if e.block == block]
        assert mutual == sorted(mutual, reverse=True)
    exact = [e for e in entries if e.block == SelectionBlock.exact]
    # Порядок по S × P расходится с порядком по одному S — модель действительно влияет.
    assert [e.candidate_id for e in exact] != [
        e.candidate_id for e in sorted(exact, key=lambda e: -e.match_score)
    ]
    assert [e.block for e in entries] == [SelectionBlock.exact] * 4 + [SelectionBlock.nearby] * 2


def test_acceptance_model_gets_features_of_need_and_candidate(
    make: Callable[..., Harness],
) -> None:
    model = SalaryFit()
    h = make(model)
    candidate = h.candidate(
        CandidateSeed(
            grade="junior",
            stack=("pytest",),
            expectations=Expectations(
                220_000, (WorkFormat.office, WorkFormat.hybrid), "Казань", True
            ),
        )
    )
    need = h.need(
        NeedSeed(salary=SalaryRange(200_000, 300_000), work_format=WorkFormat.hybrid, city="Москва")
    )

    (entry,) = h.selections.build(h.employer, need, limit=20).entries

    assert entry.candidate_id == candidate
    (features,) = model.seen
    assert features == AcceptanceFeatures(
        salary=SalaryRange(200_000, 300_000),
        expected_salary=220_000,
        work_formats=(WorkFormat.office, WorkFormat.hybrid),
        city="Казань",
        relocation=True,
        need_work_format=WorkFormat.hybrid,
        need_city="Москва",
        grade="junior",
        match_score=entry.match_score,
    )


def test_open_returns_the_saved_output(make: Callable[..., Harness]) -> None:
    h = make()
    h.candidates([CandidateSeed(levels={"qa.api": (0.2 * i, 0.4)}) for i in range(5)])
    h.candidates([CandidateSeed(grade="senior") for _ in range(2)])
    need = h.need()
    built = h.selections.build(h.employer, need, limit=3)

    # Профили меняются после построения — сохранённая выдача нет.
    h.candidate(CandidateSeed(levels={"qa.api": (3.0, 0.2)}))
    whole = h.selections.open(h.employer, built.selection.id, offset=0, limit=100)

    assert built.entries == whole.entries[:3]
    assert built.selection == whole.selection
    assert [e.position for e in whole.entries] == list(range(1, 8))
    assert [e.rank for e in whole.entries] == [1, 2, 3, 4, 5, 1, 2]
    tail = h.selections.open(h.employer, built.selection.id, offset=5, limit=10)
    assert tail.entries == whole.entries[5:]
    assert tail.offset == 5


def test_foreign_need_and_selection_are_not_found(make: Callable[..., Harness]) -> None:
    h = make()
    stranger = h.user()
    need = h.need()
    built = h.selections.build(h.employer, need, limit=20)

    with pytest.raises(NeedNotFound):
        h.selections.build(stranger, need, limit=20)
    with pytest.raises(NeedNotFound):
        h.selections.build(h.employer, uuid.uuid4(), limit=20)
    with pytest.raises(SelectionNotFound):
        h.selections.open(stranger, built.selection.id, offset=0, limit=20)
    assert h.selections.summaries(stranger, None, limit=50) == []


def test_list_is_newest_first_and_filters_by_need(make: Callable[..., Harness]) -> None:
    h = make()
    h.candidate(CandidateSeed())
    first, second = h.need(), h.need(NeedSeed(grade="senior"))
    a = h.selections.build(h.employer, first, limit=20).selection
    h.clock.shift(timedelta(minutes=1))
    b = h.selections.build(h.employer, second, limit=20).selection
    h.clock.shift(timedelta(minutes=1))
    c = h.selections.build(h.employer, first, limit=20).selection

    listed = h.selections.summaries(h.employer, None, limit=50)
    assert [s.selection.id for s in listed] == [c.id, b.id, a.id]
    assert [dict(s.totals) for s in listed] == [
        {SelectionBlock.exact: 1, SelectionBlock.nearby: 0},
        {SelectionBlock.exact: 0, SelectionBlock.nearby: 1},
        {SelectionBlock.exact: 1, SelectionBlock.nearby: 0},
    ]
    by_need = h.selections.summaries(h.employer, first, limit=50)
    assert [s.selection.id for s in by_need] == [c.id, a.id]
    assert [s.selection.id for s in h.selections.summaries(h.employer, None, limit=1)] == [c.id]


def test_topic_missing_from_profile_counts_as_prior(
    make: Callable[..., Harness], mechanics: Mechanics
) -> None:
    h = make()
    h.candidate(CandidateSeed(levels={"qa.api": (1.5, 0.3)}, absent=("qa.performance",)))

    (entry,) = h.selections.build(h.employer, h.need(), limit=20).entries

    topics = {t.topic: t for t in entry.explanation.topics}
    missing = topics["qa.performance"]
    assert missing.theta == 0
    assert missing.theta_sd == pytest.approx(
        mechanics.level_sd_inflation
        * math.hypot(mechanics.theta_prior_sd, mechanics.topic_deviation_sd)
    )
    assert missing.low_data is True


def test_stale_profile_is_marked(make: Callable[..., Harness], mechanics: Mechanics) -> None:
    h = make()
    long_ago = T0 - timedelta(days=mechanics.profile_stale_days + 1)
    fresh, stale = h.candidates([CandidateSeed(), CandidateSeed(last_signal_at=long_ago)])

    entries = h.selections.build(h.employer, h.need(), limit=20).entries

    assert {e.candidate_id: e.stale for e in entries} == {fresh: False, stale: True}


class Boom(Exception):
    pass


class FailingModel:
    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        raise Boom()


class OutOfRange:
    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        return [1.5] * len(features)


@pytest.mark.parametrize("model", [FailingModel(), OutOfRange()])
def test_failed_build_leaves_no_selection(
    make: Callable[..., Harness], model: AcceptanceModel
) -> None:
    h = make(model)
    h.candidate(CandidateSeed())

    with pytest.raises((Boom, ValueError)):
        h.selections.build(h.employer, h.need(), limit=20)

    assert h.selections.summaries(h.employer, None, limit=50) == []


def test_build_on_1000_candidates_within_a_second(make: Callable[..., Harness]) -> None:
    h = make()
    grades = ["junior", "middle", "middle", "senior"]
    h.candidates(
        [
            CandidateSeed(
                grade=grades[i % 4],
                levels={"qa.api": ((i % 37) / 10 - 1.5, 0.3 + (i % 7) / 10)},
                stack=tuple(NEED_STACK[: i % 4]),
                expectations=remote(150_000 + 1000 * (i % 50)),
            )
            for i in range(1000)
        ]
    )
    need = h.need(NeedSeed(salary=SalaryRange(200_000, 260_000)))
    h.selections.build(h.employer, need, limit=20)  # прогрев

    timings = []
    for _ in range(3):
        started = time.perf_counter()
        page = h.selections.build(h.employer, need, limit=20)
        timings.append(time.perf_counter() - started)
        assert sum(page.totals.values()) == 1000

    elapsed = sorted(timings)[1]
    assert elapsed < 1.0, f"подборка на 1000 кандидатах строилась {elapsed:.2f} с"
