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
    FspDiscipline,
    Grade,
    Industry,
    Specialization,
    Technology,
    Topic,
    fsp_discipline_topics,
    technology_topics,
)
from app.repository.orm.company import Company, CompanyDomainVerification
from app.repository.orm.fsp import FspAchievement, FspSnapshot
from app.repository.orm.invitation import Invitation, InvitationMessage, VacancyTest
from app.repository.orm.need import (
    Need,
    NeedTopicImportance,
    Selection,
    SelectionEntry,
    need_technologies,
    selection_shortlist,
)
from app.repository.orm.regular_task import RegularTask, RegularTaskAnswer, RegularTaskTopic
from app.repository.orm.skill_profile import SkillProfile, SkillProfileTopic
from app.repository.orm.vacancy import Application, Vacancy

__all__ = [
    "Application",
    "CandidateCategory",
    "CandidateProfile",
    "CategoryChange",
    "Company",
    "CompanyDomainVerification",
    "EmailVerificationToken",
    "FamilyCalibration",
    "FamilyStatus",
    "FspAchievement",
    "FspDiscipline",
    "FspSnapshot",
    "Grade",
    "Industry",
    "Invitation",
    "InvitationMessage",
    "Need",
    "NeedTopicImportance",
    "Presentation",
    "RegularTask",
    "RegularTaskAnswer",
    "RegularTaskTopic",
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
    "Vacancy",
    "VacancyTest",
    "candidate_industries",
    "candidate_technologies",
    "fsp_discipline_topics",
    "need_technologies",
    "selection_shortlist",
    "technology_topics",
]
