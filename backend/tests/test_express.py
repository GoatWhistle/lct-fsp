"""Экспресс-тест режима жюри (mechanics.md, §18) на сценариях пути: лимит заданий, то же правило
уверенности, погрешность на виду, продолжение полным тестом — на in-memory хранилищах."""

import uuid

import pytest

from app.domain.attempt import AttemptOutcome, PathView, Stage
from app.domain.errors import ExpressNotPaused, ExpressPaused, ExpressUnavailable
from tests.test_protection_scenarios import MECHANICS, Bench, always, never

LIMIT = MECHANICS.express_max_items


def running(view: PathView) -> bool:
    return view.stage == Stage.test and not (view.express and view.express.paused)


def demo_candidate(bench: Bench) -> uuid.UUID:
    user = bench.enrol()
    bench.attempts.mark_demo(user)
    return user


def test_express_is_for_demo_candidates_only() -> None:
    bench = Bench()
    user = bench.enrol()
    with pytest.raises(ExpressUnavailable):
        bench.paths.start_attempt(user, grade="middle", express=True)


def test_express_stays_within_item_limit_and_assigns_by_the_same_rule() -> None:
    """Сильный кандидат: категория присвоена, заданий не больше лимита, итог — экспресс."""
    bench = Bench()
    user = demo_candidate(bench)
    view = bench.paths.start_attempt(user, grade="junior", express=True)
    assert view.progress is not None
    assert view.progress.express and view.progress.max_items == LIMIT
    view = bench.answer(user, always)
    attempt = bench.path_attempt(user)
    assert len(attempt.presentations) <= LIMIT
    assert view.stage == Stage.category
    assert view.express is not None and not view.express.paused
    assert view.result is not None and view.result.overall.theta_sd > 0


def test_express_without_confidence_waits_instead_of_cascading() -> None:
    """Уверенности нет: тест не останавливается каскадом, а ждёт; уровень и погрешность видны,
    задания больше не выдаются."""
    bench = Bench()
    user = demo_candidate(bench)
    bench.paths.start_attempt(user, grade="senior", express=True)
    view = bench.answer(user, never, until=running)
    assert view.stage == Stage.test
    assert view.express is not None and view.express.paused
    assert view.express.answered == LIMIT
    assert view.result is not None and view.result.overall.theta_sd > 0
    assert bench.path_attempt(user).finished_at is None
    with pytest.raises(ExpressPaused):
        bench.paths.current_item(user)


def test_paused_express_continues_as_full_test() -> None:
    bench = Bench()
    user = demo_candidate(bench)
    bench.paths.start_attempt(user, grade="senior", express=True)
    bench.answer(user, never, until=running)
    view = bench.paths.continue_full(user)
    assert view.express is None
    assert view.progress is not None and not view.progress.express
    assert view.progress.max_items == MECHANICS.test_max_items
    final = bench.answer(user, never)
    assert final.stage != Stage.test
    attempt = bench.path_attempt(user)
    assert len(attempt.presentations) > LIMIT
    assert attempt.outcome in (AttemptOutcome.offered, AttemptOutcome.no_category)


def test_continue_needs_a_paused_express() -> None:
    bench = Bench()
    user = demo_candidate(bench)
    with pytest.raises(ExpressNotPaused):
        bench.paths.continue_full(user)
    bench.paths.start_attempt(user, grade="middle", express=True)
    with pytest.raises(ExpressNotPaused):
        bench.paths.continue_full(user)


def test_full_test_keeps_its_limit_and_has_no_express_mark() -> None:
    bench = Bench()
    user = demo_candidate(bench)
    view = bench.paths.start_attempt(user, grade="middle")
    assert view.express is None
    assert view.progress is not None and view.progress.max_items == MECHANICS.test_max_items
