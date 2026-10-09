"""Сценарии подборки — «построить», «открыть», «список» — на портах (mechanics.md, §12–13).

Одни и те же тесты идут на in-memory репозиториях и на Postgres: кандидатов и потребности
обвязка кладёт прямо в хранилище, без HTTP и прохождения теста.
"""

import math
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from app.adapter import irt
from app.adapter.acceptance import NoAcceptanceModel, acceptance_model
from app.adapter.acceptance_catboost import fit
from app.adapter.catalog_file import load_catalog
from app.adapter.clock import FrozenClock
from app.adapter.seed import DerivedSeeds
from app.domain.acceptance import FACTORS
from app.domain.account import Role
from app.domain.candidate import GradeStatus, GradeStatusKind
from app.domain.catalog import CatalogRef, Grade, Specialization, Technology, Topic
from app.domain.errors import NeedNotFound, NotInSelection, SelectionNotFound
from app.domain.fsp import FspResult
from app.domain.invitation import OPEN, InvitationStatus
from app.domain.selection import (
    AcceptanceExplanation,
    AcceptanceFeatures,
    Expectations,
    Need,
    Page,
    PoolCandidate,
    SelectionBlock,
    SelectionOrder,
    UnconfirmedCandidate,
)
from app.domain.skill import Normal
from app.domain.work import SalaryRange, WorkFormat
from app.repository.catalog import SqlCatalog
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.selection import MemoryCandidatePool, MemoryNeeds, MemorySelections
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.repository.need import SqlNeeds
from app.repository.orm import (
    CandidateCategory,
    CandidateProfile,
    Company,
    FspAchievement,
    FspSnapshot,
    Invitation,
    SkillProfile,
    SkillProfileTopic,
    Survey,
    TestAttempt,
    User,
    candidate_industries,
    candidate_technologies,
)
from app.repository.orm import Need as NeedRow
from app.repository.orm import Technology as TechnologyRow
from app.repository.selection import SqlCandidatePool, SqlSelections
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import AcceptanceModel, SelectionRepository, UnitOfWork
from app.usecase.selection import Selections
from settings import CATALOG_FILE, Mechanics
from tests.test_acceptance_model import TRAINING, synthetic_offers
from validation.acceptance import rows

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
CATALOG = load_catalog(CATALOG_FILE)
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

    def explain(self, features: Sequence[AcceptanceFeatures]) -> list[AcceptanceExplanation | None]:
        return [
            AcceptanceExplanation(0.0, {**dict.fromkeys(FACTORS.values(), 0.0), "salary": z})
            for z in map(self.logit, features)
        ]

    @staticmethod
    def logit(f: AcceptanceFeatures) -> float:
        if f.salary is None or f.expected_salary is None:
            return 0.0
        middle = (f.salary.low + f.salary.high) / 2
        return 4 * (middle - f.expected_salary) / f.expected_salary

    @classmethod
    def probability(cls, f: AcceptanceFeatures) -> float:
        return 1 / (1 + math.exp(-cls.logit(f)))


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
    # Темы, по которым в профиль вошли ответы на регулярные задания.
    regular_task_topics: frozenset[str] = frozenset()
    # Заявленный грейд, если каскад дал категорию ниже: попытка на него и дотест на `grade`.
    claimed: str | None = None
    overall: Normal | None = None
    # Привязан ФСП ID и есть подтверждённое достижение.
    fsp: bool = False
    # Приглашения кандидату от других компаний: статус и сколько назад отправлено.
    invitations: tuple[tuple[InvitationStatus, timedelta], ...] = ()


# Общий уровень профиля в обвязке по умолчанию.
OVERALL = Normal(0.5, 0.4)


@dataclass
class UnconfirmedSeed:
    """Кандидат без категории: опрос, попытки цепочки и, если есть ожидания, профиль со стеком."""

    # Грейды цепочки попыток: первый — заявленный, дальше дотесты каскада; пусто — грейд не
    # выбран.
    chain: tuple[str, ...] = ("middle",)
    # None — опроса нет.
    specialization: str | None = "qa"
    # Специализация попыток; None — как у опроса.
    attempt_specialization: str | None = None
    stack: tuple[str, ...] = ()
    expectations: Expectations | None = None

    @property
    def claim(self) -> tuple[str, str] | None:
        """Специализация и заявленный грейд, с которыми кандидат попадает в нижний блок."""
        tested = self.attempt_specialization or self.specialization
        if self.specialization is None or not self.chain or tested != self.specialization:
            return None
        return self.specialization, self.chain[0]


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
    repository: SelectionRepository
    uow: UnitOfWork
    clock: FrozenClock

    def need(self, seed: NeedSeed | None = None, *, owner: uuid.UUID | None = None) -> uuid.UUID:
        raise NotImplementedError

    def candidate(self, seed: CandidateSeed) -> uuid.UUID:
        raise NotImplementedError

    def candidates(self, seeds: Sequence[CandidateSeed]) -> list[uuid.UUID]:
        return [self.candidate(s) for s in seeds]

    def unconfirmed(self, seed: UnconfirmedSeed) -> uuid.UUID:
        raise NotImplementedError

    def company(self, industry: str) -> None:
        """Профиль компании работодателя обвязки со сферой `industry`."""
        raise NotImplementedError

    def user(self) -> uuid.UUID:
        return uuid.uuid4()


def open_invitations(seed: CandidateSeed, ttl: timedelta) -> int:
    """Загрузка по приглашениям обвязки — как её считает домен приглашения."""
    return sum(status in OPEN and age < ttl for status, age in seed.invitations)


def _levels(seed: CandidateSeed) -> dict[str, Normal]:
    topics = [t.code for t in SPECIALIZATIONS[seed.specialization].topics]
    return {t: Normal(*seed.levels.get(t, (0.5, 0.5))) for t in topics if t not in seed.absent}


class MemoryHarness(Harness):
    def __init__(self, acceptance: AcceptanceModel, mechanics: Mechanics) -> None:
        self.ttl = timedelta(days=mechanics.invitation_ttl_days)
        store = MemoryStore()
        self.needs = MemoryNeeds(store)
        self.pool = MemoryCandidatePool(store)
        self.clock = FrozenClock(T0)
        self.employer = uuid.uuid4()
        self.uow = MemoryUnitOfWork(store)
        self.repository = MemorySelections(store)
        self.selections = Selections(
            self.uow,
            self.needs,
            MemoryCatalog(store),
            self.pool,
            self.repository,
            acceptance,
            irt,
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
            overall=seed.overall or OVERALL,
            levels=_levels(seed),
            stack=frozenset(seed.stack),
            last_signal_at=seed.last_signal_at,
            expectations=seed.expectations,
            regular_task_topics=seed.regular_task_topics,
            claimed=GRADES[seed.claimed] if seed.claimed else None,
            # В пуле достижений нет — есть темы, подтверждённые ФСП.
            fsp_topics=frozenset(QA_TOPICS[:1]) if seed.fsp else frozenset(),
        )
        self.pool.add(candidate)
        self.pool.set_open_invitations(candidate.candidate_id, open_invitations(seed, self.ttl))
        return candidate.candidate_id

    def company(self, industry: str) -> None:
        self.needs.put_company_industry(self.employer, industry)

    def unconfirmed(self, seed: UnconfirmedSeed) -> uuid.UUID:
        candidate_id = uuid.uuid4()
        if seed.claim is not None:
            specialization, claimed = seed.claim
            self.pool.add_unconfirmed(
                UnconfirmedCandidate(
                    candidate_id, specialization, GRADES[claimed], frozenset(seed.stack)
                )
            )
        return candidate_id


class PostgresHarness(Harness):
    uow: SqlUnitOfWork

    def __init__(self, engine: Engine, acceptance: AcceptanceModel, mechanics: Mechanics) -> None:
        self.engine = engine
        self.uow = SqlUnitOfWork(Session(engine))
        session = self.uow.session
        self.clock = FrozenClock(T0)
        self.repository = SqlSelections(session)
        self.selections = Selections(
            self.uow,
            SqlNeeds(session),
            SqlCatalog(session),
            SqlCandidatePool(session),
            self.repository,
            acceptance,
            irt,
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
            candidate_industries,
            FspSnapshot,
            FspAchievement,
            Invitation,
        )
        rows: dict[Any, list[dict[str, Any]]] = {table: [] for table in tables}
        ids = []
        for seed in seeds:
            uid, survey, profile = (uuid.uuid4() for _ in range(3))
            ids.append(uid)
            at = seed.last_signal_at
            spec = seed.specialization
            rows[User].append(
                self._user_row(uid, Role.candidate)
                | {"fsp_id": f"fsp-{uid.hex}" if seed.fsp else None}
            )
            if seed.fsp:
                rows[FspSnapshot].append({"user_id": uid, "fetched_at": at})
                rows[FspAchievement].append(
                    {
                        "user_id": uid,
                        "position": 0,
                        "event": "Чемпионат России по программированию",
                        "date": at.date(),
                        "discipline_code": "product",
                        "place": 1,
                        "result": FspResult.winner,
                    }
                )
            rows[Survey].append(
                {
                    "id": survey,
                    "user_id": uid,
                    "number": 1,
                    "specialization_code": spec,
                    "created_at": at,
                }
            )
            grades = (seed.claimed, seed.grade) if seed.claimed else (seed.grade,)
            attempt = self._chain(rows[TestAttempt], uid, survey, spec, grades, at)
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
                    "overall_theta": (seed.overall or OVERALL).mean,
                    "overall_theta_sd": (seed.overall or OVERALL).sd,
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
                    "regular_task": topic in seed.regular_task_topics,
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
                rows[candidate_industries].extend(
                    {"user_id": uid, "industry_code": i} for i in sorted(expectations.industries)
                )
            for status, age in seed.invitations:
                rows[Invitation].append(
                    {
                        "id": uuid.uuid4(),
                        "employer_id": self.employer,
                        "candidate_id": uid,
                        "company_name": "Другая компания",
                        "description": "",
                        "salary_from": 100_000,
                        "salary_to": 150_000,
                        "contact": "hr@example.com",
                        "status": status,
                        "sent_at": self.clock.now() - age,
                    }
                )

        def write(s: Session) -> None:
            # По порядку ключей — родительские таблицы раньше дочерних.
            for table, values in rows.items():
                if values:
                    s.execute(insert(table), values)

        self._write(write)
        return ids

    @staticmethod
    def _chain(
        rows: list[dict[str, Any]],
        user_id: uuid.UUID,
        survey: uuid.UUID,
        specialization: str,
        grades: Sequence[str],
        at: datetime,
    ) -> uuid.UUID:
        """Попытки цепочки: первая — на заявленный грейд, каждая следующая продолжает
        предыдущую; отдаёт id последней."""
        previous = None
        for number, grade in enumerate(grades, start=1):
            attempt = uuid.uuid4()
            rows.append(
                {
                    "id": attempt,
                    "user_id": user_id,
                    "number": number,
                    "survey_id": survey,
                    "specialization_code": specialization,
                    "grade_code": grade,
                    "continues_attempt_id": previous,
                    "started_at": at,
                }
            )
            previous = attempt
        assert previous is not None, "в цепочке хоть одна попытка"
        return previous

    def company(self, industry: str) -> None:
        row = {
            "user_id": self.employer,
            "name": "Компания",
            "industry_code": industry,
            "description": "",
            "website": None,
            "contact_email": "hr@example.com",
            "contact_phone": None,
            "updated_at": T0,
        }
        self._write(lambda s: s.execute(insert(Company), [row]))

    def unconfirmed(self, seed: UnconfirmedSeed) -> uuid.UUID:
        uid = self.user(Role.candidate)
        if seed.specialization is None:
            return uid
        survey = uuid.uuid4()
        attempts: list[dict[str, Any]] = []
        if seed.chain:
            spec = seed.attempt_specialization or seed.specialization
            self._chain(attempts, uid, survey, spec, seed.chain, T0)
        expectations = seed.expectations

        def write(s: Session) -> None:
            s.execute(
                insert(Survey),
                [
                    {
                        "id": survey,
                        "user_id": uid,
                        "number": 1,
                        "specialization_code": seed.specialization,
                        "created_at": T0,
                    }
                ],
            )
            # Цепочка — по одной: дотест ссылается на уже вставленную попытку.
            for row in attempts:
                s.execute(insert(TestAttempt), [row])
            if expectations is not None:
                s.execute(insert(CandidateProfile), [_profile_row(uid, expectations)])
            if seed.stack:
                s.execute(
                    insert(candidate_technologies),
                    [{"user_id": uid, "technology_code": t} for t in seed.stack],
                )

        self._write(write)
        return uid


def _profile_row(user_id: uuid.UUID, expectations: Expectations) -> dict[str, Any]:
    return {
        "user_id": user_id,
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
        "updated_at": T0,
    }


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.integration)])
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

    assert dict(page.totals) == {
        SelectionBlock.exact: 1,
        SelectionBlock.nearby: 1,
        SelectionBlock.unconfirmed: 0,
    }
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
        score, stack = entry.match_score, entry.explanation.stack.contribution
        assert entry.acceptance_probability is not None
        assert score is not None and stack is not None
        assert entry.mutual_score == pytest.approx(score * entry.acceptance_probability)
        contributions = [t.contribution for t in entry.explanation.topics]
        assert sum(contributions) + stack == pytest.approx(score, abs=1e-12)
    for block in (SelectionBlock.exact, SelectionBlock.nearby):
        mutual = [e.mutual_score or 0.0 for e in entries if e.block == block]
        assert mutual == sorted(mutual, reverse=True)
    exact = [e for e in entries if e.block == SelectionBlock.exact]
    # Порядок по S × P расходится с порядком по одному S — модель действительно влияет.
    assert [e.candidate_id for e in exact] != [
        e.candidate_id for e in sorted(exact, key=lambda e: -(e.match_score or 0.0))
    ]
    assert [e.block for e in entries] == [SelectionBlock.exact] * 4 + [SelectionBlock.nearby] * 2


@pytest.fixture(scope="module")
def model_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Файл модели принятия CatBoost, обученной на синтетических решениях."""
    offers = synthetic_offers(2000, seed=11)
    path = tmp_path_factory.mktemp("acceptance") / "model.cbm"
    fit(rows(offers), [o.accepted for o in offers], TRAINING).save(path)
    return path


def test_with_model_file_orders_by_match_times_acceptance(
    make: Callable[..., Harness], model_file: Path
) -> None:
    h = make(acceptance_model(model_file))
    strong = dict.fromkeys(QA_TOPICS, (1.2, 0.3))
    h.candidates(
        [
            # Сильный, но ждёт вдвое больше вилки и завален приглашениями.
            CandidateSeed(
                levels=strong,
                expectations=remote(600_000),
                invitations=((InvitationStatus.sent, timedelta(days=1)),) * 6,
            ),
            CandidateSeed(expectations=remote(250_000)),
            CandidateSeed(levels={"qa.api": (1.0, 0.4)}, expectations=remote(200_000)),
            CandidateSeed(),
        ]
    )
    need = h.need(NeedSeed(salary=SalaryRange(250_000, 350_000)))

    entries = h.selections.build(h.employer, need, limit=20).entries

    assert len(entries) == 4
    for entry in entries:
        assert entry.acceptance_probability is not None
        assert entry.match_score is not None
        assert 0 <= entry.acceptance_probability <= 1
        assert entry.mutual_score == pytest.approx(entry.match_score * entry.acceptance_probability)
    mutual = [e.mutual_score or 0.0 for e in entries]
    assert mutual == sorted(mutual, reverse=True)
    by_match = sorted(entries, key=lambda e: -(e.match_score or 0.0))
    assert [e.candidate_id for e in entries] != [e.candidate_id for e in by_match]


def test_without_model_file_multiplier_is_one(make: Callable[..., Harness], tmp_path: Path) -> None:
    h = make(acceptance_model(tmp_path / "missing.cbm"))
    ids = h.candidates(
        [
            CandidateSeed(levels={"qa.api": (0.3 * i - 1, 0.4)}, expectations=remote(250_000))
            for i in range(4)
        ]
    )

    entries = h.selections.build(
        h.employer, h.need(NeedSeed(salary=SalaryRange(250_000, 350_000))), limit=20
    ).entries

    assert [e.candidate_id for e in entries] == ids[::-1]
    for entry in entries:
        assert entry.acceptance_probability is None
        assert entry.mutual_score == entry.match_score


def test_with_model_file_need_without_salary_keeps_order_by_match(
    make: Callable[..., Harness], model_file: Path
) -> None:
    h = make(acceptance_model(model_file))
    ids = h.candidates(
        [
            CandidateSeed(levels={"qa.api": (0.3 * i - 1, 0.4)}, expectations=remote(250_000))
            for i in range(4)
        ]
    )

    entries = h.selections.build(h.employer, h.need(), limit=20).entries

    assert [e.candidate_id for e in entries] == ids[::-1]
    assert all(e.acceptance_probability is None for e in entries)


def test_acceptance_model_gets_features_of_need_and_candidate(
    make: Callable[..., Harness], mechanics: Mechanics
) -> None:
    model = SalaryFit()
    h = make(model)
    h.company("fintech")
    ttl = timedelta(days=mechanics.invitation_ttl_days)
    candidate = h.candidate(
        CandidateSeed(
            grade="junior",
            stack=("pytest",),
            expectations=Expectations(
                220_000,
                (WorkFormat.office, WorkFormat.hybrid),
                "Казань",
                True,
                frozenset({"fintech", "education"}),
            ),
            # Открытые — отправленное и просмотренное в сроке; истёкшее и отклонённое — нет.
            invitations=(
                (InvitationStatus.sent, timedelta(days=1)),
                (InvitationStatus.viewed, ttl - timedelta(minutes=1)),
                (InvitationStatus.sent, ttl),
                (InvitationStatus.declined, timedelta(days=1)),
            ),
        )
    )
    need = h.need(
        NeedSeed(salary=SalaryRange(200_000, 300_000), work_format=WorkFormat.hybrid, city="Москва")
    )

    (entry,) = h.selections.build(h.employer, need, limit=20).entries

    assert entry.candidate_id == candidate
    assert entry.match_score is not None
    (features,) = model.seen
    assert features == AcceptanceFeatures(
        salary=SalaryRange(200_000, 300_000),
        expected_salary=220_000,
        market_salary=mechanics.market_salary_median["junior"],
        work_formats=(WorkFormat.office, WorkFormat.hybrid),
        city="Казань",
        relocation=True,
        need_work_format=WorkFormat.hybrid,
        need_city="Москва",
        grade="junior",
        match_score=entry.match_score,
        open_invitations=2,
        industries=frozenset({"fintech", "education"}),
        company_industry="fintech",
    )


def test_acceptance_features_without_profile_and_company(
    make: Callable[..., Harness], mechanics: Mechanics
) -> None:
    model = SalaryFit()
    h = make(model)
    h.candidate(CandidateSeed())

    h.selections.build(h.employer, h.need(NeedSeed(salary=SalaryRange(1, 2))), limit=20)

    (features,) = model.seen
    assert (features.expected_salary, features.industries, features.company_industry) == (
        None,
        frozenset(),
        None,
    )
    assert features.open_invitations == 0


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
        {SelectionBlock.exact: 1, SelectionBlock.nearby: 0, SelectionBlock.unconfirmed: 0},
        {SelectionBlock.exact: 0, SelectionBlock.nearby: 1, SelectionBlock.unconfirmed: 0},
        {SelectionBlock.exact: 1, SelectionBlock.nearby: 0, SelectionBlock.unconfirmed: 0},
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


def test_profile_is_brought_to_now_before_scoring(
    make: Callable[..., Harness], mechanics: Mechanics
) -> None:
    """Свежесть (§11): без сигналов погрешность растёт на sd_год² за год, уровень остаётся, а
    уверенность выше требования падает."""
    h = make()
    years = 2
    long_ago = T0 - timedelta(days=365.25 * years)
    levels = {"qa.api": (1.5, 0.3)}
    fresh, old = h.candidates(
        [CandidateSeed(levels=levels), CandidateSeed(levels=levels, last_signal_at=long_ago)]
    )

    entries = h.selections.build(h.employer, h.need(), limit=20).entries

    api = {
        e.candidate_id: next(t for t in e.explanation.topics if t.topic == "qa.api")
        for e in entries
    }
    assert api[old].theta == api[fresh].theta == 1.5
    assert api[fresh].theta_sd == pytest.approx(0.3)
    assert api[old].theta_sd ** 2 == pytest.approx(
        0.3**2 + years * mechanics.profile_decay_sd_per_year**2
    )
    assert api[old].probability < api[fresh].probability


def test_regular_task_is_a_source_of_confidence_by_topic(make: Callable[..., Harness]) -> None:
    h = make()
    h.candidate(CandidateSeed(regular_task_topics=frozenset({"qa.api"})))

    (entry,) = h.selections.build(h.employer, h.need(), limit=20).entries

    confirmed = {t.topic for t in entry.explanation.topics if t.regular_task}
    assert confirmed == {"qa.api"}


class Boom(Exception):
    pass


class FailingModel:
    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        raise Boom()

    def explain(self, features: Sequence[AcceptanceFeatures]) -> list[AcceptanceExplanation | None]:
        raise Boom()


class OutOfRange:
    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        return [1.5] * len(features)

    def explain(self, features: Sequence[AcceptanceFeatures]) -> list[AcceptanceExplanation | None]:
        return [None] * len(features)


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


def test_claimed_grade_without_category_is_shown_in_the_bottom_block(
    make: Callable[..., Harness],
) -> None:
    h = make()
    exact, nearby = h.candidates([CandidateSeed(), CandidateSeed(grade="junior")])
    full = h.unconfirmed(
        UnconfirmedSeed(stack=("playwright", "pytest"), expectations=remote(200_000))
    )
    bare = h.unconfirmed(UnconfirmedSeed())
    need = h.need()

    page = h.selections.build(h.employer, need, limit=20)

    assert [(e.candidate_id, e.block) for e in page.entries] == [
        (exact, SelectionBlock.exact),
        (nearby, SelectionBlock.nearby),
        (full, SelectionBlock.unconfirmed),
        (bare, SelectionBlock.unconfirmed),
    ]
    assert page.totals[SelectionBlock.unconfirmed] == 2
    bottom = page.entries[2]
    assert bottom.status == GradeStatus(
        GradeStatusKind.unconfirmed, CatalogRef("middle", "Middle"), None
    )
    assert (bottom.match_score, bottom.mutual_score, bottom.acceptance_probability) == (
        None,
        None,
        None,
    )
    assert bottom.explanation.topics == ()
    assert bottom.explanation.stack.matched == ("playwright", "pytest")
    assert [e.status.kind for e in page.entries[:2]] == [GradeStatusKind.confirmed] * 2


def test_category_below_the_claim_stays_in_the_main_blocks(make: Callable[..., Harness]) -> None:
    h = make()
    cascaded = h.candidate(CandidateSeed(grade="junior", claimed="middle"))

    (entry,) = h.selections.build(h.employer, h.need(), limit=20).entries

    assert (entry.candidate_id, entry.block) == (cascaded, SelectionBlock.nearby)
    assert entry.status == GradeStatus(
        GradeStatusKind.below_claimed,
        CatalogRef("middle", "Middle"),
        CatalogRef("junior", "Junior"),
    )
    assert entry.grade == CatalogRef("junior", "Junior")


def test_cascade_without_category_keeps_the_first_claim(make: Callable[..., Harness]) -> None:
    """Дотест на junior после попытки на middle заявку не меняет: кандидат — в нижнем блоке
    потребности middle и не попадает в нижний блок junior."""
    h = make()
    candidate = h.unconfirmed(UnconfirmedSeed(chain=("middle", "junior")))

    middle = h.selections.build(h.employer, h.need(), limit=20).entries
    junior = h.selections.build(h.employer, h.need(NeedSeed(grade="junior")), limit=20).entries

    assert [(e.candidate_id, e.block) for e in middle] == [(candidate, SelectionBlock.unconfirmed)]
    assert junior == ()


@pytest.mark.parametrize(
    "seed",
    [
        pytest.param(UnconfirmedSeed(specialization=None), id="без опроса"),
        pytest.param(UnconfirmedSeed(chain=()), id="грейд не заявлен"),
        pytest.param(UnconfirmedSeed(chain=("junior",)), id="заявлен другой грейд"),
        pytest.param(UnconfirmedSeed(chain=("senior",)), id="заявлен соседний грейд"),
        pytest.param(UnconfirmedSeed(specialization="backend"), id="другая специализация"),
        pytest.param(
            UnconfirmedSeed(specialization="qa", attempt_specialization="backend"),
            id="попытка по прошлому опросу",
        ),
    ],
)
def test_who_is_not_in_the_bottom_block(
    make: Callable[..., Harness], seed: UnconfirmedSeed
) -> None:
    h = make()
    h.unconfirmed(seed)

    assert h.selections.build(h.employer, h.need(), limit=20).entries == ()


def test_open_reproduces_the_bottom_block_and_its_total(make: Callable[..., Harness]) -> None:
    h = make()
    h.candidates([CandidateSeed() for _ in range(2)])
    for stack in (("pytest",), (), ("playwright", "pytest")):
        h.unconfirmed(UnconfirmedSeed(stack=stack, expectations=remote(200_000)))
    need = h.need()
    built = h.selections.build(h.employer, need, limit=20)

    # Страница на стыке блоков: подтверждённый последний, нижний — после него.
    page = h.selections.open(h.employer, built.selection.id, offset=1, limit=2)
    (summary,) = h.selections.summaries(h.employer, need, limit=10)

    assert page.entries == built.entries[1:3]
    assert [e.block for e in page.entries] == [SelectionBlock.exact, SelectionBlock.unconfirmed]
    assert page.totals == built.totals == summary.totals
    assert built.totals[SelectionBlock.unconfirmed] == 3


# Подборки по кандидату — для обратной связи (§15).


def test_selections_with_candidate_give_place_block_and_same_block_neighbors(
    make: Callable[..., Harness],
) -> None:
    h = make()
    me, peer, far = h.candidates(
        [
            CandidateSeed(levels={t: (0.6, 0.4) for t in QA_TOPICS}),
            CandidateSeed(levels={t: (1.2, 0.3) for t in QA_TOPICS}),
            CandidateSeed(grade="senior"),
        ]
    )
    stranger = h.candidate(CandidateSeed(specialization="backend"))
    need = h.need()
    page = h.selections.build(h.employer, need, limit=20)
    scores = {e.candidate_id: e.match_score for e in page.entries}
    position = {e.candidate_id: e.position for e in page.entries}

    with h.uow:
        (found,) = h.repository.with_candidate(me, T0)
        assert h.repository.with_candidate(stranger, T0) == []

    assert found.selection_id == page.selection.id
    assert found.owner == h.employer
    assert found.need_id == need
    assert found.need == page.selection.need
    assert found.stack_cap == page.selection.stack_cap
    assert found.created_at == page.selection.created_at
    assert (found.position, found.block) == (position[me], SelectionBlock.exact)
    # Только тот же блок: кандидат senior — в «близких».
    assert far in scores
    assert found.neighbors == (scores[peer],)


def test_selections_with_candidate_are_within_window_and_by_time(
    make: Callable[..., Harness],
) -> None:
    h = make()
    me = h.candidate(CandidateSeed())
    other = h.user()
    old = h.selections.build(h.employer, h.need(), limit=20).selection
    h.clock.shift(timedelta(days=10))
    first = h.selections.build(other, h.need(owner=other), limit=20).selection
    h.clock.shift(timedelta(minutes=1))
    second = h.selections.build(h.employer, h.need(), limit=20).selection

    with h.uow:
        found = h.repository.with_candidate(me, T0 + timedelta(days=1))

    assert old.id not in {s.selection_id for s in found}
    assert [(s.selection_id, s.owner) for s in found] == [
        (first.id, other),
        (second.id, h.employer),
    ]


def salary_fit_page(h: Harness) -> tuple[uuid.UUID, Page]:
    strong = dict.fromkeys(QA_TOPICS, (1.2, 0.3))
    h.candidates(
        [
            CandidateSeed(levels=strong, stack=("pytest",), expectations=remote(600_000)),
            CandidateSeed(expectations=remote(250_000)),
            CandidateSeed(levels={"qa.api": (1.0, 0.4)}, expectations=remote(200_000)),
            CandidateSeed(grade="junior", expectations=remote(150_000)),
        ]
    )
    page = h.selections.build(
        h.employer, h.need(NeedSeed(salary=SalaryRange(250_000, 350_000))), limit=20
    )
    return page.selection.id, page


def test_match_order_sorts_each_block_by_match_only(make: Callable[..., Harness]) -> None:
    h = make(SalaryFit())
    selection_id, page = salary_fit_page(h)

    mutual = h.selections.open(h.employer, selection_id, offset=0, limit=20)
    match = h.selections.open(
        h.employer, selection_id, offset=0, limit=20, order=SelectionOrder.match
    )

    assert mutual.entries == page.entries
    assert [e.candidate_id for e in match.entries] != [e.candidate_id for e in mutual.entries]
    assert [e.block for e in match.entries] == [e.block for e in mutual.entries]
    for block in (SelectionBlock.exact, SelectionBlock.nearby):
        scores = [e.match_score or 0.0 for e in match.entries if e.block == block]
        assert scores == sorted(scores, reverse=True)
    assert [e.position for e in match.entries] == list(range(1, len(match.entries) + 1))
    for block in (SelectionBlock.exact, SelectionBlock.nearby):
        assert [e.rank for e in match.entries if e.block == block] == list(
            range(1, sum(e.block == block for e in match.entries) + 1)
        )
    # Сохранённая выдача от переключателя не меняется.
    again = h.selections.open(h.employer, selection_id, offset=0, limit=20)
    assert again.entries == mutual.entries
    assert {e.candidate_id: e.acceptance_probability for e in match.entries} == {
        e.candidate_id: e.acceptance_probability for e in mutual.entries
    }


def test_match_order_keeps_unconfirmed_block_last(make: Callable[..., Harness]) -> None:
    h = make(SalaryFit())
    h.candidates([CandidateSeed(expectations=remote(250_000)), CandidateSeed(grade="junior")])
    h.unconfirmed(UnconfirmedSeed())
    need = h.need(NeedSeed(salary=SalaryRange(250_000, 350_000)))
    selection_id = h.selections.build(h.employer, need, limit=20).selection.id

    page = h.selections.open(
        h.employer, selection_id, offset=0, limit=20, order=SelectionOrder.match
    )

    assert page.entries[-1].block == SelectionBlock.unconfirmed
    assert page.entries[-1].match_score is None


def test_entries_carry_additive_explanation(make: Callable[..., Harness]) -> None:
    h = make(SalaryFit())
    _, page = salary_fit_page(h)

    for entry in page.entries:
        assert entry.acceptance is not None and entry.acceptance_probability is not None
        why = entry.acceptance.explanation
        assert 1 / (1 + math.exp(-why.logit)) == pytest.approx(entry.acceptance_probability)
        assert why.base + sum(why.contributions.values()) == pytest.approx(why.logit, abs=1e-6)


def test_salary_hint_for_entry_uses_stored_features(make: Callable[..., Harness]) -> None:
    h = make(SalaryFit())
    selection_id, page = salary_fit_page(h)
    entry = next(
        e for e in page.entries if e.acceptance and e.acceptance.features.expected_salary == 250_000
    )

    found = h.selections.salary_hint(
        h.employer, selection_id, entry.candidate_id, SalaryRange(100_000, 150_000)
    )

    assert found is not None
    assert found.evaluated == SalaryRange(100_000, 150_000)
    assert found.probability < 0.6
    assert found.range is not None
    assert found.range.low % 10_000 == 0 and found.range.high % 10_000 == 0
    assert (
        SalaryFit.probability(
            replace(entry.acceptance.features, salary=found.range)  # type: ignore[union-attr]
        )
        >= 0.6
    )
    # Ожидание кандидата в подсказке не отдаётся.
    assert not hasattr(found, "expected_salary")


def test_salary_hint_unreachable_target(make: Callable[..., Harness]) -> None:
    h = make(SalaryFit())
    selection_id, page = salary_fit_page(h)
    # Кандидат ждёт 600 000, сетка кончается на трёх рыночных медианах грейда (около 575 000).
    entry = next(
        e for e in page.entries if e.acceptance and e.acceptance.features.expected_salary == 600_000
    )

    found = h.selections.salary_hint(
        h.employer, selection_id, entry.candidate_id, SalaryRange(100_000, 150_000)
    )

    assert found is not None
    assert found.range is None


def test_salary_hint_of_foreign_candidate_is_not_in_selection(
    make: Callable[..., Harness],
) -> None:
    h = make(SalaryFit())
    selection_id, _ = salary_fit_page(h)

    with pytest.raises(NotInSelection):
        h.selections.salary_hint(h.employer, selection_id, uuid.uuid4(), SalaryRange(1, 2))


def test_without_model_there_is_no_hint_and_no_error(make: Callable[..., Harness]) -> None:
    h = make()
    selection_id, page = salary_fit_page(h)

    assert page.entries
    for entry in page.entries:
        assert entry.acceptance is None and entry.acceptance_probability is None
        assert (
            h.selections.salary_hint(
                h.employer, selection_id, entry.candidate_id, SalaryRange(100_000, 150_000)
            )
            is None
        )
    match = h.selections.open(
        h.employer, selection_id, offset=0, limit=20, order=SelectionOrder.match
    )
    assert [e.mutual_score for e in match.entries] == [e.match_score for e in match.entries]
