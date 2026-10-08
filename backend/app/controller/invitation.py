"""Приглашения: работодатель отправляет кандидату предложение с вилкой, кандидат открывает его и
принимает или отклоняет. Принятое приглашение раскрывает кандидата этой компании."""

import uuid

from fastapi import APIRouter, status

from app.controller.deps import ROLE_RESPONSES, CurrentUser, InvitationsDep, role_guard
from app.controller.errors import error_responses
from app.controller.invitation_schemas import (
    InvitationBudgetOut,
    InvitationIn,
    InvitationOut,
    SentInvitationsOut,
)
from app.domain import errors
from app.domain.account import Role
from app.domain.invitation import Invitation, InvitationTerms
from app.domain.work import SalaryRange
from app.usecase.invitation import Invitations

employer_router = APIRouter(
    prefix="/api/employer/invitations",
    tags=["employer-invitations"],
    dependencies=role_guard(Role.employer),
    responses=ROLE_RESPONSES,
)

candidate_router = APIRouter(
    prefix="/api/candidate/invitations",
    tags=["candidate-invitations"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)

ANSWER_ERRORS = (
    errors.InvitationNotFound,
    errors.InvitationTransitionNotAllowed,
    errors.InvitationExpired,
)


@employer_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Пригласить кандидата",
    description="Вилка обязательна. Тратит одно приглашение из бюджета недели — отклонённые и "
    "истёкшие его не возвращают. Пока прошлое приглашение компании кандидату открыто, новое не "
    "создаётся.",
    responses=error_responses(
        errors.InvalidSalaryRange,
        errors.CandidateNotFound,
        errors.CompanyProfileRequired,
        errors.InvitationAlreadyOpen,
        errors.InvitationBudgetExhausted,
    ),
)
def send_invitation(
    body: InvitationIn, user: CurrentUser, invitations: InvitationsDep
) -> InvitationOut:
    terms = InvitationTerms(
        description=body.description,
        salary=SalaryRange(body.salary_from, body.salary_to),
        contact=body.contact,
    )
    return _out(invitations, invitations.send(user.id, body.candidate_id, terms))


@employer_router.get(
    "",
    summary="Отправленные приглашения и бюджет недели",
    description="Только приглашения своей компании, новые сверху.",
)
def list_sent(user: CurrentUser, invitations: InvitationsDep) -> SentInvitationsOut:
    sent = invitations.sent(user.id)
    budget = sent.budget
    return SentInvitationsOut(
        budget=InvitationBudgetOut(
            limit=budget.limit,
            used=budget.used,
            remaining=budget.remaining,
            resets_at=budget.resets_at,
        ),
        invitations=[_out(invitations, i) for i in sent.invitations],
    )


@employer_router.get(
    "/{invitation_id}",
    summary="Отправленное приглашение",
    responses=error_responses(errors.InvitationNotFound),
)
def get_sent(
    invitation_id: uuid.UUID, user: CurrentUser, invitations: InvitationsDep
) -> InvitationOut:
    return _out(invitations, invitations.sent_one(user.id, invitation_id))


@candidate_router.get("", summary="Входящие приглашения", description="Новые сверху.")
def list_inbox(user: CurrentUser, invitations: InvitationsDep) -> list[InvitationOut]:
    return [_out(invitations, i) for i in invitations.inbox(user.id)]


@candidate_router.post(
    "/{invitation_id}/view",
    summary="Открыть приглашение",
    description="Отправленное становится просмотренным; повторное открытие ничего не меняет.",
    responses=error_responses(errors.InvitationNotFound),
)
def view_invitation(
    invitation_id: uuid.UUID, user: CurrentUser, invitations: InvitationsDep
) -> InvitationOut:
    return _out(invitations, invitations.view(user.id, invitation_id))


@candidate_router.post(
    "/{invitation_id}/accept",
    summary="Принять приглашение",
    description="Компания увидит контакты и полный профиль, кроме ожидаемой зарплаты.",
    responses=error_responses(*ANSWER_ERRORS),
)
def accept_invitation(
    invitation_id: uuid.UUID, user: CurrentUser, invitations: InvitationsDep
) -> InvitationOut:
    return _out(invitations, invitations.answer(user.id, invitation_id, accept=True))


@candidate_router.post(
    "/{invitation_id}/decline",
    summary="Отклонить приглашение",
    responses=error_responses(*ANSWER_ERRORS),
)
def decline_invitation(
    invitation_id: uuid.UUID, user: CurrentUser, invitations: InvitationsDep
) -> InvitationOut:
    return _out(invitations, invitations.answer(user.id, invitation_id, accept=False))


def _out(invitations: Invitations, invitation: Invitation) -> InvitationOut:
    terms = invitation.terms
    return InvitationOut(
        id=invitation.id,
        candidate_id=invitation.candidate_id,
        company_name=invitation.company_name,
        description=terms.description,
        salary_from=terms.salary.low,
        salary_to=terms.salary.high,
        contact=terms.contact,
        status=invitation.status,
        sent_at=invitation.sent_at,
        viewed_at=invitation.viewed_at,
        answered_at=invitation.answered_at,
        expires_at=invitation.expires_at(invitations.ttl),
    )
