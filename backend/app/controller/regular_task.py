"""Регулярные задания: кабинет работодателя — свои задания, ответы на них и оценка; кабинет
кандидата — каталог заданий своей специализации, ответ и свои ответы."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.controller.deps import ROLE_RESPONSES, CurrentUser, RegularTasksDep, role_guard
from app.controller.errors import error_responses
from app.controller.regular_task_schemas import (
    AnswerStatus,
    AuthorAnswerOut,
    CatalogTaskOut,
    GradeIn,
    OwnAnswerOut,
    TaskAnswerIn,
    TaskIn,
    TaskOut,
)
from app.controller.schemas import CatalogRef
from app.domain import errors
from app.domain.account import Role
from app.domain.regular_task import (
    TASK_FORM_ERRORS,
    CatalogFilter,
    OwnAnswer,
    RegularTask,
    TaskForm,
    TaskKind,
)
from app.usecase.regular_task import AuthorAnswer

employer_router = APIRouter(
    prefix="/api/employer/tasks",
    tags=["employer-tasks"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

candidate_router = APIRouter(
    prefix="/api/candidate/tasks",
    tags=["candidate-tasks"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


# Работодатель.


@employer_router.get("", summary="Свои задания, новые сверху — и снятые")
def list_tasks(user: CurrentUser, tasks: RegularTasksDep) -> list[TaskOut]:
    return [_task_out(t) for t in tasks.mine(user.id)]


@employer_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Новое задание",
    description="Для любой категории — специализация × грейд; 1–3 темы специализации. Ответ "
    "кандидата сужает погрешность его профиля по темам задания со сложностью от грейда задания.",
    responses=error_responses(errors.CompanyRequired, *TASK_FORM_ERRORS),
)
def create_task(body: TaskIn, user: CurrentUser, tasks: RegularTasksDep) -> TaskOut:
    return _task_out(tasks.create(user.id, _form(body)))


@employer_router.put(
    "/{task_id}",
    summary="Изменить задание",
    description="Только пока на задание никто не ответил и оно не снято.",
    responses=error_responses(errors.TaskNotFound, errors.TaskLocked, *TASK_FORM_ERRORS),
)
def update_task(
    task_id: uuid.UUID, body: TaskIn, user: CurrentUser, tasks: RegularTasksDep
) -> TaskOut:
    return _task_out(tasks.update(user.id, task_id, _form(body)))


@employer_router.post(
    "/{task_id}/withdraw",
    summary="Снять задание из каталога",
    description="Ответы и оценки по нему остаются в профилях кандидатов.",
    responses=error_responses(errors.TaskNotFound),
)
def withdraw_task(task_id: uuid.UUID, user: CurrentUser, tasks: RegularTasksDep) -> TaskOut:
    return _task_out(tasks.withdraw(user.id, task_id))


@employer_router.get(
    "/{task_id}/answers",
    summary="Ответы на своё задание",
    description="Обезличенно: псевдоним вместо кандидата, без ФИО, фото, возраста, вуза и "
    "контактов. Другие работодатели ответов не видят — только влияние на профиль.",
    responses=error_responses(errors.TaskNotFound),
)
def task_answers(
    task_id: uuid.UUID, user: CurrentUser, tasks: RegularTasksDep
) -> list[AuthorAnswerOut]:
    return [_author_answer_out(a) for a in tasks.answers(user.id, task_id)]


@employer_router.post(
    "/{task_id}/answers/{answer_id}/grade",
    summary="Оценить ответ по рубрике",
    description="Только открытое задание и только его автор; оценка ставится один раз.",
    responses=error_responses(
        errors.TaskNotFound,
        errors.TaskAnswerNotFound,
        errors.TaskNotGradable,
        errors.AnswerAlreadyGraded,
    ),
)
def grade_answer(
    task_id: uuid.UUID,
    answer_id: uuid.UUID,
    body: GradeIn,
    user: CurrentUser,
    tasks: RegularTasksDep,
) -> AuthorAnswerOut:
    return _author_answer_out(tasks.grade(user.id, task_id, answer_id, body.rubric))


# Кандидат.


@candidate_router.get(
    "",
    summary="Каталог заданий своей специализации",
    description="Активные задания специализации категории, всех грейдов: сначала с меньшим "
    "числом ответов, при равенстве — новые. Только кандидату с категорией по тесту.",
    responses=error_responses(errors.CategoryRequired),
)
def task_catalog(
    user: CurrentUser,
    tasks: RegularTasksDep,
    grade: Annotated[str | None, Query(description="Код грейда задания")] = None,
    topic: Annotated[str | None, Query(description="Код темы задания")] = None,
) -> list[CatalogTaskOut]:
    return [
        _catalog_out(item.task, answered=item.answered)
        for item in tasks.catalog(user.id, CatalogFilter(grade=grade, topic=topic))
    ]


@candidate_router.post(
    "/{task_id}/answer",
    summary="Ответить на задание",
    description="Один ответ на задание. Вердикт не показывается: ответ уходит в профиль "
    "навыков — сразу у задания с эталоном, после оценки автора у открытого. Категорию не меняет.",
    responses=error_responses(
        errors.CategoryRequired, errors.TaskNotFound, errors.TaskAlreadyAnswered
    ),
)
def answer_task(
    task_id: uuid.UUID, body: TaskAnswerIn, user: CurrentUser, tasks: RegularTasksDep
) -> OwnAnswerOut:
    return _own_answer_out(tasks.answer(user.id, task_id, body.response))


@candidate_router.get("/answers", summary="Свои ответы, новые сверху")
def own_answers(user: CurrentUser, tasks: RegularTasksDep) -> list[OwnAnswerOut]:
    return [_own_answer_out(a) for a in tasks.own_answers(user.id)]


def _form(body: TaskIn) -> TaskForm:
    return TaskForm(
        specialization=body.specialization,
        grade=body.grade,
        kind=body.kind,
        prompt=body.prompt,
        topics=tuple(body.topics),
        reference_answer=body.reference_answer,
    )


def _task_out(task: RegularTask) -> TaskOut:
    return TaskOut(
        id=task.id,
        specialization=CatalogRef.model_validate(task.specialization),
        grade=CatalogRef.model_validate(task.grade),
        kind=task.kind,
        prompt=task.prompt,
        topics=[CatalogRef.model_validate(t) for t in task.topics],
        reference_answer=task.reference_answer,
        answers=task.answers,
        editable=task.editable,
        created_at=task.created_at,
        updated_at=task.updated_at,
        withdrawn_at=task.withdrawn_at,
    )


def _catalog_out(task: RegularTask, *, answered: bool) -> CatalogTaskOut:
    return CatalogTaskOut(
        id=task.id,
        grade=CatalogRef.model_validate(task.grade),
        kind=task.kind,
        prompt=task.prompt,
        topics=[CatalogRef.model_validate(t) for t in task.topics],
        answers=task.answers,
        created_at=task.created_at,
        answered=answered,
    )


def _own_answer_out(own: OwnAnswer) -> OwnAnswerOut:
    answer = own.answer
    if own.task.kind == TaskKind.reference:
        state = AnswerStatus.accepted
    elif answer.rubric is None:
        state = AnswerStatus.awaiting_review
    else:
        state = AnswerStatus.reviewed
    return OwnAnswerOut(
        task=_catalog_out(own.task, answered=True),
        response=answer.response,
        answered_at=answer.answered_at,
        status=state,
    )


def _author_answer_out(item: AuthorAnswer) -> AuthorAnswerOut:
    answer = item.answer
    return AuthorAnswerOut(
        id=answer.id,
        candidate=item.pseudonym,
        response=answer.response,
        answered_at=answer.answered_at,
        correct=answer.correct,
        rubric=answer.rubric,
        graded_at=answer.graded_at,
    )
