"""Окна показов и связки на обеих реализациях хранилища (mechanics.md, §6, §7).

Окно показов — попытки по специализации, где было хотя бы одно предъявление, включая идущие:
задание раскрыто показом. Окно связки — только остановленные попытки: итоговая оценка без
ответа есть только у них.
"""

import uuid
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.assessment.catalog import load_catalog
from app.config import Mechanics, Settings
from app.domain.attempt import Attempt, AttemptOutcome
from app.domain.bank import families_for_topics
from app.domain.catalog import Grade, Specialization, Topic
from app.domain.skill import Normal
from app.identity.models import Role, User
from app.repository.attempt import SqlAttemptRepository
from app.repository.calibration import SqlCalibrationRepository
from app.repository.memory.attempt import MemoryAttemptRepository
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import AttemptRepository, CalibrationRepository, UnitOfWork

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = load_catalog()
GRADES = {g.code: Grade(g.code, g.name, g.rank) for g in CATALOG.grades}
SPECIALIZATIONS = {
    s.code: Specialization(s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics))
    for s in CATALOG.specializations
}
QA_TOPICS = [t.code for t in SPECIALIZATIONS["qa"].topics]
REGULAR = next(f for f in families_for_topics(QA_TOPICS) if not f.anchor)
ANCHOR = next(f for f in families_for_topics(QA_TOPICS) if f.anchor)


@dataclass
class Storage:
    uow: UnitOfWork
    attempts: AttemptRepository
    calibration: CalibrationRepository
    new_user: Callable[[], uuid.UUID]


@pytest.fixture(params=["memory", "postgres"])
def storage(request: pytest.FixtureRequest) -> Iterator[Storage]:
    if request.param == "memory":
        store = MemoryStore()
        yield Storage(
            MemoryUnitOfWork(store),
            MemoryAttemptRepository(
                store,
                SPECIALIZATIONS,
                GRADES,
                MECHANICS.grade_thresholds,
                MECHANICS.grade_confidence,
            ),
            MemoryCalibrationRepository(store),
            uuid.uuid4,
        )
        return
    engine: Engine = request.getfixturevalue("db_engine")
    with closing(SqlUnitOfWork(Session(engine))) as uow:

        def new_user() -> uuid.UUID:
            user = User(
                email=f"candidate-{uuid.uuid4().hex[:8]}@example.com",
                password_hash="-",
                role=Role.candidate,
                created_at=T0,
            )
            uow.session.add(user)
            uow.session.flush()
            return user.id

        yield Storage(
            uow,
            SqlAttemptRepository(
                uow.session, MECHANICS.grade_thresholds, MECHANICS.grade_confidence
            ),
            SqlCalibrationRepository(uow.session),
            new_user,
        )


def attempt(
    storage: Storage,
    started: int,
    *,
    families: tuple[str, ...] = (),
    answered: bool = False,
    finished: int | None = None,
) -> Attempt:
    """Попытка кандидата по qa, начатая через `started` минут после T0: предъявления семейств
    `families`, верные ответы на них при `answered` и остановка через `finished` минут после
    T0."""
    attempts = storage.attempts
    now = T0 + timedelta(minutes=started)
    user = storage.new_user()
    survey = attempts.add_survey(user, "qa", now)
    new = attempts.add_attempt(user, survey, "middle", None, now)
    for code in families:
        family = next(f for f in families_for_topics(QA_TOPICS) if f.code == code)
        p = attempts.add_presentation(
            new,
            family_code=code,
            topic_code=family.topic,
            seed=0,
            params={},
            discrimination=1.0,
            difficulty=0.0,
            level_before=Normal(0.0, 1.0),
            shown_at=now,
        )
        if answered:
            p.response, p.correct, p.answered_at, p.response_time_ms = "-", True, now, 0
            attempts.save_answer(p)
            if finished is not None:
                p.topic_theta_rest, p.topic_theta_rest_sd = 0.0, 0.5
    if finished is not None:
        new.finished_at = T0 + timedelta(minutes=finished)
        new.overall = Normal(0.0, 0.4)
        new.outcome, new.outcome_grade_code = AttemptOutcome.assigned, "middle"
        attempts.finish_attempt(new)
        attempts.save_rest_levels(new.presentations)
    return new


def test_exposure_window_skips_attempts_without_presentations(storage: Storage) -> None:
    """Попытка без предъявлений места в окне показов не занимает: окно из трёх попыток — две
    прошлые с показами, хотя после них начата пустая."""
    with storage.uow:
        attempt(storage, 0, families=(REGULAR.code,), finished=10)
        attempt(storage, 1, families=(REGULAR.code,), finished=10)
        attempt(storage, 2)
        current = attempt(storage, 3, families=(ANCHOR.code,))

        window, shown = storage.attempts.exposure("qa", current.id, 3)

    assert (window, shown) == (2, {REGULAR.code: 2})


def test_exposure_window_counts_attempts_in_progress(storage: Storage) -> None:
    """Задание раскрыто показом, а не остановкой: идущая попытка с предъявлением — в окне."""
    with storage.uow:
        attempt(storage, 0, families=(REGULAR.code,))
        current = attempt(storage, 1)

        window, shown = storage.attempts.exposure("qa", current.id, 3)

    assert (window, shown) == (1, {REGULAR.code: 1})


def test_link_window_takes_only_finished_attempts(storage: Storage) -> None:
    """Неостановленная попытка с ответами на якоря в окно связки не входит и места в нём не
    занимает: окно из одной попытки — последняя остановленная."""
    with storage.uow:
        attempt(storage, 0, families=(ANCHOR.code,), answered=True, finished=10)
        attempt(storage, 1, families=(ANCHOR.code,), answered=True)

        answers = storage.calibration.anchor_answers("qa", [ANCHOR.code], 1)

    assert len(answers) == 1
    assert answers[0].rest is not None


def test_link_window_is_ordered_by_stop(storage: Storage) -> None:
    """Окно связки — последние по остановке: долгая попытка, начатая раньше, но остановленная
    последней, в окно своей связки попадает."""
    with storage.uow:
        attempt(storage, 0, families=(ANCHOR.code,), answered=True, finished=20)
        attempt(storage, 1, families=(REGULAR.code,), answered=True, finished=10)

        answers = storage.calibration.anchor_answers("qa", [ANCHOR.code], 1)

    assert len(answers) == 1
