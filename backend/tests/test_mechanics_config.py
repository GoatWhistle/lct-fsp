"""Конфиг механик и docs/parameters.md — одни и те же имена и числа.

Таблица в доке — источник чисел механик; меняются они вместе с конфигом в одном PR.
"""

import re

import pytest
import yaml
from pydantic import ValidationError

from app.assessment.catalog import load_catalog
from app.config import BACKEND_DIR, Mechanics, Settings

PARAMETERS_DOC = BACKEND_DIR.parent / "docs" / "parameters.md"
ROW = re.compile(r"^\| `(?P<name>[a-z0-9_]+)` \| `(?P<value>[^`]+)` \|", re.MULTILINE)


def documented_parameters() -> dict[str, object]:
    text = PARAMETERS_DOC.read_text(encoding="utf-8")
    return {row["name"]: yaml.safe_load(row["value"]) for row in ROW.finditer(text)}


def test_config_has_exactly_documented_parameters_and_values() -> None:
    documented = documented_parameters()
    configured = yaml.safe_load(Settings().mechanics_file.read_text(encoding="utf-8"))

    assert documented, "в docs/parameters.md не нашлось ни одного параметра"
    assert sorted(set(configured) - set(documented)) == [], "в конфиге, но не в доке"
    assert sorted(set(documented) - set(configured)) == [], "в доке, но не в конфиге"
    for name, value in documented.items():
        assert configured[name] == value, f"{name}: конфиг {configured[name]!r}, дока {value!r}"


def test_grade_parameters_cover_catalog_grades() -> None:
    mechanics = Mechanics.from_yaml(Settings().mechanics_file)
    grades = {g.code for g in load_catalog().grades}

    assert set(mechanics.grade_thresholds) == grades
    assert set(mechanics.expert_difficulty_by_grade) == grades


@pytest.mark.parametrize(
    "changes",
    [
        {"need_importance_weights": {"key": 3, "important": 2, "nice": 0}},
        {"need_importance_weights": {"key": 3, "important": 2}},
        {"confidence_language_bands": [0.2, 0.5, 0.8, 0.95]},
        {"confidence_language_bands": [0.5, 0.2, 0.8]},
        {"confidence_language_bands": [0.0, 0.5, 1.0]},
    ],
)
def test_matching_parameters_are_validated(changes: dict[str, object]) -> None:
    """Веса важности делят вес темы, границы языка уверенности выбирают одно из четырёх слов:
    ошибка в них ломала бы каждую подборку — бэкенд не стартует с таким конфигом."""
    configured = yaml.safe_load(Settings().mechanics_file.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        Mechanics.model_validate(configured | changes)
