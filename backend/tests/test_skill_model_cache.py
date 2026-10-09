"""Модель навыка с кэшем префиксов: оценка продолжается из оценки самого длинного уже
посчитанного префикса наблюдений и совпадает с расчётом с нуля до бита."""

import random
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.adapter import irt
from app.adapter.skill_cache import PrefixCachedSkillModel
from app.domain.skill import Observation, Prior
from app.usecase.interface import SkillModel

TOPICS = ("sql", "api", "algorithms", "testing")
START = datetime(2026, 1, 1, tzinfo=UTC)


def prior(decay: float) -> Prior:
    return Prior.equal_weights(
        TOPICS, theta_sd=1.0, deviation_sd=0.6, sd_inflation=1.3, decay_sd_per_year=decay
    )


def random_items(rng: random.Random, n: int) -> list[Observation]:
    at = START
    items = []
    for _ in range(n):
        at += timedelta(days=rng.uniform(0.0, 200.0))
        items.append(
            Observation(
                topic=rng.choice(TOPICS),
                correct=rng.random() < 0.5,
                discrimination=rng.uniform(0.6, 2.0),
                difficulty=rng.uniform(-1.5, 2.0),
                weight=rng.choice((1.0, 0.5, 2.0)),
                at=at,
            )
        )
    return items


def test_cached_model_is_a_skill_model() -> None:
    model: SkillModel = PrefixCachedSkillModel(irt, max_entries=100)
    assert model.initial(prior(0.0)) == irt.initial(prior(0.0))


@pytest.mark.parametrize("decay", [0.0, 0.4])
@pytest.mark.parametrize("to_mode", [False, True])
def test_estimate_equals_estimate_from_scratch_whatever_was_asked_before(
    decay: float, to_mode: bool
) -> None:
    rng = random.Random(7)
    model = PrefixCachedSkillModel(irt, max_entries=10_000)
    p = prior(decay)
    for _ in range(40):
        items = random_items(rng, rng.randint(0, 25))
        # Как в пути кандидата: растущий префикс, затем оценки без одного ответа.
        for n in range(len(items) + 1):
            assert model.estimate(p, items[:n], to_mode=to_mode) == irt.estimate(
                p, items[:n], to_mode=to_mode
            )
        for i in range(len(items)):
            rest = items[:i] + items[i + 1 :]
            assert model.estimate(p, rest, to_mode=to_mode) == irt.estimate(
                p, rest, to_mode=to_mode
            )


@pytest.mark.parametrize("max_entries", [1, 7, 60])
def test_estimate_stays_exact_when_entries_are_evicted(max_entries: int) -> None:
    rng = random.Random(11)
    model = PrefixCachedSkillModel(irt, max_entries=max_entries)
    p = prior(0.4)
    for _ in range(30):
        items = random_items(rng, rng.randint(0, 20))
        for n in range(len(items) + 1):
            assert model.estimate(p, items[:n]) == irt.estimate(p, items[:n])
        i = rng.randrange(len(items)) if items else 0
        rest = items[:i] + items[i + 1 :]
        assert model.estimate(p, rest, to_mode=True) == irt.estimate(p, rest, to_mode=True)


def test_cache_does_not_grow_past_its_limit_over_many_attempts() -> None:
    rng = random.Random(3)
    model = PrefixCachedSkillModel(irt, max_entries=500)
    sizes = []
    for _ in range(300):
        items = random_items(rng, 20)
        for n in range(len(items) + 1):
            model.estimate(prior(0.0), items[:n])
        sizes.append(len(model))

    assert max(sizes) == 500


def test_longer_prefix_continues_from_the_cached_one() -> None:
    steps = 0

    def step(
        p: Prior, progress: irt.Progress, obs: Observation, *, to_mode: bool = False
    ) -> irt.Progress:
        nonlocal steps
        steps += 1
        return irt.step(p, progress, obs, to_mode=to_mode)

    counting = SimpleNamespace(
        initial=irt.initial, advance=irt.advance, begin=irt.begin, step=step, result=irt.result
    )
    model = PrefixCachedSkillModel(counting, max_entries=1000)
    items = random_items(random.Random(5), 12)

    model.estimate(prior(0.4), items[:10])
    model.estimate(prior(0.4), items)
    model.estimate(prior(0.4), items[:3] + items[4:])

    # 10 с нуля, 2 продолжением, 8 после общего префикса из трёх.
    assert steps == 10 + 2 + 8


def test_estimates_from_many_threads_are_exact() -> None:
    model = PrefixCachedSkillModel(irt, max_entries=300)
    p = prior(0.4)
    attempts = [random_items(random.Random(seed), 15) for seed in range(8)]

    def run(items: list[Observation]) -> bool:
        return all(
            model.estimate(p, items[:n]) == irt.estimate(p, items[:n])
            for _ in range(3)
            for n in range(len(items) + 1)
        )

    with ThreadPoolExecutor(8) as pool:
        assert all(pool.map(run, attempts))
