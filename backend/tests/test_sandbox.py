"""Песочница жюри: набор пар загружается, метрики совпадают с расчётом стенда, изолирована."""

import json
from pathlib import Path

import pytest

from settings import BACKEND_DIR, Mechanics, Settings
from validation import sandbox
from validation.metrics import ndcg_at, precision_at

EXAMPLE = BACKEND_DIR.parent / "docs" / "examples" / "sandbox-set.json"
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)


def test_example_set_loads_and_runs() -> None:
    given = sandbox.load_set(EXAMPLE)
    report = sandbox.run_set(given, MECHANICS)
    assert [r.vacancy for r in report.results] == ["qa-middle", "be-middle"]
    assert all(r.parsed and r.ranked for r in report.results)
    assert report.mean_ndcg is not None


def test_metrics_match_the_validation_stand_functions() -> None:
    report = sandbox.run_set(sandbox.load_set(EXAMPLE), MECHANICS)
    given = sandbox.load_set(EXAMPLE)
    for r in report.results:
        grades = [rel for _, _, rel in r.ranked]
        pool = [p.relevance for p in given.pairs if p.vacancy == r.vacancy]
        assert r.precision == precision_at(grades, sandbox.TOP_K)
        assert r.ndcg == ndcg_at(grades, pool, sandbox.TOP_K)


def test_sandbox_uses_its_own_store_and_leaves_nothing(tmp_path: Path) -> None:
    """Прогон идёт на стенде в памяти: второй прогон даёт те же цифры, а общего состояния нет."""
    one = sandbox.run_set(sandbox.load_set(EXAMPLE), MECHANICS)
    two = sandbox.run_set(sandbox.load_set(EXAMPLE), MECHANICS)
    assert one == two


def test_bad_pair_is_rejected(tmp_path: Path) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["pairs"].append({"vacancy": "qa-middle", "candidate": "нет-такого", "relevance": 2})
    broken = tmp_path / "set.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        sandbox.load_set(broken)
