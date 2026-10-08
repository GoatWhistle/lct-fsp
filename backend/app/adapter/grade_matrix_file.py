"""Матрица грейдов из YAML-файла: «специализация → тема → грейд → умения».

Здесь только форма файла; ссылки на справочник проверяет доменная `grade_matrix`.
"""

from pathlib import Path

import yaml
from pydantic import RootModel

from app.domain.catalog import Catalog
from app.domain.grade_matrix import GradeMatrix, grade_matrix


class _MatrixFile(RootModel[dict[str, dict[str, dict[str, list[str]]]]]):
    pass


def load_grade_matrix(path: Path, catalog: Catalog) -> GradeMatrix:
    with path.open(encoding="utf-8") as f:
        data = _MatrixFile.model_validate(yaml.safe_load(f) or {})
    return grade_matrix(data.root, catalog)
