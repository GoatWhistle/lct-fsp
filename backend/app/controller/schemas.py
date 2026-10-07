"""Схемы, общие для разделов API."""

from pydantic import BaseModel, ConfigDict


# Запись справочника в ответе — из `app.domain.catalog.CatalogRef` или любой записи с `code` и
# `name`. Без докстринга: он ушёл бы в описание схемы OpenAPI.
class CatalogRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
