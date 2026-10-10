"""Вакансии и отклики: работодатель публикует вакансию с вилкой и решает по откликам, кандидат
откликается сам. Отклик сразу раскрывает кандидата компании вакансии, пока кандидат не отозвал
доступ; бюджет приглашений отклики не тратят."""

import uuid

from fastapi import APIRouter, status

from app.controller.deps import (
    ROLE_RESPONSES,
    ApplicationsDep,
    CompaniesDep,
    CurrentUser,
    VacanciesDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.controller.vacancy_schemas import ApplicationOut, VacancyIn, VacancyOut
from app.domain import errors
from app.domain.account import Role
from app.domain.application import Application
from app.domain.vacancy import VACANCY_ERRORS, Vacancy, VacancyForm
from app.usecase.vacancy import Applications

employer_router = APIRouter(
    prefix="/api/employer",
    tags=["employer-vacancies"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

candidate_router = APIRouter(
    prefix="/api/candidate",
    tags=["candidate-vacancies"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)

ANSWER_ERRORS = (errors.ApplicationNotFound, errors.ApplicationTransitionNotAllowed)


@employer_router.post(
    "/vacancies",
    status_code=status.HTTP_201_CREATED,
    summary="Опубликовать вакансию",
    description="Вилка обязательна. Нужен профиль компании — кандидат видит, чья вакансия.",
    responses=error_responses(*VACANCY_ERRORS, errors.CompanyRequired),
)
def publish_vacancy(
    body: VacancyIn, user: CurrentUser, vacancies: VacanciesDep, companies: CompaniesDep
) -> VacancyOut:
    return _vacancy(vacancies.publish(user.id, _form(body)), companies.trusted({user.id}))


@employer_router.get(
    "/vacancies", summary="Вакансии компании", description="И снятые с публикации, новые сверху."
)
def list_own_vacancies(
    user: CurrentUser, vacancies: VacanciesDep, companies: CompaniesDep
) -> list[VacancyOut]:
    trusted = companies.trusted({user.id})
    return [_vacancy(v, trusted) for v in vacancies.own(user.id)]


@employer_router.put(
    "/vacancies/{vacancy_id}",
    summary="Править вакансию",
    description="Заменяет условия целиком; снятую с публикации не правят.",
    responses=error_responses(
        errors.VacancyNotFound, errors.VacancyArchived, *VACANCY_ERRORS, errors.CompanyRequired
    ),
)
def update_vacancy(
    vacancy_id: uuid.UUID,
    body: VacancyIn,
    user: CurrentUser,
    vacancies: VacanciesDep,
    companies: CompaniesDep,
) -> VacancyOut:
    return _vacancy(
        vacancies.update(user.id, vacancy_id, _form(body)), companies.trusted({user.id})
    )


@employer_router.post(
    "/vacancies/{vacancy_id}/archive",
    summary="Снять вакансию с публикации",
    description="Из общего списка уходит, откликнуться нельзя; поданные отклики остаются. "
    "Повторное снятие ничего не меняет.",
    responses=error_responses(errors.VacancyNotFound),
)
def archive_vacancy(
    vacancy_id: uuid.UUID, user: CurrentUser, vacancies: VacanciesDep, companies: CompaniesDep
) -> VacancyOut:
    return _vacancy(vacancies.archive(user.id, vacancy_id), companies.trusted({user.id}))


@employer_router.get(
    "/applications",
    summary="Отклики на вакансии компании",
    description="Новые сверху; `vacancy_id` — только на эту вакансию.",
    responses=error_responses(errors.VacancyNotFound),
)
def list_incoming(
    user: CurrentUser, applications: ApplicationsDep, vacancy_id: uuid.UUID | None = None
) -> list[ApplicationOut]:
    return [_application(applications, a) for a in applications.incoming(user.id, vacancy_id)]


@employer_router.post(
    "/applications/{application_id}/view",
    summary="Открыть отклик",
    description="Отправленный становится просмотренным; повторное открытие ничего не меняет.",
    responses=error_responses(errors.ApplicationNotFound),
)
def view_application(
    application_id: uuid.UUID, user: CurrentUser, applications: ApplicationsDep
) -> ApplicationOut:
    return _application(applications, applications.view(user.id, application_id))


@employer_router.post(
    "/applications/{application_id}/accept",
    summary="Принять отклик",
    responses=error_responses(*ANSWER_ERRORS),
)
def accept_application(
    application_id: uuid.UUID, user: CurrentUser, applications: ApplicationsDep
) -> ApplicationOut:
    return _application(applications, applications.answer(user.id, application_id, accept=True))


@employer_router.post(
    "/applications/{application_id}/decline",
    summary="Отклонить отклик",
    responses=error_responses(*ANSWER_ERRORS),
)
def decline_application(
    application_id: uuid.UUID, user: CurrentUser, applications: ApplicationsDep
) -> ApplicationOut:
    return _application(applications, applications.answer(user.id, application_id, accept=False))


@candidate_router.get(
    "/vacancies",
    summary="Опубликованные вакансии",
    description="Вакансии всех компаний, новые сверху; `specialization` — код специализации.",
)
def list_published(
    vacancies: VacanciesDep, companies: CompaniesDep, specialization: str | None = None
) -> list[VacancyOut]:
    published = vacancies.published(specialization)
    trusted = companies.trusted({v.employer_id for v in published})
    return [_vacancy(v, trusted) for v in published]


@candidate_router.post(
    "/vacancies/{vacancy_id}/apply",
    status_code=status.HTTP_201_CREATED,
    summary="Откликнуться на вакансию",
    description="Компания вакансии сразу увидит контакты и полный профиль, кроме ожидаемой "
    "зарплаты. Откликнуться можно один раз и без категории.",
    responses=error_responses(
        errors.VacancyNotFound,
        errors.VacancyArchived,
        errors.AlreadyApplied,
        errors.ProfileNotFound,
    ),
)
def apply(
    vacancy_id: uuid.UUID, user: CurrentUser, applications: ApplicationsDep
) -> ApplicationOut:
    return _application(applications, applications.apply(user.id, vacancy_id))


@candidate_router.get(
    "/applications",
    summary="Мои отклики",
    description="Новые сверху, и на снятые с публикации вакансии.",
)
def list_mine(user: CurrentUser, applications: ApplicationsDep) -> list[ApplicationOut]:
    return [_application(applications, a) for a in applications.mine(user.id)]


@candidate_router.post(
    "/applications/{application_id}/revoke",
    summary="Отозвать доступ компании к своим данным",
    description="Компания вакансии снова видит обезличенную карточку — отзыв закрывает все "
    "отклики и принятые приглашения этой компании. Вернуть доступ — только откликом на другую её "
    "вакансию или принятым приглашением. Повторный отзыв ничего не меняет.",
    responses=error_responses(errors.ApplicationNotFound),
)
def revoke_access(
    application_id: uuid.UUID, user: CurrentUser, applications: ApplicationsDep
) -> ApplicationOut:
    return _application(applications, applications.revoke(user.id, application_id))


def _form(body: VacancyIn) -> VacancyForm:
    return VacancyForm(
        title=body.title,
        description=body.description,
        specialization=body.specialization,
        grade=body.grade,
        work_formats=tuple(body.work_formats),
        salary_from=body.salary_from,
        salary_to=body.salary_to,
    )


def _vacancy(vacancy: Vacancy, trusted: set[uuid.UUID]) -> VacancyOut:
    terms = vacancy.terms
    return VacancyOut(
        id=vacancy.id,
        company_name=vacancy.company_name,
        title=terms.title,
        description=terms.description,
        specialization=CatalogRef.model_validate(terms.specialization),
        grade=CatalogRef.model_validate(terms.grade),
        work_formats=list(terms.work_formats),
        salary_from=terms.salary.low,
        salary_to=terms.salary.high,
        published_at=vacancy.published_at,
        updated_at=vacancy.updated_at,
        archived_at=vacancy.archived_at,
        company_domain_verified=vacancy.employer_id in trusted,
    )


def _application(applications: Applications, application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        vacancy_id=application.vacancy_id,
        candidate_id=application.candidate_id,
        vacancy_title=application.vacancy_title,
        company_name=application.company_name,
        salary_from=application.salary.low,
        salary_to=application.salary.high,
        status=application.status,
        applied_at=application.applied_at,
        viewed_at=application.viewed_at,
        answered_at=application.answered_at,
        expires_at=application.expires_at(applications.ttl),
        revoked_at=application.revoked_at,
    )
