"""Справочники из `catalog.yaml` в базу: `python -m app.assessment.catalog`.

Синхронизация полная: записи из файла вставляются или обновляются, отсутствующие в файле
удаляются. Тема, на которую уже ссылаются данные, не удалится — база откажет, и это
правильно: переименование кода темы требует миграции данных.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import delete, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assessment.models import (
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
    technology_topics,
)
from app.config import Settings
from app.db import create_db_engine

CATALOG_FILE = Path(__file__).with_name("catalog.yaml")

CatalogModel = Grade | Industry | Specialization | Topic | Technology


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str


class GradeEntry(_Entry):
    rank: int


class IndustryEntry(_Entry):
    pass


class TopicEntry(_Entry):
    pass


class SpecializationEntry(_Entry):
    topics: list[TopicEntry]

    @model_validator(mode="after")
    def topic_codes_are_namespaced(self) -> Self:
        for topic in self.topics:
            if not topic.code.startswith(f"{self.code}."):
                raise ValueError(f"код темы {topic.code} должен начинаться с «{self.code}.»")
        return self


class TechnologyEntry(_Entry):
    topics: list[str]


class CatalogData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    grades: list[GradeEntry]
    industries: list[IndustryEntry]
    specializations: list[SpecializationEntry]
    technologies: list[TechnologyEntry]

    @model_validator(mode="after")
    def references_are_consistent(self) -> Self:
        topics = [t.code for s in self.specializations for t in s.topics]
        for kind, codes in [
            ("грейд", [g.code for g in self.grades]),
            ("отрасль", [i.code for i in self.industries]),
            ("специализация", [s.code for s in self.specializations]),
            ("тема", topics),
            ("технология", [t.code for t in self.technologies]),
        ]:
            _require_unique(kind, codes)
        _require_unique("ранг грейда", [str(g.rank) for g in self.grades])
        known = set(topics)
        for tech in self.technologies:
            if unknown := set(tech.topics) - known:
                raise ValueError(f"технология {tech.code} ссылается на неизвестные темы {unknown}")
        return self


def _require_unique(kind: str, codes: Sequence[str]) -> None:
    if dupes := {c for c in codes if codes.count(c) > 1}:
        raise ValueError(f"{kind}: повторяются коды {dupes}")


def load_catalog(path: Path = CATALOG_FILE) -> CatalogData:
    with path.open(encoding="utf-8") as f:
        return CatalogData.model_validate(yaml.safe_load(f))


def sync_catalog(db: Session, data: CatalogData) -> None:
    tables: list[tuple[type[CatalogModel], list[dict[str, object]]]] = [
        (Grade, [g.model_dump() for g in data.grades]),
        (
            Industry,
            [
                {"code": i.code, "name": i.name, "position": n}
                for n, i in enumerate(data.industries)
            ],
        ),
        (
            Specialization,
            [
                {"code": s.code, "name": s.name, "position": i}
                for i, s in enumerate(data.specializations)
            ],
        ),
        (
            Topic,
            [
                {"code": t.code, "name": t.name, "position": i, "specialization_code": s.code}
                for s in data.specializations
                for i, t in enumerate(s.topics)
            ],
        ),
        (Technology, [{"code": t.code, "name": t.name} for t in data.technologies]),
    ]
    links = [
        {"technology_code": tech.code, "topic_code": topic}
        for tech in data.technologies
        for topic in tech.topics
    ]

    # Удаляем от зависимых к главным, вставляем — наоборот.
    db.execute(delete(technology_topics))
    for model, rows in reversed(tables):
        db.execute(delete(model).where(model.code.not_in([row["code"] for row in rows])))
    for model, rows in tables:
        if rows:
            stmt = pg_insert(model).values(rows)
            updated = {col: stmt.excluded[col] for col in rows[0] if col != "code"}
            db.execute(stmt.on_conflict_do_update(index_elements=["code"], set_=updated))
    if links:
        db.execute(insert(technology_topics), links)


def main() -> None:
    engine = create_db_engine(Settings().database_url)
    with Session(engine) as db:
        sync_catalog(db, load_catalog())
        db.commit()
    engine.dispose()
    print("Справочники синхронизированы")


if __name__ == "__main__":
    main()
