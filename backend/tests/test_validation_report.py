"""Отчёт стенда валидации одной командой (docs/validation-plan.md, правила 4, 6, 7): все метрики
плана в отчёте, M9 и M10 первыми, раздел добавляется своей функцией, тот же прогон — тот же файл,
оценка и подбор не читают файлов истины."""

import hashlib
import json
import math
import re
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from app.adapter.text_model import ModelRequest
from settings import Mechanics, Settings
from validation import report
from validation.baselines import LlmRanker, MissingScore, ScoreCache, record
from validation.main import b3_cache_path, baseline_source, catalog
from validation.population import D1, OBSERVED_DIR, TRUTH_DIR, Generator, write
from validation.report import (
    METRICS,
    WAITING,
    DatasetRuns,
    Runs,
    Section,
    baseline_pairs,
    build,
    collect,
    order,
    pending,
    prepared,
    render,
    write_report,
)
from validation.simulate import FamilyFit, ItemFit, Job, Scale, run_spec
from validation.truth import Corruption

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()
TINY = Scale(pairs=3, warm=15, compare=2, candidates=10, fit=3)


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


def test_m21_counts_flags_among_refitted_families_by_answer_kind() -> None:
    """TPR — по испорченным, FPR — по исправным отдельно для выбора и вычисляемого ответа; не
    набравшие ответов на переоценку в доли не входят. Порог TPR не выполнен — M21 не выполнен."""
    families = (
        FamilyFit("qa.a", False, Corruption.key, True, False),
        FamilyFit("qa.b", False, Corruption.flat, True, True),
        FamilyFit("qa.c", True, None, True, False),
        FamilyFit("qa.d", False, None, True, True),
        FamilyFit("qa.e", False, None, True, False),
        FamilyFit("qa.f", False, None, False, True),
    )
    dataset = Generator(replace(D1, candidates_per_specialization=1), MECHANICS, CATALOG).generate()
    data = DatasetRuns(dataset, {}, {}, {}, {}, {"qa": ItemFit(families, 0.5, 0.45, 0.4)})
    runs = Runs(MECHANICS, CATALOG, TINY, ("qa",), {"d1": data})

    section = report.SECTIONS["M21"](runs)

    assert section.sets == {"d1": report.FAILED}
    assert "| TPR | 0,50 (1 из 2) | ≥ 0,80 | нет |" in section.body
    assert "| FPR, выбор из вариантов | 0,00 (0 из 1) | ≤ 0,05 | да |" in section.body
    assert "| FPR, вычисляемый ответ | 0,50 (1 из 2) | ≤ 0,05 | нет |" in section.body
    assert "0,500 / 0,450 / 0,400" in section.body
    assert "ошибка эталона — 0,00 (0 из 1); ответ не зависит от уровня — 1,00 (1 из 1)" in (
        section.body
    )
    assert "разбор потребности — ожидает данных" in section.verdict


def test_m21_waits_for_data_when_a_group_has_no_refitted_family() -> None:
    """Ни одно семейство с выбором из вариантов не набрало ответов на переоценку — FPR по ним не
    измерен, и это не провал порога."""
    families = (
        FamilyFit("qa.a", False, Corruption.key, True, True),
        FamilyFit("qa.c", True, None, False, False),
        FamilyFit("qa.d", False, None, True, False),
    )
    dataset = Generator(replace(D1, candidates_per_specialization=1), MECHANICS, CATALOG).generate()
    data = DatasetRuns(dataset, {}, {}, {}, {}, {"qa": ItemFit(families, 0.5, 0.45, 0.4)})
    runs = Runs(MECHANICS, CATALOG, TINY, ("qa",), {"d1": data})

    assert report.SECTIONS["M21"](runs).sets == {"d1": WAITING}


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
        "validation-report/m3-lift.svg",
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


def fake_encoder(texts: Sequence[str]) -> list[list[float]]:
    """Векторы из хэша текста — вместо e5: тесту нужен порядок, а не смысл."""
    found = []
    for text in texts:
        raw = [b - 128 for b in hashlib.sha256(text.encode()).digest()[:8]]
        norm = sum(x * x for x in raw) ** 0.5
        found.append([x / norm for x in raw])
    return found


class Sonnet:
    model = "claude-sonnet-5-5"

    def __call__(self, request: ModelRequest) -> str:
        return json.dumps({"score": len(request.user) % 11})


@pytest.mark.simulation
def test_report_rebuilds_from_b3_cache_without_model(tmp_path: Path) -> None:
    """Кэш B3 пишется один раз с моделью; отчёт пересобирается из него без модели и сети, а
    пара без ответа в кэше — ошибка, а не тихий пропуск."""
    known = catalog()
    for name in report.SETS:
        dataset, doubles = prepared(name, MECHANICS, TINY, ("qa",), known)
        cache = ScoreCache(b3_cache_path(tmp_path, name), dataset.params.seed)
        pairs = [
            (n, r)
            for rows in baseline_pairs(dataset, doubles, known).values()
            for _, _, n, r in rows
        ]
        record(LlmRanker(cache, Sonnet()), pairs, workers=4)

    runs = collect(
        MECHANICS,
        TINY,
        specializations=["qa"],
        baselines=baseline_source(fake_encoder, b3_dir=tmp_path),
    )
    text, _ = build(runs)

    for data in runs.sets.values():
        assert set(data.scores) == {"B1", "B2", "B3"}
        assert data.b3 is not None and data.b3.model == "claude-sonnet-5-5"
    assert "D1 — claude-sonnet-5-5" in text
    m3 = text.split("## M3.")[1].split("## M4.")[0]
    assert "| B3 |" in m3 and "| B3 | — |" not in m3
    assert "Переходов в точную категорию | 0 | 0 |" in m3

    path = b3_cache_path(tmp_path, "d1")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["answers"].pop(sorted(data["answers"])[0])
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MissingScore):
        collect(
            MECHANICS,
            TINY,
            sets=["d1"],
            specializations=["qa"],
            baselines=baseline_source(fake_encoder, b3_dir=tmp_path),
        )


@pytest.mark.simulation
def test_inflated_twin_gains_at_most_stack_cap_and_never_reaches_exact() -> None:
    runs = collect(
        MECHANICS,
        replace(TINY, candidates=40),
        sets=["d1"],
        specializations=["qa"],
        baselines=baseline_source(fake_encoder, b3_dir=None),
    )
    found = report.lift(runs.sets["d1"])

    assert found.pairs and found.gains
    assert max(found.gains) <= MECHANICS.self_reported_stack_cap + 1e-9
    assert found.promoted == 0
    assert set(found.deltas) == {"ours", "B1", "B2"}
    assert all(len(v) == found.pairs for v in found.deltas.values())
    bias = report.bias(runs.sets["d1"])
    assert bias.identical == 1.0
    assert all(r == 1.0 or math.isnan(r) for r in bias.ratios["ours"].values())
