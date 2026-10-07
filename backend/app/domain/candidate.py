"""Кандидат и его проекции для зрителя (mechanics.md, §11, §14).

Что из профиля кандидата, категории и профиля навыков увидит зритель, решает одно правило —
`disclosure`: по кандидату, зрителю и входам доступа оно отдаёт раскрытую или обезличенную
карточку. Сценарии, отдающие данные кандидата, проводят их через него; рендер и controller
показывают карточку как есть. Обезличенная карточка — те же категория, профиль навыков и
структурное самоописание, что в раскрытой, только без раскрываемого: его в ней нет по типу.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Self

from app.domain.catalog import CatalogRef
from app.domain.errors import CityRequired
from app.domain.skill import LevelBand, Normal, level_band
from app.domain.work import WorkFormat


@dataclass(frozen=True)
class Level:
    """Уровень θ с погрешностью и словами — полосой грейдов по правилу уверенности.

    Полоса считается при первом обращении: подборка читает тысячи уровней, а слова ей не нужны.
    `thresholds` — пороги грейдов, `confidence` — порог уверенности.
    """

    theta: float
    theta_sd: float
    thresholds: tuple[tuple[str, float], ...]
    confidence: float

    @classmethod
    def of(cls, level: Normal, thresholds: Mapping[str, float], confidence: float) -> Self:
        return cls(level.mean, level.sd, tuple(thresholds.items()), confidence)

    @cached_property
    def band(self) -> LevelBand:
        return level_band(Normal(self.theta, self.theta_sd), dict(self.thresholds), self.confidence)


@dataclass(frozen=True)
class TopicLevel:
    topic: CatalogRef
    level: Level


@dataclass(frozen=True)
class SkillProfile:
    """Профиль навыков: общий уровень и уровни по темам в порядке тем справочника.

    `last_signal_at` — последний сигнал об уровне; `None` — сигналов не было.
    """

    overall: Level
    topics: tuple[TopicLevel, ...]
    updated_at: datetime
    last_signal_at: datetime | None


@dataclass(frozen=True)
class Category:
    specialization: CatalogRef
    grade: CatalogRef
    assigned_at: datetime


@dataclass(frozen=True)
class SelfReported:
    """Структурная часть самоописания — видна и в обезличенной карточке."""

    stack: tuple[CatalogRef, ...]
    experience_years: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool
    industries: tuple[CatalogRef, ...]


@dataclass(frozen=True)
class Disclosed:
    """Видно только после раскрытия: ФИО, контакты, «о себе», роли и софт-скиллы."""

    full_name: str
    contact_email: str
    contact_phone: str | None
    telegram: str | None
    about: str
    job_roles: tuple[str, ...]
    soft_skills: tuple[str, ...]


@dataclass(frozen=True)
class CandidateProfile:
    """Профиль кандидата — анкета по форме. Ожидаемая зарплата — отдельно, в `Candidate`: она
    не входит ни в одну проекцию для работодателя, даже раскрытую (§14)."""

    disclosed: Disclosed
    self_reported: SelfReported
    updated_at: datetime


@dataclass(frozen=True)
class Candidate:
    """Всё о кандидате, что может попасть в проекцию, — вход правила раскрытия.

    Части, которых ещё нет, — `None`: анкета не заполнена, категория не присвоена. Профиль
    навыков — только вместе с категорией и по её специализации: оценки незаконченной или
    неудачной попытки он не подтверждает.
    """

    id: uuid.UUID
    profile: CandidateProfile | None
    expected_salary: int | None
    category: Category | None
    skill_profile: SkillProfile | None


@dataclass(frozen=True)
class CandidateViewer:
    user_id: uuid.UUID


@dataclass(frozen=True)
class EmployerViewer:
    user_id: uuid.UUID


Viewer = CandidateViewer | EmployerViewer
"""Кто смотрит на кандидата. Анонимный зритель до сценариев не доходит."""


@dataclass(frozen=True)
class Access:
    """Входы доступа работодателя к кандидату (§14).

    Раскрывают принятое приглашение компании и отклик кандидата на её вакансию; отзыв доступа
    побеждает и то и другое. Согласие на публикацию и скрытые кандидатом поля правило принимает
    уже сейчас, но решения они не меняют, пока их смысл не задан вместе с согласиями: без
    согласия кандидат уходит из выдачи — это отбор, а не проекция.

    Пока приглашений, откликов, согласий и настроек видимости нет, сценарии передают
    `NO_ACCESS`.
    """

    invitation_accepted: bool = False
    applied: bool = False
    revoked: bool = False
    publication_consent: bool = False
    hidden_fields: frozenset[str] = frozenset()


NO_ACCESS = Access()


@dataclass(frozen=True)
class AnonymizedCard:
    """Обезличенная карточка: решение — по навыкам. ФИО, контактов, свободного текста и
    ожидаемой зарплаты в ней нет по типу; фото, возраст и вуз платформа не собирает (§17)."""

    candidate_id: uuid.UUID
    self_reported: SelfReported | None
    category: Category | None
    skill_profile: SkillProfile | None


@dataclass(frozen=True)
class DisclosedCard:
    """Раскрытая карточка — анкета целиком. `expected_salary` — только самому кандидату:
    работодателю ожидаемая зарплата не показывается и после раскрытия (§14)."""

    candidate_id: uuid.UUID
    profile: CandidateProfile | None
    expected_salary: int | None
    category: Category | None
    skill_profile: SkillProfile | None

    @property
    def self_reported(self) -> SelfReported | None:
        return self.profile.self_reported if self.profile else None


def disclosure(
    candidate: Candidate, viewer: Viewer, access: Access
) -> DisclosedCard | AnonymizedCard:
    """Правило раскрытия: свой профиль кандидат видит раскрытым целиком; работодатель — после
    принятого приглашения или отклика, если доступ не отозван, и без ожидаемой зарплаты; все
    остальные — обезличенную карточку."""
    if isinstance(viewer, CandidateViewer) and viewer.user_id == candidate.id:
        return _disclosed(candidate, candidate.expected_salary)
    if (
        isinstance(viewer, EmployerViewer)
        and (access.invitation_accepted or access.applied)
        and not access.revoked
    ):
        return _disclosed(candidate, None)
    return AnonymizedCard(
        candidate_id=candidate.id,
        self_reported=candidate.profile.self_reported if candidate.profile else None,
        category=candidate.category,
        skill_profile=candidate.skill_profile,
    )


def _disclosed(candidate: Candidate, expected_salary: int | None) -> DisclosedCard:
    return DisclosedCard(
        candidate_id=candidate.id,
        profile=candidate.profile,
        expected_salary=expected_salary,
        category=candidate.category,
        skill_profile=candidate.skill_profile,
    )


@dataclass(frozen=True)
class ProfileSheet:
    """Всё, что входит в PDF-профиль, — раскрытая карточка в формате файла. Ожидаемой зарплаты
    в формате нет: файл может оказаться у работодателя (§14).

    `grade_confidence` — порог уверенности для подписи к уровням словами.
    """

    disclosed: Disclosed
    self_reported: SelfReported
    category: Category | None
    skill_profile: SkillProfile | None
    grade_confidence: float

    @classmethod
    def of(cls, card: DisclosedCard, grade_confidence: float) -> Self | None:
        """Лист PDF из раскрытой карточки; `None` — анкета не заполнена, PDF не из чего собрать."""
        if card.profile is None:
            return None
        return cls(
            disclosed=card.profile.disclosed,
            self_reported=card.profile.self_reported,
            category=card.category,
            skill_profile=card.skill_profile,
            grade_confidence=grade_confidence,
        )


@dataclass(frozen=True)
class ProfileForm:
    """Анкета, как её прислал кандидат: стек и интересные сферы — кодами справочника, ожидаемая
    зарплата — в рублях в месяц до вычета НДФЛ. Город обязателен, если подходит офис или гибрид.
    """

    full_name: str
    contact_email: str
    contact_phone: str | None
    telegram: str | None
    about: str
    job_roles: tuple[str, ...]
    soft_skills: tuple[str, ...]
    stack: tuple[str, ...]
    experience_years: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool
    industries: tuple[str, ...]
    expected_salary: int

    def __post_init__(self) -> None:
        if self.city is None and set(self.work_formats) != {WorkFormat.remote}:
            raise CityRequired()
