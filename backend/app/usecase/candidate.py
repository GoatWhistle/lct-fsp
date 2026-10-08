"""Сценарии профиля кандидата: анкета, PDF-профиль и карточка для работодателя.

Данные кандидата идут к зрителю только через правило раскрытия: сценарий берёт кандидата из
репозитория целиком, проводит через `disclosure` и отдаёт controller'у карточку. Кандидат видит
и меняет только свою анкету — его id приходит из сессии, чужого эндпоинты не принимают.
Работодатель получает карточку только кандидата с категорией: выдача строится по категориям,
кандидата без неё для работодателя нет. Профиль навыков в карточке — на «сейчас»
(`ProfileFreshness`).
"""

import uuid
from dataclasses import dataclass

from app.domain.candidate import (
    NO_ACCESS,
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
from app.usecase.interface import CandidateRepository, Clock, ProfilePdfRenderer, UnitOfWork
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
) -> DisclosedCard:
    with uow:
        now = clock.now()
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
    sheet = ProfileSheet.of(card, grade_confidence)
    if sheet is None:
        raise ProfileNotFound()
    return ProfilePdf(sheet.disclosed.full_name, renderer.render(sheet, now=now))


def employer_card(
    uow: UnitOfWork,
    candidates: CandidateRepository,
    employer_id: uuid.UUID,
    candidate_id: uuid.UUID,
    clock: Clock,
    freshness: ProfileFreshness,
) -> AnonymizedCard | DisclosedCard:
    """Карточка кандидата для работодателя; без категории — `CandidateNotFound`. Входов доступа
    пока нет: приглашений и откликов не существует — карточка обезличена."""
    with uow:
        candidate = candidates.get(candidate_id)
    if candidate.category is None:
        raise CandidateNotFound()
    fresh = freshness.candidate(candidate, clock.now())
    return disclosure(fresh, EmployerViewer(employer_id), NO_ACCESS)


def _own(candidate: Candidate) -> DisclosedCard:
    card = disclosure(candidate, CandidateViewer(candidate.id), NO_ACCESS)
    assert isinstance(card, DisclosedCard), "свой профиль кандидат видит раскрытым"
    return card
