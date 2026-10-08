"""Матрица грейдов — данные «тема × грейд → наблюдаемые умения» (mechanics.md, §5): ссылки на
справочник проверяются при загрузке, документ для жюри генерируется из данных."""

from pathlib import Path

import pytest
import yaml

from app.adapter.catalog_file import load_catalog
from app.adapter.grade_matrix_file import load_grade_matrix
from app.domain.grade_matrix import Cell, render_grade_matrix
from settings import CATALOG_FILE, GRADE_MATRIX_DOC, GRADE_MATRIX_FILE

CATALOG = load_catalog(CATALOG_FILE)


def test_committed_document_matches_generated_from_data() -> None:
    """Документ правится только командой `uv run python -m bank_report matrix`."""
    matrix = load_grade_matrix(GRADE_MATRIX_FILE, CATALOG)

    assert GRADE_MATRIX_DOC.read_text(encoding="utf-8") == render_grade_matrix(matrix, CATALOG)


def test_sample_topic_is_described_for_every_grade() -> None:
    matrix = load_grade_matrix(GRADE_MATRIX_FILE, CATALOG)
    topics = {cell.topic for cell in matrix.cells}

    assert topics
    for topic in topics:
        for grade in CATALOG.grades:
            assert matrix.cells.get(Cell(topic, grade.code)), (topic, grade.code)


def write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "grade_matrix.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_valid_matrix_loads(tmp_path: Path) -> None:
    path = write(tmp_path, {"backend": {"backend.databases": {"middle": ["пишет индекс"]}}})

    matrix = load_grade_matrix(path, CATALOG)

    assert matrix.cells == {Cell("backend.databases", "middle"): ("пишет индекс",)}


@pytest.mark.parametrize(
    "data",
    [
        {"backend": {"backend.unknown": {"middle": ["что-то"]}}},
        {"backend": {"backend.databases": {"lead": ["что-то"]}}},
        {"unknown": {"backend.databases": {"middle": ["что-то"]}}},
        # Тема чужой специализации.
        {"qa": {"backend.databases": {"middle": ["что-то"]}}},
        {"backend": {"backend.databases": {"middle": []}}},
        {"backend": {"backend.databases": {"middle": "строка вместо списка"}}},
    ],
)
def test_matrix_with_unknown_reference_or_wrong_shape_is_rejected(
    tmp_path: Path, data: object
) -> None:
    with pytest.raises(ValueError):
        load_grade_matrix(write(tmp_path, data), CATALOG)
