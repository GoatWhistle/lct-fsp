"""Схемы API вакансий и откликов."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.controller.profile_schemas import WorkFormats
from app.controller.salary import SALARY_UNIT, Salary, SalaryBasisOut
from app.controller.schemas import CatalogRef
from app.domain.invitation import InvitationStatus
from app.domain.work import WorkFormat


class VacancyIn(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = Field(description="Должность")
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] = Field(
        default="", description="Задачи, команда, условия"
    )
    specialization: str = Field(description="Код специализации из `/api/catalog/specializations`")
    grade: str = Field(description="Код грейда из `/api/catalog/grades`")
    work_formats: WorkFormats = Field(min_length=1, description="Форматы работы")
    salary_from: Salary = Field(description=f"Вилка «от», обязательна. {SALARY_UNIT}")
    salary_to: Salary = Field(description=f"Вилка «до», обязательна. {SALARY_UNIT}")


class VacancyOut(SalaryBasisOut):
    id: uuid.UUID
    company_name: str = Field(description="Компания на момент последней правки")
    title: str
    description: str
    specialization: CatalogRef
    grade: CatalogRef
    work_formats: list[WorkFormat]
    salary_from: int = Field(description=SALARY_UNIT)
    salary_to: int = Field(description=SALARY_UNIT)
    published_at: datetime
    updated_at: datetime
    archived_at: datetime | None = Field(
        description="Когда снята с публикации: в общем списке её нет, откликнуться нельзя"
    )


class ApplicationOut(SalaryBasisOut):
    id: uuid.UUID
    vacancy_id: uuid.UUID
    candidate_id: uuid.UUID
    vacancy_title: str
    company_name: str
    salary_from: int = Field(description=f"Вилка вакансии. {SALARY_UNIT}")
    salary_to: int = Field(description=f"Вилка вакансии. {SALARY_UNIT}")
    status: InvitationStatus = Field(
        description="`sent` → `viewed`, когда работодатель открыл отклик → `accepted` или "
        "`declined` решением работодателя; `expired` — без ответа дольше срока с отклика"
    )
    applied_at: datetime
    viewed_at: datetime | None
    answered_at: datetime | None
    expires_at: datetime = Field(description="До какого момента работодатель может ответить")
    revoked_at: datetime | None = Field(
        description="Когда кандидат отозвал доступ: карточка для компании снова обезличена"
    )
