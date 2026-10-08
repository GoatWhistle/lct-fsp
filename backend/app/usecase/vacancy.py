"""Сценарии вакансий и откликов (mechanics.md, §14): работодатель публикует, правит и снимает
свои вакансии и решает по откликам на них; кандидат видит опубликованные вакансии, откликается,
видит свои отклики и отзывает по ним доступ.

Чужая вакансия и чужой отклик для зрителя не существуют — `VacancyNotFound` и
`ApplicationNotFound`, а не отказ в доступе. Статус отклика на момент чтения выводит домен
(`Application.at`), поэтому каждый сценарий читает «сейчас» один раз. Откликнуться может любой
кандидат с анкетой, и без категории: это его инициатива. Публикует компания — без профиля компании
кандидату не показать, чья вакансия.
"""

import uuid
from datetime import datetime, timedelta

from app.domain.application import Application, answered, check_can_apply, viewed
from app.domain.errors import (
    ApplicationNotFound,
    CompanyRequired,
    ProfileNotFound,
    VacancyArchived,
    VacancyNotFound,
)
from app.domain.vacancy import Vacancy, VacancyForm, VacancyTerms, archived, vacancy_terms
from app.usecase.candidate import revoke_company_access
from app.usecase.interface import (
    ApplicationRepository,
    CandidateRepository,
    CatalogRepository,
    Clock,
    CompanyRepository,
    InvitationRepository,
    UnitOfWork,
    VacancyRepository,
)


class Vacancies:
    def __init__(
        self,
        uow: UnitOfWork,
        vacancies: VacancyRepository,
        companies: CompanyRepository,
        catalog: CatalogRepository,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._vacancies = vacancies
        self._companies = companies
        self._catalog = catalog
        self._clock = clock

    def publish(self, employer_id: uuid.UUID, form: VacancyForm) -> Vacancy:
        with self._uow:
            company_name = self._company_name(employer_id)
            return self._vacancies.add(
                employer_id, company_name, self._terms(form), self._clock.now()
            )

    def update(self, employer_id: uuid.UUID, vacancy_id: uuid.UUID, form: VacancyForm) -> Vacancy:
        """Заменяет условия целиком; чужая проверяется раньше формы, архивную не правят —
        `VacancyArchived`."""
        with self._uow:
            current = self._own(employer_id, vacancy_id)
            if current.is_archived:
                raise VacancyArchived()
            result = Vacancy(
                id=current.id,
                employer_id=employer_id,
                company_name=self._company_name(employer_id),
                terms=self._terms(form),
                published_at=current.published_at,
                updated_at=self._clock.now(),
            )
            self._vacancies.save(result)
            return result

    def archive(self, employer_id: uuid.UUID, vacancy_id: uuid.UUID) -> Vacancy:
        """Снять с публикации; повторно — ничего не меняет. Поданные отклики остаются."""
        with self._uow:
            current = self._own(employer_id, vacancy_id)
            result = archived(current, self._clock.now())
            if result != current:
                self._vacancies.save(result)
            return result

    def own(self, employer_id: uuid.UUID) -> list[Vacancy]:
        """Вакансии компании, и архивные, — новые сверху."""
        with self._uow:
            return self._vacancies.by_employer(employer_id)

    def published(self, specialization: str | None = None) -> list[Vacancy]:
        """Общий список для кандидатов: только опубликованные, новые сверху."""
        with self._uow:
            return self._vacancies.published(specialization)

    def _own(self, employer_id: uuid.UUID, vacancy_id: uuid.UUID) -> Vacancy:
        vacancy = self._vacancies.get(vacancy_id, for_update=True)
        if vacancy is None or vacancy.employer_id != employer_id:
            raise VacancyNotFound()
        return vacancy

    def _company_name(self, employer_id: uuid.UUID) -> str:
        company = self._companies.get(employer_id)
        if company is None:
            raise CompanyRequired()
        return company.name

    def _terms(self, form: VacancyForm) -> VacancyTerms:
        return vacancy_terms(
            form, self._catalog.specialization(form.specialization), self._catalog.grade(form.grade)
        )


class Applications:
    def __init__(
        self,
        uow: UnitOfWork,
        applications: ApplicationRepository,
        vacancies: VacancyRepository,
        invitations: InvitationRepository,
        candidates: CandidateRepository,
        clock: Clock,
        *,
        ttl_days: int,
    ) -> None:
        self._uow = uow
        self._applications = applications
        self._candidates = candidates
        self._vacancies = vacancies
        self._invitations = invitations
        self._clock = clock
        self.ttl = timedelta(days=ttl_days)

    def apply(self, candidate_id: uuid.UUID, vacancy_id: uuid.UUID) -> Application:
        """Отклик на опубликованную вакансию — один раз: повторный — `AlreadyApplied`, на
        архивную — `VacancyArchived`; без анкеты — `ProfileNotFound`: компании нечего показать.
        Сразу раскрывает кандидата компании вакансии."""
        with self._uow:
            if self._candidates.get(candidate_id).profile is None:
                raise ProfileNotFound()
            # Блокировка вакансии — отклики на неё по очереди: двойной клик не даст двух.
            vacancy = self._vacancies.get(vacancy_id, for_update=True)
            if vacancy is None:
                raise VacancyNotFound()
            check_can_apply(vacancy, self._applications.find(vacancy_id, candidate_id))
            return self._applications.add(vacancy, candidate_id, self._clock.now())

    def mine(self, candidate_id: uuid.UUID) -> list[Application]:
        """Отклики кандидата — и на снятые с публикации вакансии."""
        with self._uow:
            now = self._clock.now()
            return [a.at(now, self.ttl) for a in self._applications.by_candidate(candidate_id)]

    def revoke(self, candidate_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        """Отозвать доступ компании вакансии: закрывает все отклики и принятые приглашения этой
        компании кандидату. Повторно — ничего не меняет."""
        with self._uow:
            now = self._clock.now()
            application = self._applications.get(application_id, for_update=True)
            if application is None or application.candidate_id != candidate_id:
                raise ApplicationNotFound()
            # Повторный отзыв ничего не меняет — и не закрывает доступ, открытый после первого.
            if application.is_revoked:
                return application.at(now, self.ttl)
            revoke_company_access(
                self._invitations, self._applications, candidate_id, application.employer_id, now
            )
            result = self._applications.get(application_id)
            assert result is not None, "отклик прочитан выше"
            return result.at(now, self.ttl)

    def incoming(
        self, employer_id: uuid.UUID, vacancy_id: uuid.UUID | None = None
    ) -> list[Application]:
        """Отклики на вакансии компании; `vacancy_id` — только на эту, чужая — `VacancyNotFound`."""
        with self._uow:
            if vacancy_id is not None:
                vacancy = self._vacancies.get(vacancy_id)
                if vacancy is None or vacancy.employer_id != employer_id:
                    raise VacancyNotFound()
            now = self._clock.now()
            return [
                a.at(now, self.ttl) for a in self._applications.by_employer(employer_id, vacancy_id)
            ]

    def view(self, employer_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        """Работодатель открыл отклик: отправленный становится просмотренным."""
        with self._uow:
            now = self._clock.now()
            current = self._incoming(employer_id, application_id, now)
            result = viewed(current, now)
            if result != current:
                self._applications.save(result)
            return result

    def answer(
        self, employer_id: uuid.UUID, application_id: uuid.UUID, *, accept: bool
    ) -> Application:
        """Принять или отклонить; по закрытому или истёкшему — `ApplicationTransitionNotAllowed`."""
        with self._uow:
            now = self._clock.now()
            result = answered(
                self._incoming(employer_id, application_id, now), accept=accept, now=now
            )
            self._applications.save(result)
            return result

    def _incoming(
        self, employer_id: uuid.UUID, application_id: uuid.UUID, now: datetime
    ) -> Application:
        """Отклик на вакансию компании на момент `now` — под блокировкой до конца блока."""
        application = self._applications.get(application_id, for_update=True)
        if application is None or application.employer_id != employer_id:
            raise ApplicationNotFound()
        return application.at(now, self.ttl)
