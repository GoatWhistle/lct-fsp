"""Обратная связь кандидату: место в подборках за период и что поднимет выше (mechanics.md,
§15)."""

from fastapi import APIRouter

from app.controller.deps import ROLE_RESPONSES, CurrentUser, FeedbackDep, role_guard
from app.controller.feedback_schemas import ActionOut, FeedbackOut, HintOut, PlacementOut
from app.controller.schemas import CatalogRef
from app.domain.account import Role

router = APIRouter(
    prefix="/api/candidate/feedback",
    tags=["candidate-feedback"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


@router.get(
    "",
    summary="Обратная связь по подборкам",
    description="Только о себе: кандидат определяется по сессии. Агрегаты и подсказки по "
    "потребностям — когда кандидата включили подборки не меньше `feedback_min_companies` разных "
    "компаний.",
)
def get_feedback(user: CurrentUser, feedback: FeedbackDep) -> FeedbackOut:
    result = feedback.own(user.id)
    placement = result.placement
    return FeedbackOut(
        period_days=result.period_days,
        enough=result.enough,
        placement=PlacementOut(
            selections=placement.selections,
            median_position=placement.median_position,
            exact_share=placement.exact_share,
        )
        if placement
        else None,
        hints=[
            HintOut(
                topic=CatalogRef.model_validate(h.topic) if h.topic else None,
                action=ActionOut(kind=h.action.kind, available=h.action.available),
                scenario=h.scenario,
                gain=h.gain,
                places=h.places,
            )
            for h in result.hints
        ],
    )
