"""Тест по вакансии: работодатель смотрит, как система формирует тест по потребности, и
прикладывает его к приглашению; кандидат проходит его из приглашения теми же `item`, что тест.
Итог видит только пригласившая компания."""

import uuid

from fastapi import APIRouter, status

from app.controller.deps import ROLE_RESPONSES, CurrentUser, VacancyTestsDep, role_guard
from app.controller.errors import error_responses
from app.controller.path_schemas import OptionOut
from app.controller.schemas import CatalogRef
from app.controller.vacancy_test_schemas import (
    ExampleOut,
    PlannedTopicOut,
    TopicOutcomeOut,
    VacancyTestOut,
    VacancyTestPlanOut,
    VacancyTestPreviewOut,
    VacancyTestResultOut,
)
from app.domain import errors
from app.domain.account import Role
from app.domain.vacancy_test import VacancyTestPlan, VacancyTestResult
from app.usecase.vacancy_test import VacancyTestView

employer_router = APIRouter(
    prefix="/api/employer/needs",
    tags=["employer-needs"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

candidate_router = APIRouter(
    prefix="/api/candidate/invitations",
    tags=["candidate-invitations"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


@employer_router.get(
    "/{need_id}/test",
    summary="Тест по вакансии: темы, задания и примеры",
    description="В тест идут ключевые и важные темы потребности, без них — все темы "
    "специализации; задания делятся по весам важности. Пример на тему — новый экземпляр при "
    "каждом запросе, сложность — около требуемого уровня. Эталон не отдаётся.",
    responses=error_responses(errors.NeedNotFound),
)
def preview_test(
    need_id: uuid.UUID, user: CurrentUser, tests: VacancyTestsDep
) -> VacancyTestPreviewOut:
    preview = tests.preview(user.id, need_id)
    return VacancyTestPreviewOut(
        plan=plan_out(preview.plan),
        examples=[
            ExampleOut(
                topic=CatalogRef.model_validate(e.topic.topic),
                family_code=e.family_code,
                prompt=e.instance.prompt,
                code=e.instance.code,
                answer_format=e.instance.answer_format,
                options=[OptionOut(letter=o.letter, text=o.text) for o in e.instance.options],
            )
            for e in preview.examples
        ],
    )


@candidate_router.post(
    "/{invitation_id}/test",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Начать тест по вакансии из приглашения",
    description="Пока приглашение не отклонено и не истекло, один раз. Задания — через "
    "`/api/candidate/path/item`. Категорию, грейд и профиль навыков тест не меняет.",
    responses=error_responses(
        errors.InvitationNotFound,
        errors.VacancyTestNotFound,
        errors.VacancyTestTaken,
        errors.VacancyTestClosed,
        errors.AttemptInProgress,
        errors.CategoryRequired,
        errors.VacancyTestSpecializationMismatch,
    ),
)
def start_test(invitation_id: uuid.UUID, user: CurrentUser, tests: VacancyTestsDep) -> None:
    tests.start(user.id, invitation_id)


def plan_out(plan: VacancyTestPlan) -> VacancyTestPlanOut:
    return VacancyTestPlanOut(
        specialization=CatalogRef.model_validate(plan.specialization),
        grade=CatalogRef.model_validate(plan.grade),
        items=plan.items,
        topics=[
            PlannedTopicOut(
                topic=CatalogRef.model_validate(t.topic),
                importance=t.importance,
                weight=t.weight,
                items=t.items,
            )
            for t in plan.topics
        ],
    )


def vacancy_test_out(view: VacancyTestView) -> VacancyTestOut:
    return VacancyTestOut(
        need_title=view.test.need_title,
        plan=plan_out(view.test.plan),
        status=view.status,
        answered=view.answered,
        result=_result_out(view.result) if view.result else None,
    )


def _result_out(result: VacancyTestResult) -> VacancyTestResultOut:
    return VacancyTestResultOut(
        finished_at=result.finished_at,
        match=result.match,
        topics=[
            TopicOutcomeOut(
                topic=CatalogRef.model_validate(t.topic),
                answered=t.answered,
                correct=t.correct,
                level=t.level.mean,
                level_sd=t.level.sd,
                probability=t.probability,
            )
            for t in result.topics
        ],
    )
