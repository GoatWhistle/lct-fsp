"""Правило раскрытия (mechanics.md, §14): по кандидату, зрителю и входам доступа — раскрытая или
обезличенная карточка. Без базы и HTTP: ветки, до которых HTTP пока не дотягивается, — тоже здесь.
"""

import dataclasses
import uuid
from datetime import UTC, datetime

import pytest

from app.domain.candidate import (
    NO_ACCESS,
    Access,
    AnonymizedCard,
    Candidate,
    CandidateProfile,
    CandidateViewer,
    Category,
    Disclosed,
    DisclosedCard,
    EmployerViewer,
    Level,
    SelfReported,
    SkillProfile,
    disclosure,
)
from app.domain.catalog import CatalogRef
from app.domain.fsp import AnonymizedAchievement
from app.domain.skill import Normal
from app.domain.work import WorkFormat

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
LEVEL = Level.of(Normal(0.4, 0.3), {"junior": -1.0, "middle": 0.0, "senior": 1.0}, 0.8)

SELF_REPORTED = SelfReported(
    stack=(CatalogRef("python", "Python"),),
    experience_years=4,
    work_formats=(WorkFormat.remote,),
    city="Казань",
    relocation=True,
    industries=(),
)
PROFILE = CandidateProfile(
    disclosed=Disclosed(
        full_name="Ёлкина Юлия Сергеевна",
        contact_email="yulia@example.ru",
        contact_phone="+7 999 123-45-67",
        telegram="yolkina_qa",
        about="Пишу автотесты",
        job_roles=("тимлид",),
        soft_skills=("Наставничество",),
    ),
    self_reported=SELF_REPORTED,
    updated_at=NOW,
)
CANDIDATE = Candidate(
    id=uuid.uuid4(),
    profile=PROFILE,
    expected_salary=287_500,
    category=Category(CatalogRef("qa", "QA"), CatalogRef("middle", "Middle"), NOW),
    skill_profile=SkillProfile(LEVEL, (), updated_at=NOW, last_signal_at=NOW),
)
EMPLOYER = EmployerViewer(uuid.uuid4())

# Поля, которых в обезличенной карточке нет по типу (§14, §17): ФИО, фото, возраст, вуз,
# контакты, свободный текст и ожидаемая зарплата — ни сами, ни в составе раскрываемого.
HIDDEN = {
    "full_name",
    "photo",
    "age",
    "birth_date",
    "university",
    "contact_email",
    "contact_phone",
    "telegram",
    "about",
    "job_roles",
    "soft_skills",
    "expected_salary",
    "salary_from",
    "disclosed",
    "profile",
}


def field_types(cls: type) -> set[type]:
    return {f.type for f in dataclasses.fields(cls) if isinstance(f.type, type)}


def test_anonymized_card_has_no_hidden_fields_by_type() -> None:
    names = {f.name for f in dataclasses.fields(AnonymizedCard)}

    assert names == {
        "candidate_id",
        "self_reported",
        "category",
        "skill_profile",
        "fsp_achievements",
        "grade_status",
    }
    assert not names & HIDDEN
    # Достижение ФСП в карточке — тип результата, дисциплина и год: мероприятие, место и команда
    # узнают человека.
    assert {f.name for f in dataclasses.fields(AnonymizedAchievement)} == {
        "result",
        "discipline",
        "year",
    }
    # Самоописание в карточке — только структурная часть, без раскрываемого.
    assert not {f.name for f in dataclasses.fields(SelfReported)} & HIDDEN
    assert Disclosed not in field_types(AnonymizedCard)


def test_candidate_sees_own_profile_disclosed_with_expected_salary() -> None:
    card = disclosure(CANDIDATE, CandidateViewer(CANDIDATE.id), NO_ACCESS)

    assert card == DisclosedCard(
        candidate_id=CANDIDATE.id,
        profile=PROFILE,
        expected_salary=287_500,
        category=CANDIDATE.category,
        skill_profile=CANDIDATE.skill_profile,
        grade_status=CANDIDATE.grade_status,
    )
    assert card.self_reported == SELF_REPORTED


def test_own_profile_is_disclosed_even_with_revoked_access() -> None:
    card = disclosure(CANDIDATE, CandidateViewer(CANDIDATE.id), Access(revoked=True))

    assert isinstance(card, DisclosedCard)


def test_own_card_without_profile() -> None:
    blank = dataclasses.replace(CANDIDATE, profile=None, expected_salary=None)

    card = disclosure(blank, CandidateViewer(blank.id), NO_ACCESS)

    assert isinstance(card, DisclosedCard)
    assert (card.profile, card.self_reported, card.expected_salary) == (None, None, None)


ANONYMIZED = AnonymizedCard(
    candidate_id=CANDIDATE.id,
    self_reported=SELF_REPORTED,
    category=CANDIDATE.category,
    skill_profile=CANDIDATE.skill_profile,
    grade_status=CANDIDATE.grade_status,
)


@pytest.mark.parametrize(
    ("viewer", "access"),
    [
        pytest.param(EMPLOYER, NO_ACCESS, id="работодатель без доступа"),
        pytest.param(CandidateViewer(uuid.uuid4()), NO_ACCESS, id="другой кандидат"),
        pytest.param(
            CandidateViewer(uuid.uuid4()),
            Access(invitation_accepted=True),
            id="другой кандидат с чужим доступом",
        ),
        pytest.param(EMPLOYER, Access(revoked=True), id="отзыв без приглашения"),
        pytest.param(
            EMPLOYER,
            Access(invitation_accepted=True, revoked=True),
            id="отзыв поверх приглашения",
        ),
        pytest.param(EMPLOYER, Access(applied=True, revoked=True), id="отзыв поверх отклика"),
        pytest.param(
            EMPLOYER,
            Access(invitation_accepted=True, applied=True, revoked=True),
            id="отзыв поверх приглашения и отклика",
        ),
        # Согласие на публикацию само по себе не раскрывает: раскрытие — только приглашение
        # или отклик.
        pytest.param(EMPLOYER, Access(publication_consent=True), id="согласие без приглашения"),
    ],
)
def test_anonymized_unless_own_or_disclosed_to_employer(
    viewer: CandidateViewer | EmployerViewer, access: Access
) -> None:
    assert disclosure(CANDIDATE, viewer, access) == ANONYMIZED


@pytest.mark.parametrize(
    "access",
    [
        pytest.param(Access(invitation_accepted=True), id="принятое приглашение"),
        pytest.param(Access(applied=True), id="отклик кандидата"),
        pytest.param(Access(invitation_accepted=True, applied=True), id="приглашение и отклик"),
    ],
)
def test_employer_with_access_sees_disclosed_card_without_expected_salary(access: Access) -> None:
    card = disclosure(CANDIDATE, EMPLOYER, access)

    assert card == DisclosedCard(
        candidate_id=CANDIDATE.id,
        profile=PROFILE,
        expected_salary=None,
        category=CANDIDATE.category,
        skill_profile=CANDIDATE.skill_profile,
        grade_status=CANDIDATE.grade_status,
    )


def test_anonymized_card_without_profile() -> None:
    blank = dataclasses.replace(CANDIDATE, profile=None, expected_salary=None)

    card = disclosure(blank, EMPLOYER, NO_ACCESS)

    assert card == AnonymizedCard(
        blank.id, None, blank.category, blank.skill_profile, blank.grade_status
    )


def test_no_access_is_the_default() -> None:
    assert Access() == NO_ACCESS
    assert not (NO_ACCESS.invitation_accepted or NO_ACCESS.applied or NO_ACCESS.revoked)
    assert not NO_ACCESS.publication_consent
