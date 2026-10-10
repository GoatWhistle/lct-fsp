"""Схемы API приглашений: отправка, ответ кандидата, бюджет компании и переписка."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.controller.salary import SALARY_UNIT, Salary, SalaryBasisOut
from app.controller.vacancy_test_schemas import VacancyTestOut
from app.domain.conversation import Side
from app.domain.invitation import InvitationStatus


class InvitationIn(BaseModel):
    candidate_id: uuid.UUID
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)
    ] = Field(description="Что предлагаете: роль, команда, задачи")
    salary_from: Salary = Field(description=f"Вилка «от», обязательна. {SALARY_UNIT}")
    salary_to: Salary = Field(description=f"Вилка «до», обязательна. {SALARY_UNIT}")
    contact: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ] = Field(description="Как кандидату связаться с компанией, если примет приглашение")
    test_need_id: uuid.UUID | None = Field(
        default=None,
        description="Приложить тест по вакансии: потребность компании той же специализации, что "
        "категория кандидата",
    )


class InvitationOut(SalaryBasisOut):
    id: uuid.UUID
    candidate_id: uuid.UUID
    company_name: str = Field(description="Компания на момент отправки")
    description: str
    salary_from: int = Field(description=SALARY_UNIT)
    salary_to: int = Field(description=SALARY_UNIT)
    contact: str
    status: InvitationStatus = Field(
        description="`sent` → `viewed` → `accepted`, `declined` или `expired`; «истекло» — "
        "без ответа дольше срока с отправки"
    )
    sent_at: datetime
    viewed_at: datetime | None
    answered_at: datetime | None
    expires_at: datetime = Field(description="До какого момента можно ответить")
    revoked_at: datetime | None = Field(
        description="Когда кандидат отозвал доступ: карточка снова обезличена, переписка идёт"
    )
    unread_messages: int = Field(description="Непрочитанные сообщения другой стороны")
    company_domain_verified: bool = Field(
        description="Метка доверия: компания подтвердила домен своего сайта"
    )
    vacancy_test: VacancyTestOut | None = Field(
        description="Приложенный тест по вакансии; итог — только в ответах работодателю"
    )


class InvitationBudgetOut(BaseModel):
    limit: int = Field(description="Приглашений на компанию за календарную неделю")
    used: int = Field(description="Отправлено за текущую неделю в любом статусе")
    remaining: int
    resets_at: datetime = Field(description="Понедельник 00:00 по Москве")


class SentInvitationsOut(BaseModel):
    budget: InvitationBudgetOut
    invitations: list[InvitationOut] = Field(description="Новые сверху")


class MessageIn(BaseModel):
    text: str = Field(description="Только текст; пустой или длиннее предела — 422")


class MessageOut(BaseModel):
    id: uuid.UUID
    author: Side = Field(description="Чья сторона написала")
    text: str
    sent_at: datetime
    read_at: datetime | None = Field(description="Когда прочитала другая сторона")
