"""Отчёт покрытия банка и документ матрицы грейдов (mechanics.md, §5).

    uv run python -m bank_report                # отчёт покрытия в stdout, markdown
    uv run python -m bank_report --calibration  # и сверка сложности по калибровке из базы
    uv run python -m bank_report matrix         # пересобрать docs/grade-matrix.md

Отчёт показывает нарушения, но ничего не роняет: проверки — те же чистые функции
`app.domain.bank.coverage`, что зовут тесты банка.
"""

import argparse
from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.adapter.catalog_file import load_catalog
from app.adapter.grade_matrix_file import load_grade_matrix
from app.domain.bank import BANK, Family
from app.domain.bank.coverage import (
    SCENARIO_GRADES,
    Bounds,
    Violation,
    cells_without_description,
    cells_without_families,
    scenario_counts,
    scenario_shortage,
    topic_counts,
    trace_overflow,
)
from app.domain.calibration import ExpertGap
from app.domain.grade_matrix import Cell, GradeMatrix, render_grade_matrix
from app.repository.calibration import SqlCalibrationRepository
from app.repository.database import create_db_engine
from composition import elo_calibration
from settings import GRADE_MATRIX_DOC, GRADE_MATRIX_FILE, Mechanics, Settings

GAP_WORDS = {
    ExpertGap.EASIER: "легче экспертной — на ручную проверку",
    ExpertGap.HARDER: "тяжелее экспертной — в выдаче, помечено",
}


def coverage_report(
    families: Sequence[Family],
    matrix: GradeMatrix,
    bounds: Bounds,
    gaps: Mapping[str, ExpertGap] | None,
) -> str:
    """Отчёт покрытия в markdown; `gaps` — None, когда данных калибровки нет."""
    lines = [
        "# Покрытие банка заданий",
        "",
        f"Семейств в выдаче — {len(families)}. Потолок трассировки в теме — "
        f"{bounds.max_trace_share_per_topic}, минимум сценарных семейств в ячейках "
        f"{' и '.join(SCENARIO_GRADES)} — {bounds.min_scenario_families_per_grade}.",
        "",
        "## Виды заданий по темам",
        "",
        "| Тема | Семейств | Трассировка | Доля | "
        + " | ".join(f"Сценарных {g}" for g in SCENARIO_GRADES)
        + " |",
        "|---|---|---|---|" + "---|" * len(SCENARIO_GRADES),
    ]
    scenarios = scenario_counts(families)
    for topic, (n, traces) in topic_counts(families).items():
        cells = " | ".join(str(scenarios[Cell(topic, g)]) for g in SCENARIO_GRADES)
        lines.append(f"| `{topic}` | {n} | {traces} | {traces / n:.2f} | {cells} |")
    sections = [
        ("Доля трассировки выше потолка", trace_overflow(families, bounds)),
        ("Сценарных семейств меньше минимума", scenario_shortage(families, bounds)),
        ("Ячейки матрицы без семейств", cells_without_families(families, matrix)),
        ("Семейства в ячейках без описания в матрице", cells_without_description(families, matrix)),
    ]
    lines += ["", "## Нарушения"]
    for title, violations in sections:
        lines += ["", f"### {title} — {len(violations)}", ""]
        lines += [_violation(v) for v in violations] or ["Нет."]
    lines += ["", "## Сверка сложности с экспертной", ""]
    if gaps is None:
        lines.append("Данных калибровки нет — запустите с `--calibration`.")
    else:
        lines += [f"- `{code}` — {GAP_WORDS[gap]}" for code, gap in sorted(gaps.items())] or [
            "Расхождений нет."
        ]
    return "\n".join(lines) + "\n"


def _violation(v: Violation) -> str:
    where = f"`{v.topic}` × {v.grade}" if v.grade else f"`{v.topic}`"
    return f"- {where}: {v.message}"


def _calibration_gaps(mechanics: Mechanics) -> dict[str, ExpertGap]:
    """Пометки сверки по калибровке из базы `Settings().database_url`."""
    engine = create_db_engine(Settings().database_url)
    try:
        with Session(engine) as session:
            calibration = elo_calibration(SqlCalibrationRepository(session), mechanics)
            return calibration.expert_gaps(BANK)
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m bank_report", description=__doc__)
    parser.add_argument("command", nargs="?", choices=["coverage", "matrix"], default="coverage")
    parser.add_argument(
        "--calibration", action="store_true", help="сверка сложности по калибровке из базы"
    )
    args = parser.parse_args(argv)
    settings = Settings()
    catalog = load_catalog(settings.catalog_file)
    matrix = load_grade_matrix(GRADE_MATRIX_FILE, catalog)
    if args.command == "matrix":
        GRADE_MATRIX_DOC.write_text(render_grade_matrix(matrix, catalog), encoding="utf-8")
        print(f"записан {GRADE_MATRIX_DOC}")
        return
    mechanics = Mechanics.from_yaml(settings.mechanics_file)
    bounds = Bounds(
        mechanics.bank_max_trace_share_per_topic, mechanics.bank_min_scenario_families_per_grade
    )
    gaps = _calibration_gaps(mechanics) if args.calibration else None
    print(coverage_report(BANK, matrix, bounds, gaps), end="")


if __name__ == "__main__":
    main()
