"""Проекция кандидата — то, что из профиля кандидата, категории и профиля навыков показывается
читателю (mechanics.md, §11, §14).

Проекцию собирает сценарий: он решает, что раскрыть. Рендер и controller показывают её как
есть. Части проекции общие для PDF-профиля и обезличенной карточки: карточка — те же
категория, профиль навыков и самоописание, только без раскрываемого.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from app.domain.catalog import CatalogRef
from app.domain.skill import LevelBand, Normal, level_band
from app.domain.work import WorkFormat


@dataclass(frozen=True)
class Level:
    """Уровень θ с погрешностью и словами — полосой грейдов по правилу уверенности."""

    theta: float
    theta_sd: float
    band: LevelBand

    @classmethod
    def of(cls, level: Normal, thresholds: Mapping[str, float], confidence: float) -> Self:
        return cls(level.mean, level.sd, level_band(level, thresholds, confidence))


@dataclass(frozen=True)
class TopicLevel:
    topic: CatalogRef
    level: Level


@dataclass(frozen=True)
class SkillProfile:
    """Профиль навыков: общий уровень и уровни по темам в порядке тем справочника."""

    overall: Level
    topics: tuple[TopicLevel, ...]


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
class ProfileSheet:
    """Всё, что входит в PDF-профиль. Ожидаемой зарплаты нет: файл может оказаться у
    работодателя (§13).

    Профиль навыков — только вместе с категорией и по её специализации. `grade_confidence` —
    порог уверенности для подписи к уровням словами.
    """

    disclosed: Disclosed
    self_reported: SelfReported
    category: Category | None
    skill_profile: SkillProfile | None
    grade_confidence: float
