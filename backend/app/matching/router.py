"""Потребности работодателя: кого ищет, стек, грейд, формат, вилка и важность тем."""

import uuid

from fastapi import APIRouter, status

from app.assessment.schemas import CatalogRef
from app.assessment.service import UnknownSpecialization
from app.config import Mechanics, MechanicsDep
from app.db import DbSession
from app.errors import error_responses
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role
from app.matching import service
from app.matching.models import Need
from app.matching.schemas import NeedIn, NeedOut, TopicImportanceIn, TopicImportanceOut

router = APIRouter(
    prefix="/api/employer/needs",
    tags=["employer-needs"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)


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
