"""Матрица грейдов — что кандидат грейда делает в теме (mechanics.md, §5).

Ячейка — тема × грейд, описание ячейки — наблюдаемые умения: что человек делает, а не сколько
лет стажа. По матрице проверяется содержательная валидность банка: семейства ячейки должны мерить
её умения, и у каждой описанной ячейки есть семейства. Данные — `config/grade_matrix.yaml`,
документ для жюри `docs/grade-matrix.md` генерируется из них.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from app.domain.catalog import Catalog


class Cell(NamedTuple):
    topic: str
    grade: str


@dataclass(frozen=True)
class GradeMatrix:
    cells: Mapping[Cell, tuple[str, ...]]


def grade_matrix(
    entries: Mapping[str, Mapping[str, Mapping[str, Sequence[str]]]], catalog: Catalog
) -> GradeMatrix:
    """Матрица из записей «специализация → тема → грейд → умения». Специализация, тема и грейд —
    из справочника, тема — своей специализации; у описанной ячейки хотя бы одно умение."""
    topics = {s.code: {t.code for t in s.topics} for s in catalog.specializations}
    grades = {g.code for g in catalog.grades}
    cells: dict[Cell, tuple[str, ...]] = {}
    for specialization, by_topic in entries.items():
        if specialization not in topics:
            raise ValueError(f"матрица грейдов: неизвестная специализация {specialization}")
        for topic, by_grade in by_topic.items():
            if topic not in topics[specialization]:
                raise ValueError(f"матрица грейдов: {topic} — не тема {specialization}")
            for grade, skills in by_grade.items():
                if grade not in grades:
                    raise ValueError(f"матрица грейдов: неизвестный грейд {grade} у {topic}")
                if not skills:
                    raise ValueError(f"матрица грейдов: у {topic} × {grade} нет умений")
                cells[Cell(topic, grade)] = tuple(skills)
    return GradeMatrix(cells)


def render_grade_matrix(matrix: GradeMatrix, catalog: Catalog) -> str:
    """Документ матрицы в markdown: темы и грейды — в порядке справочника, неописанные темы —
    списком в конце специализации."""
    lines = [
        "# Матрица грейдов",
        "",
        "<!-- Сгенерировано из backend/config/grade_matrix.yaml командой",
        "     `cd backend && uv run python -m bank_report matrix`. Руками не править. -->",
        "",
        "Что кандидат грейда делает в теме — наблюдаемые умения, а не стаж. По матрице банк",
        "заданий проверяется на содержательную валидность: семейства ячейки «тема × грейд»",
        "мерят её умения. Как она используется — [mechanics.md](mechanics.md), §5.",
    ]
    for specialization in catalog.specializations:
        lines += ["", f"## {specialization.name}"]
        missing = []
        for topic in specialization.topics:
            described = [g for g in catalog.grades if Cell(topic.code, g.code) in matrix.cells]
            if not described:
                missing.append(topic.name)
                continue
            lines += ["", f"### {topic.name}", "", f"Код темы — `{topic.code}`."]
            for grade in described:
                lines += ["", f"**{grade.name}**", ""]
                lines += [f"- {skill}" for skill in matrix.cells[Cell(topic.code, grade.code)]]
        if missing:
            lines += ["", "Ещё не описаны: " + "; ".join(missing) + "."]
    return "\n".join(lines) + "\n"
