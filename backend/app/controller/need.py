"""Потребности работодателя и подборки по ним: кого ищет, стек, грейд, формат, вилка, важность
тем — и выдача кандидатов с объяснением, её уточнение фильтрами, шортлист и поиск по банку."""

import uuid
from collections.abc import Sequence
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
    AcceptanceExplanationOut,
    AcceptanceFactorOut,
    CandidateFiltersIn,
    CandidateFiltersOut,
    CategoryFilterIn,
    NeedDraftOut,
    NeedIn,
    NeedOut,
    NeedParseOut,
    NeedSnapshot,
    NeedTextIn,
    OutOfCatalogOut,
    RequirementOut,
    SalaryHintOut,
    SearchHitOut,
    SearchOut,
    SelectionEntryOut,
    SelectionOut,
    SelectionSummaryOut,
    ShortlistOut,
    StackFitOut,
    TopicFitOut,
    TopicImportanceIn,
    TopicImportanceOut,
)
from app.controller.salary import SALARY_UNIT
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain import errors
from app.domain.acceptance import SalaryHint
from app.domain.account import Role
from app.domain.need import NEED_ERRORS, NeedForm, TopicView
from app.domain.need_draft import CheckedDraft, CheckedOutOfCatalog
from app.domain.search import CandidateFilters, CategoryFilter, SearchHit, SearchPage
from app.domain.selection import NeedSnapshot as Snapshot
from app.domain.selection import (
    Page,
    SelectionBlock,
    SelectionEntry,
    SelectionOrder,
    Shortlist,
    Summary,
)
from app.domain.work import SalaryRange
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

search_router = APIRouter(
    prefix="/api/employer/candidates",
    tags=["employer-selections"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

Offset = Annotated[int, Query(ge=0, description="Сколько мест выдачи пропустить")]
Limit = Annotated[int, Query(ge=1, le=100, description="Сколько кандидатов вернуть")]
SalaryQuery = Annotated[int, Query(gt=0, le=1_000_000_000, description=SALARY_UNIT)]
Order = Annotated[
    SelectionOrder,
    Query(
        description="`mutual` — сохранённый порядок по S × P; `match` — только соответствие: "
        "внутри блока по S, места и ранги пересчитаны под показанный порядок"
    ),
]


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


@search_router.post(
    "/search",
    summary="Поиск по банку кандидатов",
    description="Без потребности, по всей базе: кандидаты с категорией — по уверенности, что "
    "общий уровень не ниже порога грейда категории; с заявленным неподтверждённым грейдом — ниже "
    "всех подтверждённых. Карточки обезличены. Ничего не сохраняется.",
)
def search_candidates(
    body: CandidateFiltersIn,
    selections: SelectionsDep,
    offset: Offset = 0,
    limit: Limit = 20,
) -> SearchOut:
    return _search_out(selections.search(_filters(body), offset=offset, limit=limit))


@selections_router.get(
    "/{selection_id}",
    summary="Подборка",
    description="Выдача на момент построения — та же при каждом открытии, даже если потребность "
    "или профили кандидатов с тех пор изменились, — через последние применённые фильтры.",
    responses=error_responses(errors.SelectionNotFound),
)
def get_selection(
    selection_id: uuid.UUID,
    user: CurrentUser,
    selections: SelectionsDep,
    offset: Offset = 0,
    limit: Limit = 20,
    order: Order = SelectionOrder.mutual,
) -> SelectionOut:
    return _selection_out(
        selections.open(user.id, selection_id, offset=offset, limit=limit, order=order)
    )


@selections_router.get(
    "/{selection_id}/candidates/{candidate_id}/salary-hint",
    summary="Вероятность принятия при вилке и подсказка по вилке",
    description="Для формы приглашения: P(принятия) при вилке работодателя и самая низкая вилка, "
    "при которой P достигает целевой. Вилки в подсказке кратны шагу округления, P считается по "
    "округлённой вилке, ожидание кандидата не раскрывается. Нет файла модели — "
    "`available: false`, без ошибки.",
    responses=error_responses(
        errors.SelectionNotFound, errors.NotInSelection, errors.InvalidSalaryRange
    ),
)
def get_salary_hint(
    selection_id: uuid.UUID,
    candidate_id: uuid.UUID,
    user: CurrentUser,
    selections: SelectionsDep,
    salary_from: SalaryQuery,
    salary_to: SalaryQuery,
) -> SalaryHintOut:
    hint = selections.salary_hint(
        user.id, selection_id, candidate_id, SalaryRange(salary_from, salary_to)
    )
    return _hint_out(hint)


@selections_router.put(
    "/{selection_id}/filters",
    summary="Уточнить подборку фильтрами",
    description="Заменяет фильтры подборки и отдаёт выдачу через них. Выдача только сужается: "
    "места, ранги, скоры и объяснения — сохранённые, порядок — исходный. Пустой объект — сброс "
    "к исходной выдаче. Сохранённая выдача не меняется.",
    responses=error_responses(errors.SelectionNotFound),
)
def refine_selection(
    selection_id: uuid.UUID,
    body: CandidateFiltersIn,
    user: CurrentUser,
    selections: SelectionsDep,
    offset: Offset = 0,
    limit: Limit = 20,
    order: Order = SelectionOrder.mutual,
) -> SelectionOut:
    return _selection_out(
        selections.refine(
            user.id, selection_id, _filters(body), offset=offset, limit=limit, order=order
        )
    )


@selections_router.get(
    "/{selection_id}/shortlist",
    summary="Шортлист подборки",
    responses=error_responses(errors.SelectionNotFound),
)
def get_shortlist(
    selection_id: uuid.UUID, user: CurrentUser, selections: SelectionsDep
) -> ShortlistOut:
    return _shortlist_out(selections.shortlisted(user.id, selection_id))


@selections_router.put(
    "/{selection_id}/shortlist/{candidate_id}",
    summary="Добавить в шортлист",
    description="Только кандидата из выдачи этой подборки; повтор ничего не меняет.",
    responses=error_responses(errors.SelectionNotFound, errors.NotInSelection),
)
def add_to_shortlist(
    selection_id: uuid.UUID, candidate_id: uuid.UUID, user: CurrentUser, selections: SelectionsDep
) -> ShortlistOut:
    return _shortlist_out(selections.shortlist(user.id, selection_id, candidate_id, True))


@selections_router.delete(
    "/{selection_id}/shortlist/{candidate_id}",
    summary="Убрать из шортлиста",
    responses=error_responses(errors.SelectionNotFound, errors.NotInSelection),
)
def remove_from_shortlist(
    selection_id: uuid.UUID, candidate_id: uuid.UUID, user: CurrentUser, selections: SelectionsDep
) -> ShortlistOut:
    return _shortlist_out(selections.shortlist(user.id, selection_id, candidate_id, False))


def _filters(body: CandidateFiltersIn) -> CandidateFilters:
    return CandidateFilters(
        specialization=body.specialization,
        grade=body.grade,
        category=CategoryFilter(body.category.specialization, body.category.grade)
        if body.category
        else None,
        stack=frozenset(body.stack),
        fsp_confirmed=body.fsp_confirmed,
        confident=body.confident,
        grade_status=frozenset(body.grade_status),
    )


def _filters_out(filters: CandidateFilters) -> CandidateFiltersOut:
    category = filters.category
    return CandidateFiltersOut(
        specialization=filters.specialization,
        grade=filters.grade,
        category=CategoryFilterIn(specialization=category.specialization, grade=category.grade)
        if category
        else None,
        stack=sorted(filters.stack),
        fsp_confirmed=filters.fsp_confirmed,
        confident=filters.confident,
        grade_status=sorted(filters.grade_status),
    )


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
    selection = page.selection
    need = _snapshot_out(selection.need)
    return SelectionOut(
        **_summary_out(page).model_dump(),
        need=need,
        stack_cap=selection.stack_cap,
        offset=page.offset,
        filters=_filters_out(selection.filters),
        filtered_exact_total=page.filtered_totals[SelectionBlock.exact],
        filtered_nearby_total=page.filtered_totals[SelectionBlock.nearby],
        filtered_unconfirmed_total=page.filtered_totals[SelectionBlock.unconfirmed],
        shortlist=list(selection.shortlist),
        entries=_entries_out(need, page.entries),
    )


def _shortlist_out(shortlist: Shortlist) -> ShortlistOut:
    need = _snapshot_out(shortlist.selection.need)
    return ShortlistOut(
        selection_id=shortlist.selection.id, entries=_entries_out(need, shortlist.entries)
    )


def _search_out(page: SearchPage) -> SearchOut:
    return SearchOut(
        filters=_filters_out(page.filters),
        total=page.total,
        unconfirmed_total=page.unconfirmed_total,
        offset=page.offset,
        entries=[_hit_out(hit) for hit in page.hits],
    )


def _hit_out(hit: SearchHit) -> SearchHitOut:
    facts = hit.facts
    # Профиль навыков — только у кандидата с категорией.
    profile = facts.profile if facts.status.confirmed else None
    return SearchHitOut(
        candidate_id=facts.candidate_id,
        position=hit.position,
        specialization=facts.specialization,
        grade_status=GradeStatusOut.model_validate(facts.status),
        theta=profile.overall.mean if profile else None,
        theta_sd=profile.overall.sd if profile else None,
        grade_probability=hit.grade_probability,
        fsp_confirmed=facts.fsp_confirmed,
    )


def _hint_out(hint: SalaryHint | None) -> SalaryHintOut:
    if hint is None:
        return SalaryHintOut(
            available=False,
            probability=None,
            evaluated_from=None,
            evaluated_to=None,
            target_probability=None,
            reachable=False,
            hint_from=None,
            hint_to=None,
            rounding=None,
        )
    return SalaryHintOut(
        available=True,
        probability=hint.probability,
        evaluated_from=hint.evaluated.low,
        evaluated_to=hint.evaluated.high,
        target_probability=hint.target,
        reachable=hint.range is not None,
        hint_from=hint.range.low if hint.range else None,
        hint_to=hint.range.high if hint.range else None,
        rounding=hint.step,
    )


def _explanation_out(entry: SelectionEntry) -> AcceptanceExplanationOut | None:
    if entry.acceptance is None:
        return None
    why = entry.acceptance.explanation
    return AcceptanceExplanationOut(
        base=why.base,
        logit=why.logit,
        factors=[
            AcceptanceFactorOut(factor=f, contribution=v) for f, v in why.contributions.items()
        ],
    )


def _entries_out(need: NeedSnapshot, entries: Sequence[SelectionEntry]) -> list[SelectionEntryOut]:
    requirements = {t.topic.code: t for t in need.topics}
    technologies = {t.code: t for t in need.stack}
    out = []
    for entry in entries:
        explanation = entry.explanation
        out.append(
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
                acceptance_explanation=_explanation_out(entry),
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
                        regular_task=fit.regular_task,
                        fsp_confirmed=fit.fsp_confirmed,
                        verification_confirmed=fit.verification_confirmed,
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
    return out
