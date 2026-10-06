"""Все модели в одном месте — для миграций. Новый модуль с таблицами добавляет импорт сюда."""

from app.assessment.models import (
    CandidateCategory,
    Grade,
    Industry,
    Presentation,
    Specialization,
    Survey,
    Technology,
    TestAttempt,
    Topic,
    technology_topics,
)
from app.company.models import Company
from app.identity.models import EmailVerificationToken, User
from app.matching.models import Need, NeedTopicImportance, need_technologies
from app.skills.models import SkillProfile, SkillProfileTopic

__all__ = [
    "CandidateCategory",
    "Company",
    "EmailVerificationToken",
    "Grade",
    "Industry",
    "Need",
    "NeedTopicImportance",
    "Presentation",
    "SkillProfile",
    "SkillProfileTopic",
    "Specialization",
    "Survey",
    "Technology",
    "TestAttempt",
    "Topic",
    "User",
    "need_technologies",
    "technology_topics",
]
