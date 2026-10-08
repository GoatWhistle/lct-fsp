"""Справочники в Postgres — реализация порта `CatalogRepository` и перевод записей справочников в
доменные типы `app.domain.catalog`. Изменения не фиксируются — это делает единица работы."""

from collections.abc import Collection
from typing import Protocol

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.domain.catalog import (
    CatalogPart,
    CatalogPlan,
    CatalogRef,
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
)
from app.repository.orm import catalog as orm

CatalogRow = orm.Grade | orm.Industry | orm.Specialization | orm.Topic | orm.Technology

TABLES: dict[CatalogPart, type[CatalogRow]] = {
    CatalogPart.grades: orm.Grade,
    CatalogPart.industries: orm.Industry,
    CatalogPart.specializations: orm.Specialization,
    CatalogPart.topics: orm.Topic,
    CatalogPart.technologies: orm.Technology,
}


class _Named(Protocol):
    code: str
    name: str


def ref_of(row: _Named) -> CatalogRef:
    return CatalogRef(row.code, row.name)


def topic_of(row: orm.Topic) -> Topic:
    return Topic(row.code, row.name, row.specialization_code)


def specialization_of(row: orm.Specialization) -> Specialization:
    return Specialization(row.code, row.name, tuple(topic_of(t) for t in row.topics))


def grade_of(row: orm.Grade) -> Grade:
    return Grade(row.code, row.name, row.rank)


def technology_of(row: orm.Technology) -> Technology:
    return Technology(row.code, row.name, tuple(t.code for t in row.topics))


class SqlCatalog:
    def __init__(self, session: Session) -> None:
        self._session = session

    def grades(self) -> list[Grade]:
        rows = self._session.scalars(select(orm.Grade).order_by(orm.Grade.rank))
        return [grade_of(g) for g in rows]

    def grade(self, code: str) -> Grade | None:
        row = self._session.get(orm.Grade, code)
        return grade_of(row) if row else None

    def industries(self) -> list[Industry]:
        rows = self._session.scalars(select(orm.Industry).order_by(orm.Industry.position))
        return [Industry(i.code, i.name) for i in rows]

    def industry(self, code: str) -> Industry | None:
        row = self._session.get(orm.Industry, code)
        return Industry(row.code, row.name) if row else None

    def specializations(self) -> list[Specialization]:
        rows = self._session.scalars(
            select(orm.Specialization)
            .options(selectinload(orm.Specialization.topics))
            .order_by(orm.Specialization.position)
        )
        return [specialization_of(s) for s in rows]

    def specialization(self, code: str) -> Specialization | None:
        row = self._session.get(orm.Specialization, code)
        return specialization_of(row) if row else None

    def technologies(self, codes: Collection[str] | None = None) -> list[Technology]:
        query = select(orm.Technology).options(selectinload(orm.Technology.topics))
        if codes is not None:
            query = query.where(orm.Technology.code.in_(set(codes)))
        rows = self._session.scalars(query.order_by(orm.Technology.name))
        return [technology_of(t) for t in rows]

    def codes(self) -> dict[CatalogPart, set[str]]:
        return {
            part: set(self._session.scalars(select(table.code))) for part, table in TABLES.items()
        }

    def apply(self, plan: CatalogPlan) -> None:
        catalog = plan.catalog
        rows: dict[CatalogPart, list[dict[str, object]]] = {
            CatalogPart.grades: [
                {"code": g.code, "name": g.name, "rank": g.rank} for g in catalog.grades
            ],
            CatalogPart.industries: [
                {"code": i.code, "name": i.name, "position": n}
                for n, i in enumerate(catalog.industries)
            ],
            CatalogPart.specializations: [
                {"code": s.code, "name": s.name, "position": n}
                for n, s in enumerate(catalog.specializations)
            ],
            CatalogPart.topics: [
                {"code": t.code, "name": t.name, "position": n, "specialization_code": s.code}
                for s in catalog.specializations
                for n, t in enumerate(s.topics)
            ],
            CatalogPart.technologies: [
                {"code": t.code, "name": t.name} for t in catalog.technologies
            ],
        }
        links = [
            {"technology_code": tech.code, "topic_code": topic}
            for tech in catalog.technologies
            for topic in tech.topics
        ]

        # Снимаем от зависимых к главным, вставляем — наоборот.
        db = self._session
        db.execute(delete(orm.technology_topics))
        for part in reversed(CatalogPart):
            if removed := plan.removed.get(part):
                table = TABLES[part]
                db.execute(delete(table).where(table.code.in_(removed)))
        for part in CatalogPart:
            if part_rows := rows[part]:
                table = TABLES[part]
                stmt = pg_insert(table).values(part_rows)
                updated = {col: stmt.excluded[col] for col in part_rows[0] if col != "code"}
                db.execute(stmt.on_conflict_do_update(index_elements=["code"], set_=updated))
        if links:
            db.execute(insert(orm.technology_topics), links)
