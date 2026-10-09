"""Профиль кандидата — самоописание по форме: кто он, стек, опыт и ожидания (mechanics.md, §11).

Самоописание — низший уровень доверия: категорию определяет только тест, в скор входит один
стек с потолком вклада. Ожидания — вход модели принятия приглашения (§13): зарплата, формат,
город, переезд и интересные сферы бизнеса.

Кому что видно: ФИО, контакты и свободный текст — «о себе», роли, софт-скиллы, карточку опыта —
работодатель получает только после раскрытия: принятого приглашения или отклика (§14). В
свободный текст можно вписать имя или контакт. Ожидаемая зарплата работодателю не показывается
никогда. Фото, возраст и вуз не собираются: это защищённые признаки (§17), обезличивать их не
придётся.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, CheckConstraint, Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.candidate import HideableField
from app.repository.database import Base
from app.repository.orm.catalog import Industry, Technology

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

candidate_industries = Table(
    "candidate_industries",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("industry_code", ForeignKey("industries.code"), primary_key=True),
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
        CheckConstraint(
            f"hidden_fields <@ ARRAY[{', '.join(repr(f.value) for f in HideableField)}]::varchar[]",
            name="hidden_fields",
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
    job_roles: Mapped[list[str]] = mapped_column(ARRAY(String(100)))
    soft_skills: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    # Карточка опыта со слов кандидата: записи `{place, role, start, end, stack, summary}`,
    # месяцы — `ГГГГ-ММ`, `end` — `null` «по сейчас», стек — коды технологий. Записи читаются
    # только целиком с профилем, поэтому не отдельной таблицей; годы по технологиям не хранятся.
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")

    # Видны в обезличенной карточке: структурные поля.
    experience_years: Mapped[int]
    # Допустимые форматы работы — значения `WorkFormat`.
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    city: Mapped[str | None] = mapped_column(String(100))
    relocation: Mapped[bool]
    # Поля самоописания, скрытые кандидатом из обезличенной карточки, — значения
    # `HideableField`; пусто — видно всё.
    hidden_fields: Mapped[list[str]] = mapped_column(ARRAY(String(32)), server_default="{}")

    # Ожидаемая зарплата «от», рубли в месяц до вычета НДФЛ. Работодателю не показывается.
    salary_from: Mapped[int]

    updated_at: Mapped[datetime]

    stack: Mapped[list[Technology]] = relationship(
        secondary=candidate_technologies, order_by="Technology.name"
    )
    # Интересные сферы бизнеса — необязательны; совпадение со сферой компании — признак
    # модели принятия.
    industries: Mapped[list[Industry]] = relationship(
        secondary=candidate_industries, order_by="Industry.position"
    )
