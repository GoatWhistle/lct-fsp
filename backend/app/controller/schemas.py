"""Схемы, общие для разделов API."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.candidate import GradeStatusKind


# Запись справочника в ответе — из `app.domain.catalog.CatalogRef` или любой записи с `code` и
# `name`. Без докстринга: он ушёл бы в описание схемы OpenAPI.
class CatalogRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class GradeStatusOut(BaseModel):
    """Что тест сказал о заявленном грейде. Заявленный — грейд первой попытки определения
    категории: дотест каскада его не меняет."""

    model_config = ConfigDict(from_attributes=True)

    kind: GradeStatusKind = Field(
        description="`confirmed` — подтверждён тестом; `below_claimed` — заявлен `claimed`, "
        "подтверждён `confirmed` ниже; `unconfirmed` — заявлен, тест не пройден"
    )
    claimed: CatalogRef = Field(description="Заявленный грейд")
    confirmed: CatalogRef | None = Field(description="Грейд категории; `null` — категории нет")
