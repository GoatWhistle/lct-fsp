"""Все модели в одном месте — для миграций. Новый модуль с таблицами добавляет импорт сюда."""

from app.assessment.models import Grade, Specialization, Technology, Topic, technology_topics
from app.identity.models import EmailVerificationToken, User

__all__ = [
    "EmailVerificationToken",
    "Grade",
    "Specialization",
    "Technology",
    "Topic",
    "User",
    "technology_topics",
]
