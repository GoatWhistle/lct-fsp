"""Кандидат и его проекции для зрителя (mechanics.md, §11, §14).

Что из профиля кандидата, категории и профиля навыков увидит зритель, решает одно правило —
`disclosure`: по кандидату, зрителю и входам доступа оно отдаёт раскрытую или обезличенную
карточку. Сценарии профиля, PDF-профиля и карточки проводят данные кандидата через него; рендер
и controller показывают карточку как есть. Выдача подборки (`app.domain.selection`) данных
кандидата не несёт: в записи выдачи только скоры и объяснение. Обезличенная карточка — те же
категория, профиль навыков и структурное самоописание, что в раскрытой, только без раскрываемого:
его в ней нет по типу; поля самоописания, скрытые кандидатом, в ней пусты и перечислены.
Достижения ФСП в обезличенной карточке — тип результата, дисциплина и год; мероприятие, место и
команда — только в раскрытой.
"""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Self

from app.domain.catalog import CatalogRef, Grade
from app.domain.errors import CityRequired
from app.domain.fsp import AnonymizedAchievement, ConfirmedAchievement, FspHistory, anonymized
from app.domain.skill import LevelBand, Normal, SignalSource, level_band
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
    # Из каких уровней доверия есть наблюдения по теме; пусто — уровень только из априорного.
    sources: frozenset[SignalSource] = frozenset()


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


class GradeStatusKind(enum.StrEnum):
    # Категория — заявленного грейда.
    confirmed = "confirmed"
    # Каскад дал категорию ниже заявленного грейда.
    below_claimed = "below_claimed"
    # Грейд заявлен, категории нет: тест не пройден или не закончен.
    unconfirmed = "unconfirmed"


@dataclass(frozen=True)
class GradeStatus:
    """Что тест сказал о заявленном грейде (§12). Заявленный грейд — грейд первой попытки
    цепочки определения категории: дотест каскада его не меняет."""

    kind: GradeStatusKind
    claimed: CatalogRef
    # Грейд категории; у `unconfirmed` — нет.
    confirmed: CatalogRef | None


def grade_status(category: Grade | None, claimed: Grade | None) -> GradeStatus | None:
    """Статус из грейда категории и заявленного грейда; без того и другого статуса нет.
    Категория без известной заявки — подтверждена: присвоить её мог только тест."""
    if category is None:
        if claimed is None:
            return None
        return GradeStatus(GradeStatusKind.unconfirmed, _ref(claimed), None)
    if claimed is not None and claimed.rank > category.rank:
        return GradeStatus(GradeStatusKind.below_claimed, _ref(claimed), _ref(category))
    return GradeStatus(GradeStatusKind.confirmed, _ref(category), _ref(category))


def _ref(grade: Grade) -> CatalogRef:
    return CatalogRef(grade.code, grade.name)


@dataclass(frozen=True)
class SelfReported:
    """Структурная часть самоописания — видна и в обезличенной карточке, кроме скрытого
    кандидатом."""

    stack: tuple[CatalogRef, ...]
    experience_years: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool
    industries: tuple[CatalogRef, ...]


class HideableField(enum.StrEnum):
    """Поля самоописания, которые кандидат может скрыть из обезличенной карточки (§14). Форматы
    работы, категория и профиль навыков видны всегда."""

    stack = "stack"
    experience_years = "experience_years"
    city = "city"
    relocation = "relocation"
    industries = "industries"


@dataclass(frozen=True)
class VisibleSelfReported:
    """Самоописание в обезличенной карточке: скрытое кандидатом поле — `None` и имя в `hidden`.
    Так «скрыто» не путается с «не заполнено»: незаполненный город — `None` без имени в
    `hidden`."""

    stack: tuple[CatalogRef, ...] | None
    experience_years: int | None
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool | None
    industries: tuple[CatalogRef, ...] | None
    hidden: frozenset[HideableField]

    @classmethod
    def of(cls, self_reported: SelfReported, hidden: frozenset[HideableField]) -> Self:
        def shown[T](field: HideableField, value: T) -> T | None:
            return None if field in hidden else value

        return cls(
            stack=shown(HideableField.stack, self_reported.stack),
            experience_years=shown(HideableField.experience_years, self_reported.experience_years),
            work_formats=self_reported.work_formats,
            city=shown(HideableField.city, self_reported.city),
            relocation=shown(HideableField.relocation, self_reported.relocation),
            industries=shown(HideableField.industries, self_reported.industries),
            hidden=hidden,
        )


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
    не входит ни в одну проекцию для работодателя, даже раскрытую (§14).

    `hidden` — поля самоописания, скрытые кандидатом из обезличенной карточки; по умолчанию
    видно всё. Подбор и скор их не замечают: настройка меняет только проекцию."""

    disclosed: Disclosed
    self_reported: SelfReported
    updated_at: datetime
    hidden: frozenset[HideableField] = frozenset()


@dataclass(frozen=True)
class Candidate:
    """Всё о кандидате, что может попасть в проекцию, — вход правила раскрытия.

    Части, которых ещё нет, — `None`: анкета не заполнена, категория не присвоена. Профиль
    навыков — только вместе с категорией и по её специализации: оценки незаконченной или
    неудачной попытки он не подтверждает. `fsp` — `None`, если ФСП ID не привязан.
    """

    id: uuid.UUID
    profile: CandidateProfile | None
    expected_salary: int | None
    category: Category | None
    skill_profile: SkillProfile | None
    # Нет ни категории, ни заявленного грейда — статуса нет.
    grade_status: GradeStatus | None = None
    fsp: FspHistory | None = None

    @property
    def fsp_achievements(self) -> tuple[ConfirmedAchievement, ...]:
        """Подтверждённые достижения; без ФСП ID — пусто, как и без истории ФСП."""
        return self.fsp.achievements if self.fsp else ()


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
    побеждает и то и другое. Настройки видимости — свойство кандидата, а не доступа: они в его
    профиле.

    Работодателю сценарии собирают доступ из приглашений компании и откликов на её вакансии
    (`employer_access`). Отозванные приглашения и отклики порты не считают, поэтому `revoked`
    сценарии не ставят.
    `NO_ACCESS` — доступа нет.
    """

    invitation_accepted: bool = False
    applied: bool = False
    revoked: bool = False


NO_ACCESS = Access()


@dataclass(frozen=True)
class AnonymizedCard:
    """Обезличенная карточка: решение — по навыкам. ФИО, контактов, свободного текста и
    ожидаемой зарплаты в ней нет по типу; фото, возраст и вуз платформа не собирает (§17).
    Скрытые кандидатом поля самоописания пусты."""

    candidate_id: uuid.UUID
    self_reported: VisibleSelfReported | None
    category: Category | None
    skill_profile: SkillProfile | None
    grade_status: GradeStatus | None
    # Пусто — нет истории ФСП: нейтральная пометка, не штраф.
    fsp_achievements: tuple[AnonymizedAchievement, ...] = ()


@dataclass(frozen=True)
class DisclosedCard:
    """Раскрытая карточка — анкета целиком. `expected_salary` — только самому кандидату:
    работодателю ожидаемая зарплата не показывается и после раскрытия (§14)."""

    candidate_id: uuid.UUID
    profile: CandidateProfile | None
    expected_salary: int | None
    category: Category | None
    skill_profile: SkillProfile | None
    grade_status: GradeStatus | None
    fsp_achievements: tuple[ConfirmedAchievement, ...] = ()

    @property
    def self_reported(self) -> SelfReported | None:
        return self.profile.self_reported if self.profile else None


def disclosure(
    candidate: Candidate, viewer: Viewer, access: Access
) -> DisclosedCard | AnonymizedCard:
    """Правило раскрытия: свой профиль кандидат видит раскрытым целиком; работодатель — после
    принятого приглашения или отклика, если доступ не отозван, и без ожидаемой зарплаты; все
    остальные — обезличенную карточку без скрытых кандидатом полей самоописания. Раскрытая
    карточка — всегда полная: настройки видимости действуют только до раскрытия."""
    if isinstance(viewer, CandidateViewer) and viewer.user_id == candidate.id:
        return _disclosed(candidate, candidate.expected_salary)
    if (
        isinstance(viewer, EmployerViewer)
        and (access.invitation_accepted or access.applied)
        and not access.revoked
    ):
        return _disclosed(candidate, None)
    profile = candidate.profile
    return AnonymizedCard(
        candidate_id=candidate.id,
        self_reported=(
            VisibleSelfReported.of(profile.self_reported, profile.hidden) if profile else None
        ),
        category=candidate.category,
        skill_profile=candidate.skill_profile,
        grade_status=candidate.grade_status,
        fsp_achievements=tuple(anonymized(a) for a in candidate.fsp_achievements),
    )


def _disclosed(candidate: Candidate, expected_salary: int | None) -> DisclosedCard:
    return DisclosedCard(
        candidate_id=candidate.id,
        profile=candidate.profile,
        expected_salary=expected_salary,
        category=candidate.category,
        skill_profile=candidate.skill_profile,
        grade_status=candidate.grade_status,
        fsp_achievements=candidate.fsp_achievements,
    )


@dataclass(frozen=True)
class ProfileSheet:
    """Всё, что входит в PDF-профиль, — раскрытая карточка в формате файла. Ожидаемой зарплаты
    в формате нет: файл может оказаться у работодателя (§14).

    `grade_confidence` — порог уверенности для подписи к уровням словами. Достижения ФСП —
    полностью, отдельно от самоописания; пусто — нет истории ФСП.
    """

    disclosed: Disclosed
    self_reported: SelfReported
    category: Category | None
    skill_profile: SkillProfile | None
    grade_confidence: float
    fsp_achievements: tuple[ConfirmedAchievement, ...] = ()

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
            fsp_achievements=card.fsp_achievements,
        )


@dataclass(frozen=True)
class ProfileForm:
    """Анкета, как её прислал кандидат: стек и интересные сферы — кодами справочника, ожидаемая
    зарплата — в рублях в месяц до вычета НДФЛ. Город обязателен, если подходит офис или гибрид.
    `hidden` — поля самоописания, скрытые из обезличенной карточки.
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
    hidden: frozenset[HideableField] = frozenset()

    def __post_init__(self) -> None:
        if self.city is None and set(self.work_formats) != {WorkFormat.remote}:
            raise CityRequired()
