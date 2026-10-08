"""Статус грейда (mechanics.md, §12): из категории по тесту и заявленного грейда."""

from app.domain.candidate import GradeStatusKind, grade_status
from app.domain.catalog import CatalogRef, Grade

JUNIOR = Grade("junior", "Junior", 2)
MIDDLE = Grade("middle", "Middle", 3)


def ref(grade: Grade) -> CatalogRef:
    return CatalogRef(grade.code, grade.name)


def test_category_of_the_claimed_grade_is_confirmed_by_test() -> None:
    status = grade_status(MIDDLE, MIDDLE)

    assert status is not None
    assert status.kind is GradeStatusKind.confirmed
    assert (status.claimed, status.confirmed) == (ref(MIDDLE), ref(MIDDLE))


def test_category_below_the_claim_names_both_grades() -> None:
    status = grade_status(JUNIOR, MIDDLE)

    assert status is not None
    assert status.kind is GradeStatusKind.below_claimed
    assert (status.claimed, status.confirmed) == (ref(MIDDLE), ref(JUNIOR))


def test_claim_without_category_is_unconfirmed() -> None:
    status = grade_status(None, MIDDLE)

    assert status is not None
    assert status.kind is GradeStatusKind.unconfirmed
    assert (status.claimed, status.confirmed) == (ref(MIDDLE), None)


def test_category_without_known_claim_counts_as_claimed() -> None:
    status = grade_status(JUNIOR, None)

    assert status is not None
    assert status.kind is GradeStatusKind.confirmed
    assert status.claimed == ref(JUNIOR)


def test_no_category_and_no_claim_has_no_status() -> None:
    assert grade_status(None, None) is None
