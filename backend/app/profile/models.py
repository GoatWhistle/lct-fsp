"""Профиль кандидата — самоописание по форме: кто он, стек, опыт и ожидания (mechanics.md, §11).

Самоописание — низший уровень доверия: категорию определяет только тест, в скор входит один
стек с потолком вклада. Ожидания — вход модели принятия приглашения (§13).

Кому что видно: ФИО, контакты и «о себе» работодатель получает только после раскрытия —
принятого приглашения или отклика (§14); ожидаемая зарплата ему не показывается никогда.
Фото, возраст и вуз не собираются: это защищённые признаки (§17), обезличивать их не придётся.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.assessment.models import Technology
from app.db import Base, utcnow

candidate_technologies = Table(
    "candidate_technologies",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("technology_code", ForeignKey("technologies.code"), primary_key=True),
)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("salary_from > 0", name="salary_from_positive"),
        CheckConstraint("experience_years >= 0", name="experience_years_not_negative"),
        CheckConstraint(
            "cardinality(work_formats) > 0 "
            "AND work_formats <@ ARRAY['office', 'hybrid', 'remote']::varchar[]",
            name="work_formats",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Раскрываются работодателю после принятия приглашения или отклика.
    full_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    # Имя пользователя без «@».
    telegram: Mapped[str | None] = mapped_column(String(32))
    about: Mapped[str] = mapped_column(String(3000))

    # Видны в обезличенной карточке.
    job_roles: Mapped[list[str]] = mapped_column(ARRAY(String(100)))
    experience_years: Mapped[int]
    soft_skills: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    # Допустимые форматы работы — значения `WorkFormat`.
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    city: Mapped[str | None] = mapped_column(String(100))
    relocation: Mapped[bool]

    # Ожидаемая зарплата «от», рубли в месяц. Работодателю не показывается.
    salary_from: Mapped[int]

    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    stack: Mapped[list[Technology]] = relationship(
        secondary=candidate_technologies, order_by="Technology.name"
    )
