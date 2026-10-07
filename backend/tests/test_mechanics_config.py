"""Конфиг механик и docs/parameters.md — одни и те же имена и числа.

Таблица в доке — источник чисел механик; меняются они вместе с конфигом в одном PR.
"""

import re

import pytest
import yaml
from pydantic import ValidationError

from app.assessment.catalog import load_catalog
from app.config import BACKEND_DIR, Mechanics, Settings
from main import create_app

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


CALIBRATION_PARAMETERS = (
    "expert_discrimination",
    "expert_difficulty_by_grade",
    "elo_k_initial",
    "elo_k_half_responses",
    "elo_k_min",
    "calibration_refit_min_responses",
    "calibration_expert_gap_review",
    "calibration_refit_difficulty_prior_sd",
    "calibration_refit_log_discrimination_prior_sd",
    "calibration_link_window_attempts",
)


def test_port_implementations_receive_mechanics_parameters() -> None:
    """Реализации алгоритмов получают числа механик через конструктор при сборке: выбор
    задания — пул и потолок показов, калибровка — параметры Эло, переоценки и связки шкалы."""
    mechanics = Mechanics.from_yaml(Settings().mechanics_file)
    app = create_app(Settings(_env_file=None), mechanics)
    try:
        selector = app.state.item_selector
        assert selector.top_k == mechanics.exposure_top_k
        assert selector.max_rate == mechanics.exposure_max_rate
        calibration = app.state.calibration(app.state.unit_of_work())
        for name in CALIBRATION_PARAMETERS:
            assert getattr(calibration, name) == getattr(mechanics, name), name
    finally:
        app.state.engine.dispose()


@pytest.mark.parametrize(
    "changes",
    [
        {"need_importance_weights": {"key": 3, "important": 2, "nice": 0}},
        {"need_importance_weights": {"key": 3, "important": 2}},
        {"confidence_language_bands": [0.2, 0.5, 0.8, 0.95]},
        {"confidence_language_bands": [0.5, 0.2, 0.8]},
        {"confidence_language_bands": [0.0, 0.5, 1.0]},
        {"fsp_result_difficulty": {"winner": 1.0, "prize": 0.5, "national_finalist": 0.0}},
        {"fsp_result_difficulty": {"winner": 1.0, "prize": 0.5, "finalist": 0.0, "regional": 0}},
        {"fsp_result_difficulty": {"winner": 0.5, "prize": 1.0, "finalist": 0.0}},
        {"grade_retry_interval_days": 0},
        {"level_sd_inflation": 0},
        {"grade_retry_interval_days": 120, "grade_change_interval_days": 90},
    ],
)
def test_mechanics_parameters_are_validated(changes: dict[str, object]) -> None:
    """Веса важности делят вес темы, границы языка уверенности выбирают одно из четырёх слов:
    ошибка в них ломала бы каждую подборку. Сложность ФСП — только по типу результата, без
    уровня мероприятия; повтор после провала ждёт не дольше смены грейда. С таким конфигом
    бэкенд не стартует."""
    configured = yaml.safe_load(Settings().mechanics_file.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        Mechanics.model_validate(configured | changes)
