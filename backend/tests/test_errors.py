"""Доменные ошибки и их HTTP-статусы: статус назначает таблица контроллера."""

from app.controller.errors import STATUS, status_of
from app.domain import errors


def test_every_domain_error_has_its_own_status() -> None:
    declared = {
        v
        for v in vars(errors).values()
        if isinstance(v, type) and issubclass(v, errors.DomainError)
    }
    assert declared - STATUS.keys() == set()


def test_subclass_without_row_inherits_status_of_nearest_ancestor() -> None:
    class Locked(errors.StepUnavailable):
        code = "locked"

    assert status_of(Locked) == STATUS[errors.StepUnavailable]
    assert status_of(errors.DomainError) == 400
