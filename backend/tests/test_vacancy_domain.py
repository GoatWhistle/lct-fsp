"""Вакансия и отклик в домене (mechanics.md, §14): форма вакансии, статусы отклика — те же, что у
приглашения, но ход у работодателя, — срок ответа, отзыв доступа и правила отклика."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.application import (
    Application,
    answered,
    check_can_apply,
    revoked,
    viewed,
)
from app.domain.catalog import CatalogRef, Grade, Specialization
from app.domain.errors import (
    AlreadyApplied,
    ApplicationTransitionNotAllowed,
    InvalidSalaryRange,
    UnknownGrade,
    UnknownSpecialization,
    VacancyArchived,
)
from app.domain.invitation import InvitationStatus
from app.domain.vacancy import Vacancy, VacancyForm, VacancyTerms, archived, vacancy_terms
from app.domain.work import SalaryRange, WorkFormat

S = InvitationStatus
T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TTL = timedelta(days=7)
QA = Specialization("qa", "Тестирование")
MIDDLE = Grade("middle", "Middle", 2)


def form(**changes: object) -> VacancyForm:
    base = VacancyForm(
        title="QA-инженер в платёжный шлюз",
        description="Автотесты на pytest, нагрузка, CI",
        specialization="qa",
        grade="middle",
        work_formats=(WorkFormat.remote, WorkFormat.hybrid),
        salary_from=200_000,
        salary_to=260_000,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def vacancy(archived_at: datetime | None = None) -> Vacancy:
    return Vacancy(
        id=uuid.uuid4(),
        employer_id=uuid.uuid4(),
        company_name="Платёжные решения",
        terms=VacancyTerms(
            title="QA",
            description="",
            specialization=CatalogRef("qa", "Тестирование"),
            grade=CatalogRef("middle", "Middle"),
            work_formats=(WorkFormat.remote,),
            salary=SalaryRange(200_000, 260_000),
        ),
        published_at=T0,
        updated_at=T0,
        archived_at=archived_at,
    )


def application(status: InvitationStatus = S.sent, applied_at: datetime = T0) -> Application:
    v = vacancy()
    return Application(
        id=uuid.uuid4(),
        vacancy_id=v.id,
        employer_id=v.employer_id,
        candidate_id=uuid.uuid4(),
        vacancy_title=v.terms.title,
        company_name=v.company_name,
        salary=v.terms.salary,
        status=status,
        applied_at=applied_at,
        viewed_at=None,
        answered_at=None,
    )


# Вакансия.


def test_vacancy_terms_take_catalog_names() -> None:
    terms = vacancy_terms(form(), QA, MIDDLE)

    assert terms.specialization == CatalogRef("qa", "Тестирование")
    assert terms.grade == CatalogRef("middle", "Middle")
    assert terms.salary == SalaryRange(200_000, 260_000)
    assert terms.work_formats == (WorkFormat.remote, WorkFormat.hybrid)


def test_vacancy_work_formats_lose_repeats_and_keep_order() -> None:
    terms = vacancy_terms(
        form(work_formats=(WorkFormat.office, WorkFormat.remote, WorkFormat.office)), QA, MIDDLE
    )

    assert terms.work_formats == (WorkFormat.office, WorkFormat.remote)


@pytest.mark.parametrize(
    ("salary_from", "salary_to"), [(0, 100_000), (-1, 100_000), (300_000, 200_000)]
)
def test_vacancy_needs_salary_range(salary_from: int, salary_to: int) -> None:
    with pytest.raises(InvalidSalaryRange):
        vacancy_terms(form(salary_from=salary_from, salary_to=salary_to), QA, MIDDLE)


def test_vacancy_needs_known_specialization_and_grade() -> None:
    with pytest.raises(UnknownSpecialization):
        vacancy_terms(form(), None, MIDDLE)
    with pytest.raises(UnknownGrade):
        vacancy_terms(form(), QA, None)


def test_archived_vacancy_keeps_first_archive_time() -> None:
    once = archived(vacancy(), T0)

    assert once.archived_at == T0
    assert archived(once, T0 + TTL) == once


# Отклик: кто и когда может откликнуться.


def test_candidate_applies_to_published_vacancy_once() -> None:
    check_can_apply(vacancy(), None)

    with pytest.raises(AlreadyApplied):
        check_can_apply(vacancy(), application())


def test_archived_vacancy_takes_no_applications() -> None:
    with pytest.raises(VacancyArchived):
        check_can_apply(vacancy(archived_at=T0), None)


# Статусы отклика: машина приглашения, ход у работодателя.


def test_employer_opening_application_marks_it_viewed() -> None:
    result = viewed(application(), T0 + timedelta(hours=1))

    assert result.status is S.viewed
    assert result.viewed_at == T0 + timedelta(hours=1)
    assert viewed(result, T0 + TTL / 2) == result


@pytest.mark.parametrize("start", [S.sent, S.viewed])
@pytest.mark.parametrize(("accept", "target"), [(True, S.accepted), (False, S.declined)])
def test_employer_answers_open_application(
    start: InvitationStatus, accept: bool, target: InvitationStatus
) -> None:
    result = answered(application(start), accept=accept, now=T0 + timedelta(days=1))

    assert result.status is target
    assert result.answered_at == T0 + timedelta(days=1)


@pytest.mark.parametrize("closed", [S.accepted, S.declined])
def test_answered_application_cannot_be_answered_again(closed: InvitationStatus) -> None:
    with pytest.raises(ApplicationTransitionNotAllowed):
        answered(application(closed), accept=True, now=T0)


def test_application_without_answer_expires_after_ttl() -> None:
    a = application()

    assert a.at(T0 + TTL - timedelta(seconds=1), TTL).status is S.sent
    expired = a.at(T0 + TTL, TTL)
    assert expired.status is S.expired
    assert a.expires_at(TTL) == T0 + TTL
    assert viewed(expired, T0 + TTL) == expired
    with pytest.raises(ApplicationTransitionNotAllowed):
        answered(expired, accept=True, now=T0 + TTL)


@pytest.mark.parametrize("status", list(S))
def test_application_can_be_revoked_in_any_status(status: InvitationStatus) -> None:
    once = revoked(application(status), T0)

    assert once.is_revoked
    assert once.status is status
    assert revoked(once, T0 + TTL) == once
