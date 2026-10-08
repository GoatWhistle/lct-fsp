"""Справочники для форм: грейды, сферы бизнеса, специализации с темами, технологии."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.controller.deps import CatalogQueriesDep
from app.controller.errors import error_responses
from app.domain.errors import SpecializationNotFound

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GradeOut(_Out):
    code: str
    name: str
    rank: int = Field(description="Порядок грейда: чем больше, тем старше")


class TopicOut(_Out):
    code: str
    name: str


class IndustryOut(_Out):
    code: str
    name: str


class SpecializationOut(_Out):
    code: str
    name: str
    topics: list[TopicOut]
    has_test: bool = Field(
        description="Тест готов: в банке есть задания по всем темам. Без него специализацию "
        "нельзя выбрать в опросе"
    )


class TechnologyOut(_Out):
    code: str
    name: str
    topics: list[str] = Field(description="Коды тем, на которые указывает технология")


@router.get("/grades", summary="Грейды от младшего к старшему")
def list_grades(catalog: CatalogQueriesDep) -> list[GradeOut]:
    return [GradeOut.model_validate(g) for g in catalog.grades()]


@router.get(
    "/industries",
    summary="Сферы бизнеса",
    description="Сфера деятельности компании и интересные кандидату сферы. Не «отрасль» из ТЗ: "
    "та — IT-направление, специализация.",
)
def list_industries(catalog: CatalogQueriesDep) -> list[IndustryOut]:
    return [IndustryOut.model_validate(i) for i in catalog.industries()]


@router.get("/specializations", summary="Специализации с темами")
def list_specializations(catalog: CatalogQueriesDep) -> list[SpecializationOut]:
    return [
        SpecializationOut(
            code=entry.specialization.code,
            name=entry.specialization.name,
            topics=[TopicOut.model_validate(t) for t in entry.specialization.topics],
            has_test=entry.has_test,
        )
        for entry in catalog.specializations()
    ]


@router.get(
    "/technologies",
    summary="Технологии стека и их темы",
    description="С `specialization` — только технологии, связанные с темами этой "
    "специализации, и только её темы.",
    responses=error_responses(SpecializationNotFound),
)
def list_technologies(
    catalog: CatalogQueriesDep, specialization: str | None = None
) -> list[TechnologyOut]:
    return [
        TechnologyOut(code=t.code, name=t.name, topics=list(t.topics))
        for t in catalog.technologies(specialization)
    ]
