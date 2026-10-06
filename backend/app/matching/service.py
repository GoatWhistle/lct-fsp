"""Потребности работодателя: заведение, правка, удаление и важность тем (mechanics.md, §12).

Работодатель видит и меняет только свои потребности: чужая для него не существует — 404, а не
403, чтобы не раскрывать, что такая есть.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.assessment.models import Grade, Specialization, Technology, Topic
from app.assessment.service import UnknownGrade, UnknownSpecialization
from app.config import Mechanics
from app.errors import AppError
from app.matching.importance import TopicImportance, topic_importance
from app.matching.models import Need, NeedTopicImportance, WorkFormat
from app.matching.schemas import NeedIn, TopicImportanceIn


class NeedNotFound(AppError):
    status_code = 404
    code = "need_not_found"
    message = "Потребность не найдена — возможно, её удалили"


class UnknownTechnology(AppError):
    status_code = 422
    code = "unknown_technology"
    message = "Такой технологии нет в справочнике"


class TopicNotInSpecialization(AppError):
    status_code = 422
    code = "topic_not_in_specialization"
    message = "Важность задаётся только темам специализации потребности"


class InvalidSalaryRange(AppError):
    status_code = 422
    code = "invalid_salary_range"
    message = "Вилка — обе границы больше нуля, «от» не больше «до»"


class CityRequired(AppError):
    status_code = 422
    code = "city_required"
    message = "Укажите город — для офиса и гибрида он обязателен"


@dataclass(frozen=True)
class TopicView:
    topic: Topic
    importance: TopicImportance
    edited: bool
    technologies: list[Technology]


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
        db.scalars(select(Need).where(Need.user_id == user_id).order_by(Need.created_at.desc()))
    )


def get_need(db: Session, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
    need = db.get(Need, need_id)
    if need is None or need.user_id != user_id:
        raise NeedNotFound()
    return need


def create_need(db: Session, user_id: uuid.UUID, data: NeedIn) -> Need:
    need = Need(user_id=user_id)
    _fill(db, need, data)
    db.add(need)
    db.commit()
    return need


def update_need(db: Session, user_id: uuid.UUID, need_id: uuid.UUID, data: NeedIn) -> Need:
    need = get_need(db, user_id, need_id)
    _fill(db, need, data)
    db.commit()
    return need


def delete_need(db: Session, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
    db.delete(get_need(db, user_id, need_id))
    db.commit()


def need_topics(need: Need, mechanics: Mechanics) -> list[TopicView]:
    edited = {row.topic_code: row.importance for row in need.edited_importance}
    return _rows(need.specialization, need.stack, edited, mechanics)


def preview_topics(db: Session, data: TopicImportanceIn, mechanics: Mechanics) -> list[TopicView]:
    """Важность тем по стеку до сохранения — форма показывает её, пока работодатель выбирает."""
    specialization = _specialization(db, data.specialization)
    stack = _technologies(db, data.stack)
    _check_topics(specialization, data.topic_importance)
    return _rows(specialization, stack, data.topic_importance, mechanics)


def _fill(db: Session, need: Need, data: NeedIn) -> None:
    specialization = _specialization(db, data.specialization)
    if db.get(Grade, data.grade) is None:
        raise UnknownGrade()
    stack = _technologies(db, data.stack)
    _check_topics(specialization, data.topic_importance)
    _check_salary(data.salary_from, data.salary_to)
    city = data.city or None
    if city is None and data.work_format != WorkFormat.remote:
        raise CityRequired()

    need.title = data.title
    need.team_description = data.team_description
    need.specialization_code = specialization.code
    need.grade_code = data.grade
    need.work_format = data.work_format
    need.city = city
    need.salary_from = data.salary_from
    need.salary_to = data.salary_to
    need.stack = stack
    need.edited_importance = [
        NeedTopicImportance(topic_code=topic, importance=importance)
        for topic, importance in data.topic_importance.items()
    ]


def _specialization(db: Session, code: str) -> Specialization:
    specialization = db.get(Specialization, code)
    if specialization is None:
        raise UnknownSpecialization()
    return specialization


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


def _check_salary(salary_from: int | None, salary_to: int | None) -> None:
    if salary_from is None and salary_to is None:
        return
    if salary_from is None or salary_to is None or not 0 < salary_from <= salary_to:
        raise InvalidSalaryRange()


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
    technologies = {tech.code: tech for tech in stack}
    return [
        TopicView(topic, row.importance, row.edited, [technologies[c] for c in row.technologies])
        for topic, row in zip(specialization.topics, rows, strict=True)
    ]
