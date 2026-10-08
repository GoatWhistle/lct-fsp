"""Потребности работодателя и подборки по ним: кого ищет, стек, грейд, формат, вилка, важность
тем — и выдача кандидатов с объяснением."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.controller.deps import (
    ROLE_RESPONSES,
    CurrentUser,
    NeedDraftsDep,
    NeedsDep,
    SelectionsDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.need_schemas import (
    NeedDraftOut,
    NeedIn,
    NeedOut,
    NeedParseOut,
    NeedSnapshot,
    NeedTextIn,
    OutOfCatalogOut,
    RequirementOut,
    SelectionEntryOut,
    SelectionOut,
    SelectionSummaryOut,
    StackFitOut,
    TopicFitOut,
    TopicImportanceIn,
    TopicImportanceOut,
)
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain import errors
from app.domain.account import Role
from app.domain.need import NEED_ERRORS, NeedForm, TopicView
from app.domain.need_draft import CheckedDraft, CheckedOutOfCatalog
from app.domain.selection import NeedSnapshot as Snapshot
from app.domain.selection import Page, SelectionBlock, Summary
from app.usecase.need import NeedView

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
def list_needs(user: CurrentUser, needs: NeedsDep) -> list[NeedOut]:
    return [_need_out(view) for view in needs.all(user.id)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Новая потребность",
    responses=error_responses(*NEED_ERRORS),
)
def create_need(body: NeedIn, user: CurrentUser, needs: NeedsDep) -> NeedOut:
    return _need_out(needs.create(user.id, _form(body)))


@router.post(
    "/topic-importance",
    summary="Важность тем по стеку — до сохранения",
    description="Та же функция, что у сохранённой потребности: форма показывает, как стек "
    "превращается в важность тем, пока работодатель его выбирает.",
    responses=error_responses(
        errors.UnknownSpecialization, errors.UnknownTechnology, errors.TopicNotInSpecialization
    ),
)
def preview_topic_importance(body: TopicImportanceIn, needs: NeedsDep) -> list[TopicImportanceOut]:
    return _topics_out(needs.preview_topics(body.specialization, body.stack, body.topic_importance))


@router.post(
    "/parse",
    summary="Разобрать потребность из текста",
    description="Текст вакансии или описание как есть → черновик «система поняла так» со "
    "значениями справочника или ответ «такой специализации нет» с ближайшими. Разбор локальный, "
    "наружу текст не уходит; ничего не сохраняется.",
)
def parse_need(body: NeedTextIn, drafts: NeedDraftsDep) -> NeedParseOut:
    return _parsed_out(drafts.parse(body.text))


@router.get(
    "/{need_id}",
    summary="Потребность",
    responses=error_responses(errors.NeedNotFound),
)
def get_need(need_id: uuid.UUID, user: CurrentUser, needs: NeedsDep) -> NeedOut:
    return _need_out(needs.get(user.id, need_id))


@router.put(
    "/{need_id}",
    summary="Правка потребности",
    description="Заменяет потребность целиком, включая правки важности тем.",
    responses=error_responses(errors.NeedNotFound, *NEED_ERRORS),
)
def update_need(need_id: uuid.UUID, body: NeedIn, user: CurrentUser, needs: NeedsDep) -> NeedOut:
    return _need_out(needs.update(user.id, need_id, _form(body)))


@router.delete(
    "/{need_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление потребности",
    responses=error_responses(errors.NeedNotFound),
)
def delete_need(need_id: uuid.UUID, user: CurrentUser, needs: NeedsDep) -> None:
    needs.delete(user.id, need_id)


@router.post(
    "/{need_id}/selections",
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать подборку",
    description="Строит подборку по текущей потребности и профилям навыков и сохраняет её: "
    "кандидаты с категорией потребности, затем «близкие» — соседнего грейда. Внутри блока — по "
    "соответствию × P(принятия). Каждый вызов — новая подборка; отдаёт первую страницу выдачи.",
    responses=error_responses(errors.NeedNotFound),
)
def build_selection(
    need_id: uuid.UUID, user: CurrentUser, selections: SelectionsDep, limit: Limit = 20
) -> SelectionOut:
    return _selection_out(selections.build(user.id, need_id, limit=limit))


@selections_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать подборку по черновику",
    description="Та же подборка, что по сохранённой потребности, но по полям формы без "
    "сохранения — черновик из текста после правки. Правка и новый вызов — новая подборка, "
    "прежняя открывается с той же выдачей. `need_id` у такой подборки — `null`.",
    responses=error_responses(*NEED_ERRORS),
)
def build_draft_selection(
    body: NeedIn, user: CurrentUser, selections: SelectionsDep, limit: Limit = 20
) -> SelectionOut:
    return _selection_out(selections.build_draft(user.id, _form(body), limit=limit))


@selections_router.get("", summary="Подборки компании, новые сверху")
def list_selections(
    user: CurrentUser,
    selections: SelectionsDep,
    need_id: Annotated[uuid.UUID | None, Query(description="Только по этой потребности")] = None,
    limit: Limit = 50,
) -> list[SelectionSummaryOut]:
    return [_summary_out(s) for s in selections.summaries(user.id, need_id, limit=limit)]


@selections_router.get(
    "/{selection_id}",
    summary="Подборка",
    description="Выдача на момент построения — та же при каждом открытии, даже если потребность "
    "или профили кандидатов с тех пор изменились.",
    responses=error_responses(errors.SelectionNotFound),
)
def get_selection(
    selection_id: uuid.UUID,
    user: CurrentUser,
    selections: SelectionsDep,
    offset: Offset = 0,
    limit: Limit = 20,
) -> SelectionOut:
    return _selection_out(selections.open(user.id, selection_id, offset=offset, limit=limit))


def _form(body: NeedIn) -> NeedForm:
    return NeedForm(
        title=body.title,
        team_description=body.team_description,
        specialization=body.specialization,
        grade=body.grade,
        stack=tuple(body.stack),
        topic_importance=body.topic_importance,
        work_format=body.work_format,
        city=body.city,
        salary_from=body.salary_from,
        salary_to=body.salary_to,
    )


def _parsed_out(parsed: CheckedDraft | CheckedOutOfCatalog) -> NeedDraftOut | OutOfCatalogOut:
    if isinstance(parsed, CheckedOutOfCatalog):
        return OutOfCatalogOut(
            kind="out_of_catalog",
            asked=parsed.asked,
            nearest=[CatalogRef.model_validate(s) for s in parsed.nearest],
        )
    return NeedDraftOut(
        kind="draft",
        title=parsed.title,
        specialization=CatalogRef.model_validate(parsed.specialization)
        if parsed.specialization
        else None,
        grade=CatalogRef.model_validate(parsed.grade) if parsed.grade else None,
        stack=[CatalogRef.model_validate(t) for t in parsed.stack],
        work_format=parsed.work_format,
        city=parsed.city,
        salary_from=parsed.salary_from,
        salary_to=parsed.salary_to,
        confidence=dict(parsed.confidence),
        uncertain=sorted(parsed.uncertain),
    )


def _need_out(view: NeedView) -> NeedOut:
    record, need = view.record, view.record.need
    return NeedOut(
        id=need.id,
        title=need.title,
        team_description=record.team_description,
        specialization=CatalogRef.model_validate(need.specialization),
        grade=CatalogRef.model_validate(need.grade),
        stack=[CatalogRef.model_validate(t) for t in need.stack],
        work_format=need.work_format,
        city=need.city,
        salary_from=need.salary.low if need.salary else None,
        salary_to=need.salary.high if need.salary else None,
        topics=_topics_out(view.topics),
        created_at=record.created_at,
        updated_at=need.updated_at,
    )


def _topics_out(views: list[TopicView]) -> list[TopicImportanceOut]:
    return [
        TopicImportanceOut(
            topic=CatalogRef.model_validate(view.topic),
            importance=view.importance,
            edited=view.edited,
            technologies=[CatalogRef.model_validate(t) for t in view.technologies],
        )
        for view in views
    ]


def _summary_out(summary: Summary) -> SelectionSummaryOut:
    selection, need = summary.selection, summary.selection.need
    return SelectionSummaryOut(
        id=selection.id,
        need_id=selection.need_id,
        title=need.title,
        specialization=CatalogRef.model_validate(need.specialization),
        grade=CatalogRef.model_validate(need.grade),
        exact_total=summary.totals[SelectionBlock.exact],
        nearby_total=summary.totals[SelectionBlock.nearby],
        unconfirmed_total=summary.totals[SelectionBlock.unconfirmed],
        created_at=selection.created_at,
    )


def _snapshot_out(need: Snapshot) -> NeedSnapshot:
    return NeedSnapshot(
        title=need.title,
        specialization=CatalogRef.model_validate(need.specialization),
        grade=CatalogRef.model_validate(need.grade),
        stack=[CatalogRef.model_validate(t) for t in need.stack],
        work_format=need.work_format,
        city=need.city,
        salary_from=need.salary.low if need.salary else None,
        salary_to=need.salary.high if need.salary else None,
        topics=[
            RequirementOut(
                topic=CatalogRef.model_validate(t.topic),
                importance=t.importance,
                edited=t.edited,
                weight=t.weight,
                requirement=t.requirement,
            )
            for t in need.topics
        ],
        updated_at=need.updated_at,
    )


def _selection_out(page: Page) -> SelectionOut:
    need = _snapshot_out(page.selection.need)
    requirements = {t.topic.code: t for t in need.topics}
    technologies = {t.code: t for t in need.stack}
    entries = []
    for entry in page.entries:
        explanation = entry.explanation
        entries.append(
            SelectionEntryOut(
                candidate_id=entry.candidate_id,
                position=entry.position,
                block=entry.block,
                rank=entry.rank,
                grade=CatalogRef.model_validate(entry.grade),
                grade_status=GradeStatusOut.model_validate(entry.status),
                match_score=entry.match_score,
                acceptance_probability=entry.acceptance_probability,
                mutual_score=entry.mutual_score,
                topics=[
                    TopicFitOut(
                        topic=requirements[fit.topic].topic,
                        importance=requirements[fit.topic].importance,
                        weight=requirements[fit.topic].weight,
                        requirement=requirements[fit.topic].requirement,
                        theta=fit.theta,
                        theta_sd=fit.theta_sd,
                        probability=fit.probability,
                        contribution=fit.contribution,
                        verdict=fit.verdict,
                        low_data=fit.low_data,
                        fsp_confirmed=fit.fsp_confirmed,
                    )
                    for fit in explanation.topics
                ],
                stack=StackFitOut(
                    matched=[technologies[code] for code in explanation.stack.matched],
                    total=len(need.stack),
                    overlap=explanation.stack.overlap,
                    contribution=explanation.stack.contribution,
                ),
                stale=entry.stale,
            )
        )
    return SelectionOut(
        **_summary_out(page).model_dump(),
        need=need,
        stack_cap=page.selection.stack_cap,
        offset=page.offset,
        entries=entries,
    )
