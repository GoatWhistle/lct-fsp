"""Вакансии и отклики в Postgres — реализация портов `VacancyRepository` и
`ApplicationRepository`. Изменения не фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session, joinedload

from app.domain.application import Application
from app.domain.catalog import CatalogRef
from app.domain.invitation import InvitationStatus
from app.domain.vacancy import Vacancy, VacancyTerms
from app.domain.work import SalaryRange, WorkFormat
from app.repository.orm import Application as ApplicationRow
from app.repository.orm import Vacancy as VacancyRow

_VACANCY_LOADED = (joinedload(VacancyRow.specialization), joinedload(VacancyRow.grade))


class SqlVacancies:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, employer_id: uuid.UUID, company_name: str, terms: VacancyTerms, now: datetime
    ) -> Vacancy:
        row = VacancyRow(id=uuid.uuid4(), employer_id=employer_id, published_at=now, updated_at=now)
        _fill(row, company_name, terms)
        self._session.add(row)
        self._session.flush()
        found = self.get(row.id)
        assert found is not None, "вакансия только что записана"
        return found

    def get(self, vacancy_id: uuid.UUID, *, for_update: bool = False) -> Vacancy | None:
        stmt = (
            select(VacancyRow)
            .where(VacancyRow.id == vacancy_id)
            .options(*_VACANCY_LOADED)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update(of=VacancyRow)
        row = self._session.scalars(stmt).first()
        return _vacancy(row) if row else None

    def save(self, vacancy: Vacancy) -> None:
        row = self._session.get(VacancyRow, vacancy.id)
        assert row is not None, "сохраняется только прочитанная вакансия"
        _fill(row, vacancy.company_name, vacancy.terms)
        row.updated_at = vacancy.updated_at
        row.archived_at = vacancy.archived_at
        self._session.flush()

    def by_employer(self, employer_id: uuid.UUID) -> list[Vacancy]:
        return self._list(VacancyRow.employer_id == employer_id)

    def published(self, specialization: str | None = None) -> list[Vacancy]:
        where: list[ColumnElement[bool]] = [VacancyRow.archived_at.is_(None)]
        if specialization is not None:
            where.append(VacancyRow.specialization_code == specialization)
        return self._list(*where)

    def _list(self, *where: ColumnElement[bool]) -> list[Vacancy]:
        stmt = (
            select(VacancyRow)
            .where(*where)
            .options(*_VACANCY_LOADED)
            .order_by(VacancyRow.published_at.desc(), VacancyRow.id.desc())
            .execution_options(populate_existing=True)
        )
        return [_vacancy(row) for row in self._session.scalars(stmt)]


class SqlApplications:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, vacancy: Vacancy, candidate_id: uuid.UUID, now: datetime) -> Application:
        row = ApplicationRow(
            id=uuid.uuid4(),
            vacancy_id=vacancy.id,
            candidate_id=candidate_id,
            status=InvitationStatus.sent,
            applied_at=now,
        )
        self._session.add(row)
        self._session.flush()
        found = self.get(row.id)
        assert found is not None, "отклик только что записан"
        return found

    def get(self, application_id: uuid.UUID, *, for_update: bool = False) -> Application | None:
        stmt = (
            select(ApplicationRow)
            .where(ApplicationRow.id == application_id)
            .options(joinedload(ApplicationRow.vacancy))
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update(of=ApplicationRow)
        row = self._session.scalars(stmt).first()
        return _application(row) if row else None

    def find(self, vacancy_id: uuid.UUID, candidate_id: uuid.UUID) -> Application | None:
        found = self._list(
            ApplicationRow.vacancy_id == vacancy_id, ApplicationRow.candidate_id == candidate_id
        )
        return found[0] if found else None

    def save(self, application: Application) -> None:
        if application.status is InvitationStatus.expired:
            raise ValueError("истёкший не записывается — его выводит домен при чтении")
        row = self._session.get(ApplicationRow, application.id)
        assert row is not None, "сохраняется только прочитанный отклик"
        row.status = application.status
        row.viewed_at = application.viewed_at
        row.answered_at = application.answered_at
        row.revoked_at = application.revoked_at
        self._session.flush()

    def by_candidate(self, candidate_id: uuid.UUID) -> list[Application]:
        return self._list(ApplicationRow.candidate_id == candidate_id)

    def by_employer(
        self, employer_id: uuid.UUID, vacancy_id: uuid.UUID | None = None
    ) -> list[Application]:
        where: list[ColumnElement[bool]] = [VacancyRow.employer_id == employer_id]
        if vacancy_id is not None:
            where.append(ApplicationRow.vacancy_id == vacancy_id)
        return self._list(*where)

    def applied(self, employer_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
        found = self._session.scalar(
            select(ApplicationRow.id)
            .join(VacancyRow, ApplicationRow.vacancy_id == VacancyRow.id)
            .where(
                VacancyRow.employer_id == employer_id,
                ApplicationRow.candidate_id == candidate_id,
                ApplicationRow.revoked_at.is_(None),
            )
            .limit(1)
        )
        return found is not None

    def _list(self, *where: ColumnElement[bool]) -> list[Application]:
        stmt = (
            select(ApplicationRow)
            .join(VacancyRow, ApplicationRow.vacancy_id == VacancyRow.id)
            .where(*where)
            .options(joinedload(ApplicationRow.vacancy))
            .order_by(ApplicationRow.applied_at.desc(), ApplicationRow.id.desc())
            .execution_options(populate_existing=True)
        )
        return [_application(row) for row in self._session.scalars(stmt)]


def _fill(row: VacancyRow, company_name: str, terms: VacancyTerms) -> None:
    row.company_name = company_name
    row.title = terms.title
    row.description = terms.description
    row.specialization_code = terms.specialization.code
    row.grade_code = terms.grade.code
    row.work_formats = [f.value for f in terms.work_formats]
    row.salary_from = terms.salary.low
    row.salary_to = terms.salary.high


def _vacancy(row: VacancyRow) -> Vacancy:
    return Vacancy(
        id=row.id,
        employer_id=row.employer_id,
        company_name=row.company_name,
        terms=VacancyTerms(
            title=row.title,
            description=row.description,
            specialization=CatalogRef(row.specialization.code, row.specialization.name),
            grade=CatalogRef(row.grade.code, row.grade.name),
            work_formats=tuple(WorkFormat(f) for f in row.work_formats),
            salary=SalaryRange(row.salary_from, row.salary_to),
        ),
        published_at=row.published_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )


def _application(row: ApplicationRow) -> Application:
    vacancy = row.vacancy
    return Application(
        id=row.id,
        vacancy_id=row.vacancy_id,
        employer_id=vacancy.employer_id,
        candidate_id=row.candidate_id,
        vacancy_title=vacancy.title,
        company_name=vacancy.company_name,
        salary=SalaryRange(vacancy.salary_from, vacancy.salary_to),
        status=row.status,
        applied_at=row.applied_at,
        viewed_at=row.viewed_at,
        answered_at=row.answered_at,
        revoked_at=row.revoked_at,
    )
