"""ORM-модели всех таблиц — только для репозиториев и миграций. Импорт пакета регистрирует все
таблицы в `Base.metadata`: новый модуль с таблицами добавляет импорт сюда."""

from app.repository.orm.account import EmailVerificationToken, User
from app.repository.orm.attempt import (
    CandidateCategory,
    CategoryChange,
    FamilyCalibration,
    FamilyStatus,
    Presentation,
    ScaleLink,
    Survey,
    TestAttempt,
)
from app.repository.orm.candidate import (
    CandidateProfile,
    candidate_industries,
    candidate_technologies,
)
from app.repository.orm.catalog import (
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
    technology_topics,
)
from app.repository.orm.company import Company
from app.repository.orm.need import (
    Need,
    NeedTopicImportance,
    Selection,
    SelectionEntry,
    need_technologies,
)
from app.repository.orm.skill_profile import SkillProfile, SkillProfileTopic

__all__ = [
    "CandidateCategory",
    "CandidateProfile",
    "CategoryChange",
    "Company",
    "EmailVerificationToken",
    "FamilyCalibration",
    "FamilyStatus",
    "Grade",
    "Industry",
    "Need",
    "NeedTopicImportance",
    "Presentation",
    "ScaleLink",
    "Selection",
    "SelectionEntry",
    "SkillProfile",
    "SkillProfileTopic",
    "Specialization",
    "Survey",
    "Technology",
    "TestAttempt",
    "Topic",
    "User",
    "candidate_industries",
    "candidate_technologies",
    "need_technologies",
    "technology_topics",
]
