"""Модель принятия (mechanics.md, §13): признаки числами, CatBoost за портом `AcceptanceModel`,
заглушка без файла, монотонность по вилке и загрузке на сетке плана (M7), повторяемость
обучения и правило решения синтетического кандидата."""

import math
import random
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from app.adapter.acceptance import NoAcceptanceModel, acceptance_model
from app.adapter.acceptance_catboost import CatBoostAcceptanceModel, Training, fit
from app.domain.acceptance import COLUMNS, encode
from app.domain.selection import AcceptanceFeatures
from app.domain.work import SalaryRange, WorkFormat
from settings import ACCEPTANCE_MODEL_FILE, Mechanics
from validation.acceptance import (
    GRID_LOADS,
    GRID_RATIOS,
    Offer,
    baselines,
    monotonicity,
    percentiles,
    poisson,
    rows,
)
from validation.metrics import roc_auc
from validation.simulate import Scored
from validation.truth import AcceptanceRule

GRADES = ("intern", "junior", "middle", "senior")
CITIES = ("Москва", "Казань")
INDUSTRIES = ("fintech", "education", "telecom")
TRAINING = Training(iterations=120, depth=4, learning_rate=0.1, random_seed=7, thread_count=2)


def features(**changes: object) -> AcceptanceFeatures:
    base = AcceptanceFeatures(
        salary=SalaryRange(200_000, 300_000),
        expected_salary=200_000,
        market_salary=250_000,
        work_formats=(WorkFormat.office, WorkFormat.hybrid),
        city="Москва",
        relocation=False,
        need_work_format=WorkFormat.hybrid,
        need_city="Москва",
        grade="middle",
        match_score=0.6,
        open_invitations=1,
        industries=frozenset({"fintech"}),
        company_industry="fintech",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def random_features(rng: random.Random) -> AcceptanceFeatures:
    expected = rng.choice((80_000, 150_000, 250_000, 400_000))
    middle = expected * math.exp(rng.gauss(0, 0.3))
    need_format = rng.choice(list(WorkFormat))
    return AcceptanceFeatures(
        salary=SalaryRange(round(0.85 * middle), round(1.15 * middle)),
        expected_salary=expected,
        market_salary=round(expected * math.exp(rng.gauss(0, 0.2))),
        work_formats=tuple(f for f in WorkFormat if rng.random() < 0.6) or (WorkFormat.remote,),
        city=rng.choice(CITIES),
        relocation=rng.random() < 0.2,
        need_work_format=need_format,
        need_city=None if need_format == WorkFormat.remote else rng.choice(CITIES),
        grade=rng.choice(GRADES),
        match_score=rng.random(),
        open_invitations=poisson(1.5, rng),
        industries=frozenset(rng.sample(INDUSTRIES, rng.randint(0, 2))),
        company_industry=rng.choice(INDUSTRIES),
    )


def synthetic_offers(n: int, seed: int) -> list[Offer]:
    """Пары с решениями по правилу синтетического кандидата — без прогона стенда."""
    rng = random.Random(seed)
    rule = AcceptanceRule(acceptance_w_intercept=0.3)
    found = []
    for _ in range(n):
        f = random_features(rng)
        acceptance = 1 / (1 + math.exp(-rng.gauss(0, 1)))
        accepted = int(rng.random() < rule.probability(acceptance, f))
        found.append(Offer(_uuid(rng), _uuid(rng), f, accepted))
    return found


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128))


@pytest.fixture(scope="module")
def trained() -> CatBoostAcceptanceModel:
    offers = synthetic_offers(3000, seed=1)
    return fit(rows(offers), [o.accepted for o in offers], TRAINING)


# --- Признаки числами ---------------------------------------------------------------------------


def test_row_follows_columns() -> None:
    row = encode(features())

    assert row is not None
    assert len(row) == len(COLUMNS)
    values = dict(zip(COLUMNS, row, strict=True))
    assert values["salary_to_expected"] == pytest.approx(math.log(250_000 / 200_000))
    assert values["salary_to_market"] == pytest.approx(0.0)
    assert values["grade"] == "middle"
    assert (values["format_match"], values["city_match"], values["industry_match"]) == (1, 1, 1)
    assert values["open_invitations"] == 1.0


def test_need_without_salary_has_no_row() -> None:
    assert encode(features(salary=None)) is None


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, 1.0),
        ({"city": "Казань"}, 0.0),
        ({"city": "Казань", "relocation": True}, 0.5),
        # Удалённой потребности и потребности без города город не важен.
        ({"city": "Казань", "need_work_format": WorkFormat.remote}, 1.0),
        ({"city": "Казань", "need_city": None}, 1.0),
    ],
)
def test_city_match(changes: dict[str, object], expected: float) -> None:
    row = encode(features(**changes))
    assert row is not None
    assert row[COLUMNS.index("city_match")] == expected


def test_without_profile_expectations_are_missing() -> None:
    row = encode(
        features(
            expected_salary=None,
            work_formats=(),
            city=None,
            relocation=None,
            industries=frozenset(),
        )
    )
    assert row is not None
    values = dict(zip(COLUMNS, row, strict=True))
    for column in ("salary_to_expected", "format_match", "city_match"):
        assert math.isnan(float(values[column]))
    assert values["industry_match"] == 0.0


# --- Заглушка и файл модели ---------------------------------------------------------------------


def test_without_model_file_multiplier_is_one(tmp_path: Path) -> None:
    model = acceptance_model(tmp_path / "missing.cbm")

    assert isinstance(model, NoAcceptanceModel)
    assert model.predict([features()]) == [None]


def test_model_file_round_trip(trained: CatBoostAcceptanceModel, tmp_path: Path) -> None:
    path = tmp_path / "model.cbm"
    trained.save(path)

    loaded = acceptance_model(path)

    assert isinstance(loaded, CatBoostAcceptanceModel)
    probe = [o.features for o in synthetic_offers(20, seed=2)]
    assert loaded.predict(probe) == trained.predict(probe)


def test_need_without_salary_gets_no_probability(trained: CatBoostAcceptanceModel) -> None:
    found = trained.predict([features(), features(salary=None)])

    assert found[0] is not None and 0 <= found[0] <= 1
    assert found[1] is None


# --- Монотонность и качество --------------------------------------------------------------------


def test_monotone_in_salary_and_load_on_plan_grid(trained: CatBoostAcceptanceModel) -> None:
    """Сетка M7: отношение вилки к ожиданию 0,5–2,0 шагом 0,05, загрузка 0–10, 50 строк."""
    found = monotonicity(trained.predict, synthetic_offers(50, seed=3))

    assert found.salary_total == 50 * (len(GRID_RATIOS) - 1)
    assert found.load_total == 50 * (len(GRID_LOADS) - 1)
    assert found.share == 1.0


@pytest.mark.skipif(not ACCEPTANCE_MODEL_FILE.exists(), reason="модель ещё не обучена")
def test_committed_model_is_monotone_on_plan_grid(mechanics: Mechanics) -> None:
    model = CatBoostAcceptanceModel.load(ACCEPTANCE_MODEL_FILE)
    offers = [
        replace(o, features=replace(o.features, market_salary=mechanics.market_salary_median[g]))
        for o in synthetic_offers(50, seed=4)
        for g in [o.features.grade]
    ]

    assert monotonicity(model.predict, offers).share == 1.0


def test_model_beats_salary_only_baseline(trained: CatBoostAcceptanceModel) -> None:
    train = synthetic_offers(3000, seed=1)
    holdout = synthetic_offers(2000, seed=5)
    labels = [o.accepted for o in holdout]
    found = baselines(rows(train), [o.accepted for o in train])

    model_auc = roc_auc(trained.predict_rows(rows(holdout)), labels)
    logistic_auc = roc_auc([found.logistic(r) for r in rows(holdout)], labels)

    assert found.slope > 0
    assert model_auc > logistic_auc > 0.5


def test_same_seed_same_model(tmp_path: Path) -> None:
    offers = synthetic_offers(800, seed=6)
    table, labels = rows(offers), [o.accepted for o in offers]
    probe = rows(synthetic_offers(50, seed=7))

    one, two = fit(table, labels, TRAINING), fit(table, labels, TRAINING)

    assert one.predict_rows(probe) == two.predict_rows(probe)
    one.save(tmp_path / "one.cbm")
    two.save(tmp_path / "two.cbm")
    assert (tmp_path / "one.cbm").read_bytes() == (tmp_path / "two.cbm").read_bytes()


# --- Правило решения и пары стенда --------------------------------------------------------------


def test_decision_rule_terms() -> None:
    """Слагаемые правила — сдвиг логита от нейтральной пары: вилка равна ожиданию, формат, город и
    загрузка не мешают, сферы не отмечены."""
    rule = AcceptanceRule()
    base = features(
        salary=SalaryRange(200_000, 200_000), open_invitations=0, industries=frozenset()
    )
    neutral = rule.logit(0.5, base)

    def shift(**changes: object) -> float:
        return rule.logit(0.5, replace(base, **changes)) - neutral  # type: ignore[arg-type]

    assert neutral == pytest.approx(rule.acceptance_w_intercept)
    assert rule.logit(0.8, base) - neutral == pytest.approx(math.log(4))
    assert shift(salary=SalaryRange(100_000, 100_000)) == pytest.approx(5.0 * math.log(0.5))
    assert shift(salary=SalaryRange(400_000, 400_000)) == pytest.approx(2.0 * math.log(2))
    assert shift(need_work_format=WorkFormat.remote) == pytest.approx(-1.5)
    assert shift(city="Казань") == pytest.approx(-2.0)
    assert shift(city="Казань", relocation=True) == pytest.approx(-0.5)
    assert shift(industries=frozenset({"fintech"})) == pytest.approx(0.5)
    assert shift(open_invitations=3) == pytest.approx(-1.2)


def test_percentiles_of_match_score() -> None:
    ids = [uuid.UUID(int=i) for i in range(4)]
    scored = [Scored(c, "middle", s) for c, s in zip(ids, (0.1, 0.5, 0.5, 0.9), strict=True)]

    found = percentiles(scored)

    assert [found[c] for c in ids] == pytest.approx([0.0, 0.5, 0.5, 1.0])
