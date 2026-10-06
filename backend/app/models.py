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
from app.identity.models import EmailVerificationToken, User
from app.skills.models import SkillProfile, SkillProfileTopic

__all__ = [
    "CandidateCategory",
    "EmailVerificationToken",
    "Grade",
    "Industry",
    "Presentation",
    "SkillProfile",
    "SkillProfileTopic",
    "Specialization",
    "Survey",
    "Technology",
    "TestAttempt",
    "Topic",
    "User",
    "technology_topics",
]
