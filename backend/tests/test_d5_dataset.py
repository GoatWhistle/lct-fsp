"""Набор D5 для M21: читается загрузчиком команды `parsing`, значения разметки — коды справочника
и канонические города словаря синонимов, покрытие — как в плане валидации
(docs/validation-plan.md, D5; формат — validation/data/need_texts.md)."""

from collections import Counter
from urllib.parse import urlparse

import pytest
import yaml

from settings import CATALOG_FILE, SYNONYMS_FILE
from validation.commands import D5_FILE
from validation.parsing import LabeledText, load_labeled

CATALOG = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
SPECIALIZATIONS = {s["code"] for s in CATALOG["specializations"]}
GRADES = {g["code"] for g in CATALOG["grades"]}
TECHNOLOGIES = {t["code"] for t in CATALOG["technologies"]}
CITIES = set(yaml.safe_load(SYNONYMS_FILE.read_text(encoding="utf-8"))["cities"])
# Разметка модели без проверки человеком — значение из формата набора.
MODEL_LABEL = "model"


@pytest.fixture(scope="module")
def d5() -> list[LabeledText]:
    return load_labeled(D5_FILE)


def test_d5_size_and_sources(d5: list[LabeledText]) -> None:
    assert len(d5) >= 100
    assert len({t.id for t in d5}) == len(d5)
    for t in d5:
        url = urlparse(t.source)
        assert url.scheme == "https" and url.netloc, t.id
        assert t.text.strip(), t.id
        assert t.checked_by == MODEL_LABEL, t.id


def test_d5_codes_are_from_catalog(d5: list[LabeledText]) -> None:
    for t in d5:
        assert t.specialization is None or t.specialization in SPECIALIZATIONS, t.id
        assert t.grade is None or t.grade in GRADES, t.id
        assert set(t.stack) <= TECHNOLOGIES, (t.id, set(t.stack) - TECHNOLOGIES)
        assert t.city is None or t.city in CITIES, t.id
        if t.salary_from is not None and t.salary_to is not None:
            assert t.salary_from <= t.salary_to, t.id


def test_d5_out_of_catalog_has_no_fields(d5: list[LabeledText]) -> None:
    outside = [t for t in d5 if t.out_of_catalog]
    assert len(outside) >= 10
    for t in outside:
        fields = (t.specialization, t.grade, t.work_format, t.city, t.salary_from, t.salary_to)
        assert fields == (None,) * 6 and t.stack == [], t.id


def test_d5_covers_every_specialization_and_grade(d5: list[LabeledText]) -> None:
    specs = Counter(t.specialization for t in d5 if not t.out_of_catalog)
    grades = Counter(t.grade for t in d5 if not t.out_of_catalog)
    assert all(specs[s] >= 15 for s in SPECIALIZATIONS), specs
    assert all(grades[g] >= 10 for g in GRADES), grades
