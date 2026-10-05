from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.assessment.models import Grade, Specialization, Technology, Topic
from app.db import DbSession
from app.errors import AppError, error_responses

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class SpecializationNotFound(AppError):
    status_code = 404
    code = "specialization_not_found"
    message = "Такой специализации нет в справочнике"


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GradeOut(_Out):
    code: str
    name: str
    rank: int = Field(description="Порядок грейда: чем больше, тем старше")


class TopicOut(_Out):
    code: str
    name: str


class SpecializationOut(_Out):
    code: str
    name: str
    topics: list[TopicOut]


class TechnologyOut(_Out):
    code: str
    name: str
    topics: list[str] = Field(description="Коды тем, на которые указывает технология")


@router.get("/grades", summary="Грейды от младшего к старшему")
def list_grades(db: DbSession) -> list[GradeOut]:
    grades = db.scalars(select(Grade).order_by(Grade.rank))
    return [GradeOut.model_validate(g) for g in grades]


@router.get("/specializations", summary="Специализации с темами")
def list_specializations(db: DbSession) -> list[SpecializationOut]:
    specializations = db.scalars(
        select(Specialization)
        .options(selectinload(Specialization.topics))
        .order_by(Specialization.position)
    )
    return [SpecializationOut.model_validate(s) for s in specializations]


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
