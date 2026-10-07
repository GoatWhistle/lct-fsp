from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.assessment.models import Grade, Industry, Specialization, Technology, Topic
from app.controller.errors import error_responses
from app.db import DbSession
from app.domain import bank
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
def list_grades(db: DbSession) -> list[GradeOut]:
    grades = db.scalars(select(Grade).order_by(Grade.rank))
    return [GradeOut.model_validate(g) for g in grades]


@router.get(
    "/industries",
    summary="Сферы бизнеса",
    description="Сфера деятельности компании и интересные кандидату сферы. Не «отрасль» из ТЗ: "
    "та — IT-направление, специализация.",
)
def list_industries(db: DbSession) -> list[IndustryOut]:
    industries = db.scalars(select(Industry).order_by(Industry.position))
    return [IndustryOut.model_validate(i) for i in industries]


@router.get("/specializations", summary="Специализации с темами")
def list_specializations(db: DbSession) -> list[SpecializationOut]:
    specializations = db.scalars(
        select(Specialization)
        .options(selectinload(Specialization.topics))
        .order_by(Specialization.position)
    )
    return [
        SpecializationOut(
            code=s.code,
            name=s.name,
            topics=[TopicOut.model_validate(t) for t in s.topics],
            has_test=bank.covers(t.code for t in s.topics),
        )
        for s in specializations
    ]


@router.get(
    "/technologies",
    summary="Технологии стека и их темы",
    description="С `specialization` — только технологии, связанные с темами этой "
    "специализации, и только её темы.",
    responses=error_responses(SpecializationNotFound),
)
def list_technologies(db: DbSession, specialization: str | None = None) -> list[TechnologyOut]:
    if specialization is not None and db.get(Specialization, specialization) is None:
        raise SpecializationNotFound()
    technologies = db.scalars(
        select(Technology).options(selectinload(Technology.topics)).order_by(Technology.name)
    )
    result = []
    for tech in technologies:
        topics: list[Topic] = tech.topics
        if specialization is not None:
            topics = [t for t in topics if t.specialization_code == specialization]
            if not topics:
                continue
        result.append(
            TechnologyOut(code=tech.code, name=tech.name, topics=[t.code for t in topics])
        )
    return result
