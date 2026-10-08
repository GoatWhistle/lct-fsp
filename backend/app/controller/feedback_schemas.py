"""Схемы API обратной связи кандидату. Только числа и темы: ни работодателей, ни потребностей,
ни подборок, ни других кандидатов."""

from pydantic import BaseModel, Field

from app.controller.schemas import CatalogRef
from app.domain.feedback import ActionKind, Scenario


class PlacementOut(BaseModel):
    selections: int = Field(description="Подборок за период, в выдаче которых вы были")
    median_position: float = Field(
        description="Медианное место в общей выдаче: сначала точные, затем «близкие»"
    )
    exact_share: float = Field(description="Доля подборок, где вы были в точном блоке, 0–1")


class ActionOut(BaseModel):
    kind: ActionKind = Field(
        description="`regular_task` — ответить на регулярное задание по теме; `topic_block` — "
        "пройти блок по теме; `link_fsp` — привязать ФСП ID"
    )
    available: bool = Field(description="Действие можно выполнить сейчас")


class HintOut(BaseModel):
    topic: CatalogRef | None = Field(description="Тема; `null` — у привязки ФСП ID темы нет")
    action: ActionOut
    scenario: Scenario | None = Field(
        description="`narrow` — сузить погрешность, `raise` — поднять уровень на полосу; "
        "`null` — подсказка без числа"
    )
    gain: float | None = Field(
        description="Средний прирост скора соответствия по встреченным потребностям, 0–1"
    )
    places: float | None = Field(description="Средний выигрыш мест в подборках")


class FeedbackOut(BaseModel):
    period_days: int = Field(description="Период, за который считаются подборки, в днях")
    enough: bool = Field(
        description="Подборок достаточно: `false` — пока мало, агрегатов и подсказок по "
        "потребностям нет, только общая подсказка"
    )
    placement: PlacementOut | None
    hints: list[HintOut]
