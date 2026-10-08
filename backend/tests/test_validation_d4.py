"""D4 и M20 (docs/validation-plan.md): выборка 80 пар по специализациям и квинтилям нашего
скора, файлы оценок двух размечающих, M20 ждёт разметки и считается, как только она лежит."""

import random
import uuid
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from app.domain.skill import Normal
from settings import Mechanics, Settings
from validation import d4
from validation.main import catalog
from validation.population import D1, Generator
from validation.report import WAITING, DatasetRuns, Runs, m20
from validation.simulate import Determined, Outcome, Placed, Scale, SpecRun

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()


def scored(codes: list[str], per: int = 50) -> dict[str, list[tuple[uuid.UUID, uuid.UUID, float]]]:
    rng = random.Random(1)
    return {
        code: [
            (uuid.UUID(int=rng.getrandbits(128)), uuid.UUID(int=rng.getrandbits(128)), rng.random())
            for _ in range(per)
        ]
        for code in codes
    }


def test_sample_is_80_pairs_even_by_specialization_and_quintile() -> None:
    codes = ["backend", "data-ml", "devops", "frontend", "qa"]
    found = d4.draw(scored(codes), seed=7)

    assert len(found) == 80
    assert [it.number for it in found] == list(range(1, 81))
    assert Counter(it.specialization for it in found) == {c: 16 for c in codes}
    for code in codes:
        per_quintile = Counter(it.quintile for it in found if it.specialization == code)
        assert sorted(per_quintile.values()) == [3, 3, 3, 3, 4]
        assert per_quintile[5] == 4
    assert len({(it.need, it.candidate) for it in found}) == 80
    assert d4.draw(scored(codes), seed=7) == found


def test_quintile_follows_our_score() -> None:
    pairs = scored(["qa"], per=100)
    found = d4.draw(pairs, seed=7, size=20)
    score = {(n, c): s for n, c, s in pairs["qa"]}

    top = [score[it.need, it.candidate] for it in found if it.quintile == 5]
    bottom = [score[it.need, it.candidate] for it in found if it.quintile == 1]
    assert min(top) > max(bottom)


def runs_with(items: list[d4.Item], ours: list[float], baseline: list[float]) -> Runs:
    dataset = Generator(replace(D1, candidates_per_specialization=2), MECHANICS, CATALOG).generate()
    outcome = Outcome(Determined("junior", Normal(0, 1)), None, {}, ())
    placed: dict[uuid.UUID, tuple[Placed, ...]] = {}
    for it, s in zip(items, ours, strict=True):
        placed[it.need] = (*placed.get(it.need, ()), Placed(it.candidate, "exact", s))
    run = SpecRun("d1", "qa", 1.0, {it.candidate: outcome for it in items}, placed=placed)
    scores = {
        m: {(it.need, it.candidate): b for it, b in zip(items, baseline, strict=True)}
        for m in ("B1", "B2", "B3")
    }
    data = DatasetRuns(dataset, {"qa": run}, {}, {}, {}, scores=scores)
    return Runs(MECHANICS, CATALOG, Scale(), ("qa",), {"d1": data})


def label(directory: Path, rater: str, values: dict[int, int]) -> None:
    lines = ["item,rel", *(f"{n},{values.get(n, '')}" for n in range(1, 81))]
    (directory / f"labels-{rater}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[d4.Item]:
    monkeypatch.setattr(d4, "D4_DIR", tmp_path)
    items = d4.draw(scored(["qa"], per=200), seed=7)
    d4.write_sample(items, tmp_path)
    return items


def test_m20_waits_for_labels(sample: list[d4.Item], tmp_path: Path) -> None:
    runs = runs_with(sample, [0.5] * 80, [1.0] * 80)
    label(tmp_path, "a", {1: 2})

    found = m20(runs)

    assert found.verdict == WAITING
    assert "A — 1 из 80" in found.body and "B — 0 из 80" in found.body


def test_m20_counts_as_soon_as_labels_are_in_repo(sample: list[d4.Item], tmp_path: Path) -> None:
    """Фиктивная разметка: оценка растёт с нашим скором, у B1 — обратная связь."""
    ours = [(i + 0.5) / 80 for i in range(80)]
    rel = {it.number: min(3, int(s * 4)) for it, s in zip(sample, ours, strict=True)}
    label(tmp_path, "a", rel)
    label(tmp_path, "b", {n: max(0, r - (n % 2)) for n, r in rel.items()})
    runs = runs_with(sample, ours, [-s for s in ours])

    found = m20(runs)

    assert found.verdict.startswith("D1 — выполнен")
    assert "κ_AB" in found.body and "ρ(B1, консенсус)" in found.body
    rho = next(line for line in found.body.splitlines() if line.startswith("| ρ(S"))
    assert "0,9" in rho


def test_written_labels_start_empty(sample: list[d4.Item], tmp_path: Path) -> None:
    assert d4.load_sample(tmp_path) == sample
    assert d4.load_labels(tmp_path, "a") == {}
    assert d4.load_labels(tmp_path, "b") == {}
