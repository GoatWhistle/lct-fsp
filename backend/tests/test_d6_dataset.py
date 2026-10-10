"""Набор D6 (validation/d6.py; формат — validation/data/resume_pdfs.md): целостность, покрытие
плана валидации, приём листа ревью и отложенность набора."""

import csv
import shutil
from datetime import date
from pathlib import Path

import pytest

from settings import Mechanics, Settings
from validation import d6
from validation.resume_parsing import visible_texts

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)

pytestmark = pytest.mark.unit
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    target = tmp_path / "d6"
    shutil.copytree(d6.D6_DIR, target)
    return target


def test_committed_dataset_is_intact() -> None:
    assert d6.check() == []


def test_covers_plan() -> None:
    records = d6.load().records
    clean = [r for r in records if r.injection is None]
    injected = [r for r in records if r.injection is not None]
    assert len({r.layout for r in clean}) >= 5
    assert len(injected) >= 10
    assert set(d6.SPECIALIZATIONS) <= {r.specialization for r in clean}
    assert set(d6.PLAN_TYPES) <= {r.injection.type for r in injected if r.injection}


def test_nothing_is_confirmed_without_a_human() -> None:
    for r in d6.load().records:
        assert r.checked_by == d6.PENDING and r.checked_at is None, r.id


def test_broken_file_is_caught(root: Path) -> None:
    victim = root / d6.load(root).records[0].file
    victim.write_bytes(victim.read_bytes() + b"\n%")
    assert any("хэш" in p for p in d6.check(root))


def test_injection_missing_from_file_is_caught(root: Path) -> None:
    dataset = d6.load(root)
    twin = next(r for r in dataset.records if r.injection)
    clean = next(r for r in dataset.records if r.id == twin.twin_of)
    (root / twin.file).write_bytes((root / clean.file).read_bytes())
    problems = d6.check(root)
    assert any("инъекции нет в файле" in p or "хэш" in p for p in problems)


def test_build_is_reproducible(tmp_path: Path) -> None:
    built = d6.build(tmp_path)
    assert [r.sha256 for r in built.records] == [r.sha256 for r in d6.load().records]


def write_sheet(root: Path, path: Path, reviewer: str, answers: dict[str, str]) -> None:
    with (root / "review" / d6.SHEET).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.update({v: d6.YES for v in d6.VERDICTS})
        row.update(reviewer=reviewer, checked_at="2026-10-09")
    rows[0].update(answers)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, d6.SHEET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_confirm_takes_only_a_filled_human_sheet(root: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "filled.csv"
    write_sheet(root, sheet, "Проверяющий", {"stack_ok": "нет"})
    result = d6.confirm(sheet, root)
    first = d6.load(root).records[0]
    assert first.id in result.refused and first.checked_by == d6.PENDING
    second = d6.load(root).records[1]
    assert second.checked_by == "Проверяющий" and second.checked_at == date(2026, 10, 9)
    assert d6.check(root) == []


def test_confirm_refuses_non_human_reviewer(root: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "filled.csv"
    write_sheet(root, sheet, "model", {})
    assert d6.confirm(sheet, root).accepted == []
    assert all(r.checked_by == d6.PENDING for r in d6.load(root).records)


def test_build_does_not_overwrite_confirmed(root: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "filled.csv"
    write_sheet(root, sheet, "Проверяющий", {})
    d6.confirm(sheet, root)
    with pytest.raises(RuntimeError):
        d6.build(root)


def test_dataset_is_not_used_by_the_product() -> None:
    for folder in ("app", "config"):
        for path in (BACKEND / folder).rglob("*"):
            if path.suffix in {".py", ".yaml"} and path.is_file():
                text = path.read_text(encoding="utf-8")
                assert "data/d6" not in text and "validation.d6" not in text, path


def test_hidden_payload_is_really_hidden() -> None:
    """Скрытая инъекция в файле действительно скрыта: видимый текст, который читает продукт, её
    не содержит. Видимые инструкции — наоборот, на месте."""
    dataset = d6.load()
    texts = visible_texts(dataset, MECHANICS)
    for record in dataset.records:
        if record.injection is None:
            continue
        shown = d6.squeeze(record.injection.text) in d6.squeeze(texts[record.id])
        visible = record.injection.type == "visible_instruction"
        assert shown == visible, record.id
