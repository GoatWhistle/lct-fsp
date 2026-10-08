"""Правила справочника без базы: согласованность ссылок и синхронизация по кодам."""

from dataclasses import replace

import pytest

from app.adapter.catalog_file import load_catalog
from app.domain.catalog import (
    Catalog,
    CatalogPart,
    Grade,
    Specialization,
    Technology,
    Topic,
    catalog_codes,
    catalog_plan,
)
from settings import CATALOG_FILE

QA = Specialization("qa", "QA", (Topic("qa.theory", "Теория", "qa"),))
SMALL = Catalog(
    grades=(Grade("junior", "Junior", 1),),
    industries=(),
    specializations=(QA,),
    technologies=(Technology("pytest", "pytest", ("qa.theory",)),),
)


def test_sync_keeps_every_code_of_the_same_catalog() -> None:
    catalog = load_catalog(CATALOG_FILE)

    plan = catalog_plan(catalog_codes(catalog), catalog)

    assert plan.catalog == catalog
    assert all(not codes for codes in plan.removed.values())


def test_sync_removes_only_codes_missing_from_catalog() -> None:
    stored = catalog_codes(SMALL) | {
        CatalogPart.technologies: {"pytest", "selenium"},
        CatalogPart.grades: {"junior", "senior"},
    }

    plan = catalog_plan(stored, SMALL)

    assert plan.removed[CatalogPart.technologies] == {"selenium"}
    assert plan.removed[CatalogPart.grades] == {"senior"}
    assert plan.removed[CatalogPart.topics] == frozenset()


def test_sync_into_empty_storage_removes_nothing() -> None:
    plan = catalog_plan({}, SMALL)

    assert set(plan.removed) == set(CatalogPart)
    assert all(not codes for codes in plan.removed.values())


def test_duplicate_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="грейд"):
        replace(SMALL, grades=(Grade("junior", "J", 1), Grade("junior", "J2", 2)))


def test_duplicate_grade_rank_is_rejected() -> None:
    with pytest.raises(ValueError, match="ранг грейда"):
        replace(SMALL, grades=(Grade("junior", "J", 1), Grade("middle", "M", 1)))


def test_topic_code_starts_with_specialization_code() -> None:
    with pytest.raises(ValueError, match=r"dev\.api"):
        replace(SMALL, specializations=(replace(QA, topics=(Topic("dev.api", "API", "qa"),)),))


def test_technology_points_only_to_known_topics() -> None:
    with pytest.raises(ValueError, match="react"):
        replace(SMALL, technologies=(Technology("react", "React", ("frontend.frameworks",)),))
