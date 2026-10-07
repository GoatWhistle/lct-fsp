"""Потребности работодателя: заведение, правка, удаление и важность тем (mechanics.md, §12).

Работодатель видит и меняет только свои потребности: чужая для него не существует — 404, а не
403, чтобы не раскрывать, что такая есть.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.assessment.models import Grade as GradeRow
from app.assessment.models import Specialization as SpecializationRow
from app.assessment.models import Technology
from app.config import Mechanics
from app.domain.catalog import CatalogRef, Specialization, Topic
from app.domain.errors import (
    CityRequired,
    InvalidSalaryRange,
    NeedNotFound,
    TopicNotInSpecialization,
    UnknownGrade,
    UnknownSpecialization,
    UnknownTechnology,
)
from app.domain.work import SalaryRange, WorkFormat
from app.matching.importance import TopicImportance, topic_importance
from app.matching.models import Need, NeedTopicImportance
from app.matching.schemas import NeedIn, TopicImportanceIn
from app.repository.catalog import ref_of, specialization_of
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import Clock


@dataclass(frozen=True)
class TopicView:
    topic: Topic
    importance: TopicImportance
    edited: bool
    technologies: list[CatalogRef]


NEED_ERRORS = (
    UnknownSpecialization,
    UnknownGrade,
    UnknownTechnology,
    TopicNotInSpecialization,
    InvalidSalaryRange,
    CityRequired,
)


def list_needs(db: Session, user_id: uuid.UUID) -> list[Need]:
    return list(
        db.scalars(
            select(Need)
            .where(Need.user_id == user_id)
            .options(
                selectinload(Need.specialization).selectinload(SpecializationRow.topics),
                selectinload(Need.grade),
                selectinload(Need.stack).selectinload(Technology.topics),
                selectinload(Need.edited_importance),
            )
            .order_by(Need.created_at.desc())
        )
    )


def get_need(db: Session, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
    need = db.get(Need, need_id)
    if need is None or need.user_id != user_id:
        raise NeedNotFound()
    return need


def create_need(uow: SqlUnitOfWork, user_id: uuid.UUID, data: NeedIn, clock: Clock) -> Need:
    with uow:
        db = uow.session
        now = clock.now()
        need = Need(user_id=user_id, created_at=now, updated_at=now)
        _fill(db, need, data)
        db.add(need)
        return need


def update_need(
    uow: SqlUnitOfWork, user_id: uuid.UUID, need_id: uuid.UUID, data: NeedIn, clock: Clock
) -> Need:
    with uow:
        db = uow.session
        need = get_need(db, user_id, need_id)
        _fill(db, need, data)
        # Стек и правки важности лежат в своих таблицах: строка потребности может не измениться.
        need.updated_at = clock.now()
        return need


def delete_need(uow: SqlUnitOfWork, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
    with uow:
        db = uow.session
        db.delete(get_need(db, user_id, need_id))


def need_topics(need: Need, mechanics: Mechanics) -> list[TopicView]:
    edited = {row.topic_code: row.importance for row in need.edited_importance}
    return _rows(specialization_of(need.specialization), need.stack, edited, mechanics)


def preview_topics(db: Session, data: TopicImportanceIn, mechanics: Mechanics) -> list[TopicView]:
    """Важность тем по стеку до сохранения — форма показывает её, пока работодатель выбирает."""
    specialization = _specialization(db, data.specialization)
    stack = _technologies(db, data.stack)
    _check_topics(specialization, data.topic_importance)
    return _rows(specialization, stack, data.topic_importance, mechanics)


def _fill(db: Session, need: Need, data: NeedIn) -> None:
    specialization = _specialization(db, data.specialization)
    if db.get(GradeRow, data.grade) is None:
        raise UnknownGrade()
    stack = _technologies(db, data.stack)
    _check_topics(specialization, data.topic_importance)
    salary = SalaryRange.optional(data.salary_from, data.salary_to)
    city = data.city or None
    if city is None and data.work_format != WorkFormat.remote:
        raise CityRequired()

    need.title = data.title
    need.team_description = data.team_description
    need.specialization_code = specialization.code
    need.grade_code = data.grade
    need.work_format = data.work_format
    need.city = city
    need.salary_from = salary.low if salary else None
    need.salary_to = salary.high if salary else None
    need.stack = stack
    need.edited_importance = [
        NeedTopicImportance(topic_code=topic, importance=importance)
        for topic, importance in data.topic_importance.items()
    ]


def _specialization(db: Session, code: str) -> Specialization:
    row = db.get(SpecializationRow, code)
    if row is None:
        raise UnknownSpecialization()
    return specialization_of(row)


def _technologies(db: Session, codes: list[str]) -> list[Technology]:
    unique = set(codes)
    technologies = list(
        db.scalars(
            select(Technology)
            .where(Technology.code.in_(unique))
            .options(selectinload(Technology.topics))
            .order_by(Technology.name)
        )
    )
    if len(technologies) != len(unique):
        raise UnknownTechnology()
    return technologies


def _check_topics(specialization: Specialization, edited: dict[str, TopicImportance]) -> None:
    if set(edited) - {t.code for t in specialization.topics}:
        raise TopicNotInSpecialization()


def _rows(
    specialization: Specialization,
    stack: list[Technology],
    edited: dict[str, TopicImportance],
    mechanics: Mechanics,
) -> list[TopicView]:
    rows = topic_importance(
        [t.code for t in specialization.topics],
        {tech.code: {t.code for t in tech.topics} for tech in stack},
        edited,
        key_min_technologies=mechanics.need_key_topic_min_technologies,
    )
    technologies = {tech.code: ref_of(tech) for tech in stack}
    return [
        TopicView(topic, row.importance, row.edited, [technologies[c] for c in row.technologies])
        for topic, row in zip(specialization.topics, rows, strict=True)
    ]
