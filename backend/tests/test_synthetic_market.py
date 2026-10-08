"""Синтетический рынок D1/D2 (docs/validation-plan.md, «Данные» и «Эталонная релевантность»):
истина отдельно от наблюдаемого, персонажи и вилки по долям плана, эталон только из истины,
файлы воспроизводятся по seed байт в байт, прежние числа стенда не сдвинулись."""

import dataclasses
import hashlib
import inspect
import json
import random
import re
import statistics
import uuid
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adapter.fsp_registry import FileFspRegistry
from app.domain.catalog import CatalogRef
from app.domain.importance import TopicImportance
from app.domain.selection import NeedRequirement, NeedSnapshot
from app.domain.work import WorkFormat
from settings import BACKEND_DIR, Mechanics, Settings
from validation.main import catalog
from validation.market import SEED, TUNING_SEED, market
from validation.population import (
    D1,
    D2,
    OBSERVED_DIR,
    PAIRS_FILE,
    TRUTH_DIR,
    Dataset,
    Generator,
    GeneratorParams,
    SalaryPosition,
    as_candidate,
    label_files,
    pair_json,
    write,
)
from validation.truth import CandidateTruth, Persona, ResponseModel, relevance

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()


@pytest.fixture(scope="module")
def d1() -> Dataset:
    return Generator(D1, MECHANICS, CATALOG).generate()


def small(params: GeneratorParams = D1, n: int = 12) -> Dataset:
    sized = replace(params, candidates_per_specialization=n)
    return Generator(sized, MECHANICS, CATALOG).generate()


def truth(level: dict[str, float], specialization: str = "qa") -> CandidateTruth:
    return CandidateTruth(
        id=uuid.UUID(int=1),
        specialization=specialization,
        persona=Persona.honest,
        common=0.0,
        level=level,
        grade="middle",
        claimed="middle",
        expected_salary=200_000,
        work_formats=(WorkFormat.remote,),
        city=None,
        relocation=False,
        acceptance=0.5,
        speed=0.0,
    )


def need(weights: dict[str, float], requirement: float = 0.5) -> NeedSnapshot:
    return NeedSnapshot(
        title="QA",
        specialization=CatalogRef("qa", "QA"),
        grade=CatalogRef("middle", "Middle"),
        stack=(),
        work_format=WorkFormat.remote,
        city=None,
        salary=None,
        topics=tuple(
            NeedRequirement(CatalogRef(t, t), TopicImportance.important, False, w, requirement)
            for t, w in weights.items()
        ),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_relevance_is_weighted_share_of_requirements_met_by_truth() -> None:
    weights = {"qa.theory": 0.5, "qa.api": 0.2, "qa.automation": 0.3}
    snap = need(weights)

    assert relevance(truth(dict.fromkeys(weights, 1.0)), snap).grade == 3
    met = relevance(truth({"qa.theory": 0.5, "qa.api": 0.0, "qa.automation": 0.6}), snap)
    assert met.share == pytest.approx(0.8)
    assert met.grade == 2
    assert (
        relevance(truth({"qa.theory": 0.6, "qa.api": 0.9, "qa.automation": 0.0}), snap).grade == 2
    )
    assert (
        relevance(truth({"qa.theory": 0.6, "qa.api": 0.0, "qa.automation": 0.0}), snap).grade == 1
    )
    assert relevance(truth(dict.fromkeys(weights, 0.0)), snap).share == 0.0


def test_other_true_specialization_is_never_relevant() -> None:
    weights = {"qa.theory": 1.0}

    found = relevance(truth(dict.fromkeys(weights, 3.0), specialization="backend"), need(weights))

    assert (found.share, found.grade) == (0.0, 0)


def test_relevance_signature_takes_only_truth_and_employer_input() -> None:
    params = inspect.signature(relevance, eval_str=True).parameters

    assert [p.annotation for p in params.values()] == [CandidateTruth, NeedSnapshot]


def test_d1_has_planned_sizes_and_persona_shares(d1: Dataset) -> None:
    assert len(d1.truths) == 3000
    assert len(d1.employers) == 50
    assert len(d1.needs) == 100
    for code in CATALOG.specializations:
        own = [t for t in d1.truths if t.specialization == code]
        shares = Counter(t.persona for t in own)
        assert len(own) == 600
        for persona, planned in D1.persona_shares:
            assert shares[persona] / len(own) == pytest.approx(planned, abs=0.01)
        own_needs = [n for n in d1.needs if n.form.specialization == code]
        assert len(own_needs) == 20
        assert set(Counter(n.form.grade for n in own_needs).values()) == {5}


def test_employer_salary_positions_follow_plan_shares(d1: Dataset) -> None:
    shares = Counter(e.position for e in d1.employers)

    for position, planned in D1.salary_position_shares:
        assert shares[position] / len(d1.employers) == pytest.approx(planned, abs=0.02)
    factor = dict(D1.salary_position_factor)
    assert (
        factor[SalaryPosition.below] < factor[SalaryPosition.market] < factor[SalaryPosition.above]
    )


def test_every_category_has_candidates_with_and_without_fsp(d1: Dataset) -> None:
    found = {(t.specialization, t.grade, t.fsp_sub is not None) for t in d1.truths}

    for code in CATALOG.specializations:
        for grade in MECHANICS.grade_thresholds:
            assert (code, grade, True) in found
            assert (code, grade, False) in found


def test_registry_is_in_fsp_stub_format(d1: Dataset, tmp_path: Path) -> None:
    write(d1, tmp_path, CATALOG, MECHANICS)
    reader = FileFspRegistry(tmp_path / OBSERVED_DIR / "fsp_registry.json")
    subs = {t.fsp_sub for t in d1.truths if t.fsp_sub}

    assert set(d1.registry) == subs
    found = [a for sub in sorted(subs) for a in reader.achievements(sub)]
    assert {a.discipline for a in found} <= set(CATALOG.fsp_disciplines)
    assert {a.team_role for a in found if a.team_role} <= set(CATALOG.specializations)


def test_personas_leave_their_traces_only_in_observed(d1: Dataset) -> None:
    """Накрутчик пишет больше стека при том же уровне; LLM-помощник отвечает аномально быстро;
    у читера — слитая доля банка."""
    seen = {o.id: o for o in d1.observed}

    def by(persona: Persona, value: object) -> list[float]:
        return [value(t) for t in d1.truths if t.persona == persona]  # type: ignore[operator]

    def stack(t: CandidateTruth) -> float:
        return len(seen[t.id].stack)

    def seconds(t: CandidateTruth) -> float:
        return statistics.median(r.seconds for r in seen[t.id].answers.values())

    assert statistics.fmean(by(Persona.resume_inflator, stack)) > statistics.fmean(
        by(Persona.honest, stack)
    )
    assert statistics.median(by(Persona.llm_helper, seconds)) < 0.5 * statistics.median(
        by(Persona.honest, seconds)
    )
    leaks = [t for t in d1.truths if t.persona == Persona.bank_leak]
    assert all(t.leaked for t in leaks)
    assert not any(t.leaked for t in d1.truths if t.persona != Persona.bank_leak)


def digest(directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def test_same_seed_writes_same_files_byte_for_byte(tmp_path: Path) -> None:
    for name in ("one", "two"):
        write(small(), tmp_path / name, CATALOG, MECHANICS)
    write(small(D2), tmp_path / "shifted", CATALOG, MECHANICS)

    assert digest(tmp_path / "one") == digest(tmp_path / "two")
    assert digest(tmp_path / "one") != digest(tmp_path / "shifted")
    assert {p.split("/")[0] for p in digest(tmp_path / "one")} >= {TRUTH_DIR, OBSERVED_DIR}


def test_labels_do_not_change_when_observed_files_are_spoiled(tmp_path: Path) -> None:
    write(small(), tmp_path, CATALOG, MECHANICS)
    labeled = (tmp_path / PAIRS_FILE).read_text(encoding="utf-8")
    for path in (tmp_path / OBSERVED_DIR).iterdir():
        path.write_text("испорчено\n", encoding="utf-8")
    (tmp_path / "employers.jsonl").write_text("испорчено\n", encoding="utf-8")

    pairs = label_files(tmp_path, CATALOG, MECHANICS)

    assert pairs
    assert [pair_json(p) for p in pairs] == [json.loads(line) for line in labeled.splitlines()]


def test_only_generator_and_labeling_know_where_truth_lives() -> None:
    """Каталог истины называет только генератор: оценка, подбор, прод и засев его не читают."""
    sources = [
        *BACKEND_DIR.joinpath("app").rglob("*.py"),
        *BACKEND_DIR.joinpath("validation").rglob("*.py"),
        BACKEND_DIR / "main.py",
        BACKEND_DIR / "composition.py",
        BACKEND_DIR / "seed_demo.py",
    ]
    mentions = {
        str(p.relative_to(BACKEND_DIR))
        for p in sources
        if "TRUTH_DIR" in p.read_text(encoding="utf-8") or "truth/" in p.read_text(encoding="utf-8")
    }

    assert mentions == {"validation/population.py"}


def test_generator_names_sources_of_salaries_and_stacks() -> None:
    source = BACKEND_DIR.joinpath("validation", "population.py").read_text(encoding="utf-8")

    assert "https://career.habr.com/salaries" in source
    assert "https://survey.stackoverflow.co/2025/technology/" in source


def test_family_truth_is_the_same_as_on_the_stand(d1: Dataset) -> None:
    m = market("qa", MECHANICS, D1.seed)

    assert {code: d1.families[code] for code in m.truth} == m.truth


def test_existing_stand_numbers_do_not_move() -> None:
    """Кандидаты калибровки, D1-команд и D3 — прежние: расширение истины не трогает их поток
    случайности. Отпечаток снят до расширения."""
    expected = {
        SEED: "b1c787ea386fb664705c307d96b51377c2861855908143cb64e5e3d75ec7c581",
        TUNING_SEED: "ef9f67d12486e248339b044ef2bcef47dd6b92211b426c84d9883fbe3e80214a",
    }
    for seed, fingerprint in expected.items():
        m = market("qa", MECHANICS, seed)
        candidates = [m.candidate() for _ in range(5)]
        assert all(c.truth is None for c in candidates)
        runs = [m.attempt(c) for c in candidates[:2]]
        text = repr(
            (
                sorted(m.truth.items()),
                [(c.level, c.claimed) for c in candidates],
                [(r.shown, r.outcome, r.outcome_grade) for r in runs],
            )
        )
        assert hashlib.sha256(text.encode()).hexdigest() == fingerprint


def test_synthetic_candidate_takes_test_on_stand_with_its_response_time() -> None:
    generator = Generator(D1, MECHANICS, CATALOG)
    rng = random.Random(1)
    m = market("qa", MECHANICS)
    times = {}
    for persona in (Persona.honest, Persona.llm_helper):
        t = generator.truth("qa", persona, rng)
        user = m.determine(as_candidate(t)).user
        with m.stand.uow:
            ms = [
                p.response_time_ms
                for a in m.stand.attempts.attempts(user)
                for p in a.presentations
                if p.response_time_ms is not None
            ]
        times[persona] = statistics.median(ms) / 1000

    assert times[Persona.llm_helper] < 0.6 * times[Persona.honest]
    assert times[Persona.llm_helper] == pytest.approx(ResponseModel().llm_median_seconds, rel=0.3)


def test_generator_numbers_are_documented_under_their_names() -> None:
    """Строки раздела генератора в parameters.md называют поля генератора и модели ответа."""
    text = (BACKEND_DIR.parent / "docs" / "parameters.md").read_text(encoding="utf-8")
    section = text.split("## Синтетический рынок стенда валидации")[1].split("\n## ")[0]
    names = set(re.findall(r"^\| `([a-z0-9_]+)` \|", section, re.MULTILINE))
    fields = {f.name for f in dataclasses.fields(GeneratorParams)} | {
        f.name for f in dataclasses.fields(ResponseModel)
    }

    assert names
    assert names <= fields
