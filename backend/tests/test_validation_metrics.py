"""Статистики отчёта стенда на известных значениях (docs/validation-plan.md, M1, M2, M4, M11)."""

import math

import pytest

from validation.metrics import (
    ece,
    ndcg_at,
    point_biserial,
    precision_at,
    regression,
    reliability,
)


def test_ndcg_of_ideal_order_is_one() -> None:
    pool = [3, 0, 2, 1, 3, 0]
    ideal = sorted(pool, reverse=True)

    assert ndcg_at(ideal, pool, 10) == pytest.approx(1.0)
    assert ndcg_at(ideal[:3], pool, 3) == pytest.approx(1.0)


def test_ndcg_of_reversed_order_matches_hand_count() -> None:
    pool = [3, 2, 1, 0]
    ranked = sorted(pool)
    dcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ranked))
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(pool))

    assert ndcg_at(ranked, pool, 10) == pytest.approx(dcg / idcg)
    assert ndcg_at(ranked, pool, 10) < 1


def test_ndcg_is_cut_at_k_and_normalized_on_the_whole_pool() -> None:
    """Идеальный порядок — по всему пулу: в топ-2 лучшие пула, а не лучшие выдачи."""
    pool = [3, 3, 0, 0]

    assert ndcg_at([0, 0, 3, 3], pool, 2) == 0.0
    assert ndcg_at([3, 0, 3], pool, 2) == pytest.approx(
        (2**3 - 1) / ((2**3 - 1) + (2**3 - 1) / math.log2(3))
    )


def test_ndcg_without_relevant_in_pool_is_nan() -> None:
    assert math.isnan(ndcg_at([0, 0], [0, 0, 0], 10))


def test_precision_counts_relevant_among_k_places() -> None:
    """Меньше k в выдаче — пустые места нерелевантны: делим на k."""
    assert precision_at([3, 2, 1, 0, 2], 5) == pytest.approx(3 / 5)
    assert precision_at([3, 2], 10) == pytest.approx(2 / 10)
    assert precision_at([3, 3, 3], 2) == 1.0


def test_ece_of_perfectly_calibrated_prediction_is_zero() -> None:
    """В каждой корзине доля событий равна предсказанной вероятности."""
    predicted, observed = [], []
    for p, hits in ((0.05, 1), (0.35, 7), (0.75, 15), (0.95, 19)):
        predicted += [p] * 20
        observed += [1.0] * hits + [0.0] * (20 - hits)

    assert ece(predicted, observed) == pytest.approx(0.0)


def test_ece_weights_bins_by_their_size() -> None:
    predicted = [0.9] * 30 + [0.2] * 10
    observed = [0.6] * 30 + [0.2] * 10

    assert ece(predicted, observed) == pytest.approx(30 / 40 * 0.3)


def test_reliability_bins_are_equal_width_and_keep_one_in_the_last() -> None:
    bins = reliability([0.0, 0.1, 0.55, 1.0, 1.0], [0, 1, 1, 1, 0], bins=10)

    assert [b.count for b in bins] == [1, 1, 0, 0, 0, 1, 0, 0, 0, 2]
    assert bins[9].confidence == 1.0
    assert bins[9].accuracy == 0.5
    assert bins[1].lower == pytest.approx(0.1)
    assert math.isnan(bins[2].confidence)


def test_point_biserial_matches_formula() -> None:
    """r_pb = (M₁ − M₀) / s · √(p q) с s — стандартным отклонением всей выборки."""
    correct = [1, 1, 1, 0, 0, 1, 0, 0]
    level = [2.0, 1.5, 0.5, 0.0, -1.0, 1.0, 0.5, -0.5]
    ones = [x for c, x in zip(correct, level, strict=True) if c]
    zeros = [x for c, x in zip(correct, level, strict=True) if not c]
    mean = sum(level) / len(level)
    s = math.sqrt(sum((x - mean) ** 2 for x in level) / len(level))
    p = len(ones) / len(level)
    expected = (sum(ones) / len(ones) - sum(zeros) / len(zeros)) / s * math.sqrt(p * (1 - p))

    assert point_biserial(correct, level) == pytest.approx(expected)


def test_point_biserial_of_constant_answers_is_nan() -> None:
    assert math.isnan(point_biserial([1, 1, 1], [0.0, 1.0, 2.0]))


def test_regression_splits_error_into_line_and_residual() -> None:
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [1.0, 3.0, 5.0, 7.5]

    fit = regression(xs, ys)

    assert fit.slope == pytest.approx(2.15)
    assert fit.intercept == pytest.approx(0.9)
    explained = [fit.intercept + fit.slope * x for x in xs]
    assert fit.residual_sd == pytest.approx(
        math.sqrt(sum((y - e) ** 2 for y, e in zip(ys, explained, strict=True)) / len(xs))
    )
