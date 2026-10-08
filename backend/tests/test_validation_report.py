"""Отчёт стенда валидации одной командой (docs/validation-plan.md, правила 4, 6, 7): все метрики
плана в отчёте, M9 и M10 первыми, раздел добавляется своей функцией, тот же прогон — тот же файл,
оценка и подбор не читают файлов истины."""

import hashlib
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from settings import Mechanics, Settings
from validation import report
from validation.main import catalog
from validation.population import D1, OBSERVED_DIR, TRUTH_DIR, Generator, write
from validation.report import (
    METRICS,
    WAITING,
    Runs,
    Section,
    build,
    collect,
    order,
    pending,
    render,
    write_report,
)
from validation.simulate import Job, Scale, run_spec

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()
TINY = Scale(pairs=3, warm=15, compare=2, candidates=10)


def empty_runs() -> Runs:
    return Runs(MECHANICS, CATALOG, TINY, ("qa",), {})


def headings(text: str) -> list[str]:
    return re.findall(r"^## (M\d+)\.", text, flags=re.MULTILINE)


def test_m9_and_m10_go_first_then_plan_numbers() -> None:
    assert order(["M2", "M10", "M1", "M23", "M9", "M11"]) == ["M9", "M10", "M1", "M2", "M11", "M23"]


def test_every_plan_metric_is_in_report_and_unmeasured_wait_for_data() -> None:
    text = render(empty_runs(), {m: pending(m) for m in METRICS})

    assert headings(text) == order(METRICS)
    assert len(headings(text)) == 23
    assert text.count(f"Вердикт: {WAITING}.") == 23
    assert "validation-plan.md#" in text


def test_section_is_added_by_its_own_function(monkeypatch: pytest.MonkeyPatch) -> None:
    """Новый раздел — функция под декоратором: остальные разделы не правятся, метрика без раздела
    остаётся «ожидает данных»."""
    monkeypatch.setattr(report, "SECTIONS", {})

    @report.section("M23")
    def speed(runs: Runs) -> Section:
        return Section("M23", "p95 — 0,2 с.", "D1 — выполнен")

    text, _ = build(empty_runs())

    m23 = text.split("## M23.")[1]
    assert "p95 — 0,2 с." in m23
    assert "Вердикт: D1 — выполнен." in m23
    assert "Вердикт: ожидает данных." in text.split("## M22.")[1]


@pytest.mark.simulation
def test_same_run_writes_same_report_byte_for_byte(tmp_path: Path) -> None:
    """Задачи идут в пуле процессов; тот же прогон с другим числом процессов — тот же файл."""
    for name, workers in (("one", 2), ("two", 3)):
        (tmp_path / name).mkdir()
        runs = collect(MECHANICS, TINY, specializations=["qa"], workers=workers)
        write_report(runs, tmp_path / name / "validation-report.md")

    def digest(directory: Path) -> dict[str, str]:
        return {
            str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        }

    one = digest(tmp_path / "one")
    assert one == digest(tmp_path / "two")
    assert set(one) == {
        "validation-report.md",
        "validation-report/m4-reliability-d1.svg",
        "validation-report/m4-reliability-d2.svg",
    }
    text = (tmp_path / "one" / "validation-report.md").read_text(encoding="utf-8")
    assert headings(text)[:3] == ["M9", "M10", "M1"]
    assert "](validation-report/m4-reliability-d1.svg)" in text
    for metric in ("M1", "M2", "M4", "M9", "M10", "M11", "M12", "M13"):
        verdict = re.search(rf"## {metric}\..*?Вердикт: (.*?)\.\n", text, flags=re.DOTALL)
        assert verdict is not None
        assert "D1 —" in verdict.group(1) and "D2 —" in verdict.group(1)


@pytest.mark.simulation
def test_evaluation_and_selection_never_open_truth_files(tmp_path: Path) -> None:
    """Набор лежит файлами рядом; прогон специализации — тест, повтор, B0, пул и подборки — не
    открывает ни одного файла из `truth/`, а `observed/` тоже не нужен: ответы порождает
    симулятор, платформа видит только их."""
    params = replace(D1, candidates_per_specialization=TINY.candidates or 10)
    dataset = Generator(params, MECHANICS, CATALOG).generate()
    write(dataset, tmp_path, CATALOG, MECHANICS)
    opened: list[str] = []
    watching = True

    def hook(event: str, args: tuple[object, ...]) -> None:
        if watching and event == "open" and isinstance(args[0], str | Path):
            opened.append(str(args[0]))

    sys.addaudithook(hook)
    try:
        run = run_spec(
            Job(
                D1,
                "qa",
                MECHANICS,
                TINY,
                tuple(t for t in dataset.truths if t.specialization == "qa"),
                tuple(n for n in dataset.needs if n.form.specialization == "qa"),
                {o.id: frozenset(o.stack) for o in dataset.observed},
            )
        )
    finally:
        watching = False

    assert run.rankings
    assert opened
    assert not [p for p in opened if str(tmp_path / TRUTH_DIR) in p]
    assert not [p for p in opened if str(tmp_path / OBSERVED_DIR) in p]
