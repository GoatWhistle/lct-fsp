"""Сценарии профиля кандидата: анкета, PDF-профиль и карточка для работодателя.

Данные кандидата идут к зрителю только через правило раскрытия: сценарий берёт кандидата из
репозитория целиком, проводит через `disclosure` и отдаёт controller'у карточку. Кандидат видит
и меняет только свою анкету — его id приходит из сессии, чужого эндпоинты не принимают.
Работодатель получает карточку кандидата со статусом грейда — с категорией или с заявленным
грейдом, такого показывает нижний блок подборки, — или откликнувшегося на вакансию компании.
Остальных для работодателя нет. Профиль навыков в карточке — на «сейчас» (`ProfileFreshness`).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain import application, invitation
from app.domain.candidate import (
    NO_ACCESS,
    Access,
    AnonymizedCard,
    Candidate,
    CandidateViewer,
    DisclosedCard,
    EmployerViewer,
    ProfileForm,
    ProfileSheet,
    disclosure,
)
from app.domain.errors import CandidateNotFound, ProfileNotFound
from app.domain.experience import ExperienceLimits, check_experience
from app.domain.invitation import InvitationStatus
from app.usecase.interface import (
    ApplicationReader,
    ApplicationRepository,
    CandidateRepository,
    Clock,
    InvitationReader,
    InvitationRepository,
    ProfilePdfRenderer,
    UnitOfWork,
)
from app.usecase.skill_profile import ProfileFreshness


@dataclass(frozen=True)
class ProfilePdf:
    full_name: str
    content: bytes


def own_profile(
    uow: UnitOfWork,
    candidates: CandidateRepository,
    candidate_id: uuid.UUID,
    clock: Clock,
    freshness: ProfileFreshness,
) -> DisclosedCard:
    with uow:
        return _own(freshness.candidate(candidates.get(candidate_id), clock.now()))


def save_profile(
    uow: UnitOfWork,
    candidates: CandidateRepository,
    candidate_id: uuid.UUID,
    form: ProfileForm,
    clock: Clock,
    freshness: ProfileFreshness,
    *,
    experience_limits: ExperienceLimits,
) -> DisclosedCard:
    """Анкета целиком; карточку опыта сначала проверяет `check_experience` на сегодня."""
    with uow:
        now = clock.now()
        check_experience(form.experience, now.date(), experience_limits)
        candidates.save_profile(candidate_id, form, now)
        return _own(freshness.candidate(candidates.get(candidate_id), now))


def profile_pdf(
    uow: UnitOfWork,
    candidates: CandidateRepository,
    renderer: ProfilePdfRenderer,
    candidate_id: uuid.UUID,
    clock: Clock,
    freshness: ProfileFreshness,
    *,
    grade_confidence: float,
) -> ProfilePdf:
    """PDF-профиль — для самого кандидата: собирается из его раскрытой карточки."""
    now = clock.now()
    with uow:
        card = _own(freshness.candidate(candidates.get(candidate_id), now))
    sheet = ProfileSheet.of(card, grade_confidence, now.date())
    if sheet is None:
        raise ProfileNotFound()
    return ProfilePdf(sheet.disclosed.full_name, renderer.render(sheet, now=now))


def employer_card(
    uow: UnitOfWork,
    candidates: CandidateRepository,
    invitations: InvitationReader,
    applications: ApplicationReader,
    employer_id: uuid.UUID,
    candidate_id: uuid.UUID,
    clock: Clock,
    freshness: ProfileFreshness,
) -> AnonymizedCard | DisclosedCard:
    """Карточка кандидата для работодателя; без категории, заявленного грейда и отклика на
    вакансию компании — `CandidateNotFound`. Раскрывают её принятое приглашение компании и отклик
    на её вакансию, пока кандидат не отозвал доступ."""
    with uow:
        candidate = candidates.get(candidate_id)
        access = employer_access(invitations, applications, employer_id, candidate_id)
        if candidate.grade_status is None and not access.applied:
            raise CandidateNotFound()
    fresh = freshness.candidate(candidate, clock.now())
    return disclosure(fresh, EmployerViewer(employer_id), access)


def employer_access(
    invitations: InvitationReader,
    applications: ApplicationReader,
    employer_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> Access:
    """Входы доступа компании к кандидату — для каждого сценария, отдающего его данные
    работодателю. Отозванные приглашения и отклики порты не считают. Внутри блока единицы
    работы."""
    return Access(
        invitation_accepted=invitations.accepted(employer_id, candidate_id),
        applied=applications.applied(employer_id, candidate_id),
    )


def revoke_company_access(
    invitations: InvitationRepository,
    applications: ApplicationRepository,
    candidate_id: uuid.UUID,
    employer_id: uuid.UUID,
    now: datetime,
) -> None:
    """Кандидат закрывает компании свои данные: отзыв отмечает все её принятые приглашения и
    все отклики на её вакансии — иначе любое из них раскрывало бы данные дальше. Вернуть доступ
    — только новым принятым приглашением или откликом на другую её вакансию. Внутри блока
    единицы работы."""
    for i in invitations.by_candidate(candidate_id):
        if (
            i.employer_id == employer_id
            and i.status is InvitationStatus.accepted
            and not i.is_revoked
        ):
            invitations.save(invitation.revoked(i, now))
    for a in applications.by_candidate(candidate_id):
        if a.employer_id == employer_id and not a.is_revoked:
            applications.save(application.revoked(a, now))


def _own(candidate: Candidate) -> DisclosedCard:
    card = disclosure(candidate, CandidateViewer(candidate.id), NO_ACCESS)
    assert isinstance(card, DisclosedCard), "свой профиль кандидат видит раскрытым"
    return card
