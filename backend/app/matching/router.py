"""Потребности работодателя и подборки по ним: кого ищет, стек, грейд, формат, вилка, важность
тем — и выдача кандидатов с объяснением."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.assessment.schemas import CatalogRef
from app.assessment.service import UnknownSpecialization
from app.config import Mechanics, MechanicsDep
from app.db import DbSession
from app.errors import error_responses
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role
from app.matching import selection, service
from app.matching.models import Need, Selection
from app.matching.schemas import (
    Explanation,
    NeedIn,
    NeedOut,
    SelectionEntryOut,
    SelectionOut,
    SelectionSummaryOut,
    StackFitOut,
    TopicFitOut,
    TopicImportanceIn,
    TopicImportanceOut,
)

router = APIRouter(
    prefix="/api/employer/needs",
    tags=["employer-needs"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

selections_router = APIRouter(
    prefix="/api/employer/selections",
    tags=["employer-selections"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

Offset = Annotated[int, Query(ge=0, description="Сколько мест выдачи пропустить")]
Limit = Annotated[int, Query(ge=1, le=100, description="Сколько кандидатов вернуть")]


@router.get("", summary="Потребности компании, новые сверху")
def list_needs(user: CurrentUser, db: DbSession, mechanics: MechanicsDep) -> list[NeedOut]:
    return [_need_out(need, mechanics) for need in service.list_needs(db, user.id)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Новая потребность",
    responses=error_responses(*service.NEED_ERRORS),
)
def create_need(body: NeedIn, user: CurrentUser, db: DbSession, mechanics: MechanicsDep) -> NeedOut:
    return _need_out(service.create_need(db, user.id, body), mechanics)


@router.post(
    "/topic-importance",
    summary="Важность тем по стеку — до сохранения",
    description="Та же функция, что у сохранённой потребности: форма показывает, как стек "
    "превращается в важность тем, пока работодатель его выбирает.",
    responses=error_responses(
        UnknownSpecialization, service.UnknownTechnology, service.TopicNotInSpecialization
    ),
)
def preview_topic_importance(
    body: TopicImportanceIn, db: DbSession, mechanics: MechanicsDep
) -> list[TopicImportanceOut]:
    return _topics_out(service.preview_topics(db, body, mechanics))


@router.get(
    "/{need_id}",
    summary="Потребность",
    responses=error_responses(service.NeedNotFound),
)
def get_need(
    need_id: uuid.UUID, user: CurrentUser, db: DbSession, mechanics: MechanicsDep
) -> NeedOut:
    return _need_out(service.get_need(db, user.id, need_id), mechanics)


@router.put(
    "/{need_id}",
    summary="Правка потребности",
    description="Заменяет потребность целиком, включая правки важности тем.",
    responses=error_responses(service.NeedNotFound, *service.NEED_ERRORS),
)
def update_need(
    need_id: uuid.UUID, body: NeedIn, user: CurrentUser, db: DbSession, mechanics: MechanicsDep
) -> NeedOut:
    return _need_out(service.update_need(db, user.id, need_id, body), mechanics)


@router.delete(
    "/{need_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление потребности",
    responses=error_responses(service.NeedNotFound),
)
def delete_need(need_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    service.delete_need(db, user.id, need_id)


@router.post(
    "/{need_id}/selections",
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать подборку",
    description="Строит подборку по текущей потребности и профилям навыков и сохраняет её: "
    "кандидаты с категорией потребности, затем «близкие» — соседнего грейда. Внутри блока — по "
    "соответствию × P(принятия). Каждый вызов — новая подборка; отдаёт первую страницу выдачи.",
    responses=error_responses(service.NeedNotFound),
)
def build_selection(
    need_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    mechanics: MechanicsDep,
    limit: Limit = 20,
) -> SelectionOut:
    return _selection_out(selection.build(db, user.id, need_id, mechanics, limit=limit))


@selections_router.get("", summary="Подборки компании, новые сверху")
def list_selections(
    user: CurrentUser,
    db: DbSession,
    need_id: Annotated[uuid.UUID | None, Query(description="Только по этой потребности")] = None,
) -> list[SelectionSummaryOut]:
    return [_summary_out(s) for s in selection.list_selections(db, user.id, need_id)]


@selections_router.get(
    "/{selection_id}",
    summary="Подборка",
    description="Выдача на момент построения — та же при каждом открытии, даже если потребность "
    "или профили кандидатов с тех пор изменились.",
    responses=error_responses(selection.SelectionNotFound),
)
def get_selection(
    selection_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    offset: Offset = 0,
    limit: Limit = 20,
) -> SelectionOut:
    return _selection_out(selection.get_page(db, user.id, selection_id, offset=offset, limit=limit))


def _need_out(need: Need, mechanics: Mechanics) -> NeedOut:
    return NeedOut(
        id=need.id,
        title=need.title,
        team_description=need.team_description,
        specialization=CatalogRef.model_validate(need.specialization),
        grade=CatalogRef.model_validate(need.grade),
        stack=[CatalogRef.model_validate(t) for t in need.stack],
        work_format=need.work_format,
        city=need.city,
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        topics=_topics_out(service.need_topics(need, mechanics)),
        created_at=need.created_at,
        updated_at=need.updated_at,
    )


def _topics_out(views: list[service.TopicView]) -> list[TopicImportanceOut]:
    return [
        TopicImportanceOut(
            topic=CatalogRef.model_validate(view.topic),
            importance=view.importance,
            edited=view.edited,
            technologies=[CatalogRef.model_validate(t) for t in view.technologies],
        )
        for view in views
    ]


def _summary_out(row: Selection) -> SelectionSummaryOut:
    need = selection.snapshot_of(row)
    return SelectionSummaryOut(
        id=row.id,
        need_id=row.need_id,
        title=need.title,
        specialization=need.specialization,
        grade=need.grade,
        exact_total=row.exact_total,
        nearby_total=row.nearby_total,
        created_at=row.created_at,
    )


def _selection_out(page: selection.Page) -> SelectionOut:
    requirements = {t.topic.code: t for t in page.need.topics}
    technologies = {t.code: t for t in page.need.stack}
    entries = []
    for entry in page.entries:
        explanation = Explanation.model_validate(entry.explanation)
        entries.append(
            SelectionEntryOut(
                candidate_id=entry.candidate_id,
                position=entry.position,
                block=entry.block,
                rank=entry.rank,
                grade=CatalogRef.model_validate(entry.grade),
                match_score=entry.match_score,
                acceptance_probability=entry.acceptance_probability,
                mutual_score=entry.mutual_score,
                topics=[
                    TopicFitOut(
                        topic=requirements[fit.topic].topic,
                        importance=requirements[fit.topic].importance,
                        weight=requirements[fit.topic].weight,
                        requirement=requirements[fit.topic].requirement,
                        **fit.model_dump(exclude={"topic"}),
                    )
                    for fit in explanation.topics
                ],
                stack=StackFitOut(
                    matched=[technologies[code] for code in explanation.stack.matched],
                    total=len(page.need.stack),
                    overlap=explanation.stack.overlap,
                    contribution=explanation.stack.contribution,
                ),
                stale=entry.stale,
            )
        )
    return SelectionOut(
        **_summary_out(page.selection).model_dump(),
        need=page.need,
        stack_cap=page.selection.stack_cap,
        offset=page.offset,
        entries=entries,
    )
