"""Записи справочников из базы — в доменные типы `app.domain.catalog`.

ORM справочников пока живёт в `app.assessment.models`; сюда он переедет вместе с репозиториями.
"""

from typing import Protocol

from app.assessment import models
from app.domain.catalog import CatalogRef, Specialization, Topic


class _Named(Protocol):
    code: str
    name: str


def ref_of(row: _Named) -> CatalogRef:
    return CatalogRef(row.code, row.name)


def topic_of(row: models.Topic) -> Topic:
    return Topic(row.code, row.name, row.specialization_code)


def specialization_of(row: models.Specialization) -> Specialization:
    return Specialization(row.code, row.name, tuple(topic_of(t) for t in row.topics))
