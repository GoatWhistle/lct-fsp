"""Справочники из YAML-файла — реализация порта `CatalogSource`.

Здесь только форма файла: лишние и пропущенные поля — ошибка. Согласованность ссылок проверяет
доменный `Catalog`.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.domain.catalog import (
    Catalog,
    FspDiscipline,
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
)


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str


class _Grade(_Entry):
    rank: int


class _Specialization(_Entry):
    topics: list[_Entry]


class _Technology(_Entry):
    topics: list[str]


class _FspDiscipline(_Entry):
    topics: list[str]


class _CatalogFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    grades: list[_Grade]
    industries: list[_Entry]
    specializations: list[_Specialization]
    technologies: list[_Technology]
    fsp_disciplines: list[_FspDiscipline]


def load_catalog(path: Path) -> Catalog:
    with path.open(encoding="utf-8") as f:
        data = _CatalogFile.model_validate(yaml.safe_load(f))
    return Catalog(
        grades=tuple(Grade(g.code, g.name, g.rank) for g in data.grades),
        industries=tuple(Industry(i.code, i.name) for i in data.industries),
        specializations=tuple(
            Specialization(s.code, s.name, tuple(Topic(t.code, t.name, s.code) for t in s.topics))
            for s in data.specializations
        ),
        technologies=tuple(Technology(t.code, t.name, tuple(t.topics)) for t in data.technologies),
        fsp_disciplines=tuple(
            FspDiscipline(d.code, d.name, tuple(d.topics)) for d in data.fsp_disciplines
        ),
    )


class YamlCatalog:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Catalog:
        return load_catalog(self._path)
