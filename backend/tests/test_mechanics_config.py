"""Конфиг механик и docs/parameters.md — одни и те же имена и числа.

Таблица в доке — источник чисел механик; меняются они вместе с конфигом в одном PR.
"""

import re

import yaml

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
