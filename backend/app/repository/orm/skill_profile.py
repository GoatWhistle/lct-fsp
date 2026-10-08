"""Профиль навыков — уровень и погрешность по каждой теме специализации из всех сигналов
(mechanics.md, §11). Хранится, чтобы подбору не пересчитывать модель на каждого кандидата;
пересчитывается из наблюдений при каждом новом сигнале."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repository.database import Base
from app.repository.orm.catalog import Topic


class SkillProfile(Base):
    __tablename__ = "skill_profiles"
    __table_args__ = (UniqueConstraint("user_id", "specialization_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    # Общий уровень θ̄ — не выводится из тем по отдельности: нужна совместная погрешность.
    overall_theta: Mapped[float]
    overall_theta_sd: Mapped[float]
    observations: Mapped[int]
    last_signal_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]

    topics: Mapped[list["SkillProfileTopic"]] = relationship(cascade="all, delete-orphan")


class SkillProfileTopic(Base):
    __tablename__ = "skill_profile_topics"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_code: Mapped[str] = mapped_column(ForeignKey("topics.code"), primary_key=True)
    theta: Mapped[float]
    theta_sd: Mapped[float]
    # В уровень вошли ответы на регулярные задания — источник уверенности в объяснении подборки.
    regular_task: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Уровни доверия, из которых есть наблюдения по теме (`SignalSource`): `fsp` — «подтверждено
    # ФСП» в объяснении подборки.
    sources: Mapped[list[str]] = mapped_column(ARRAY(String(16)), server_default="{}")

    topic: Mapped[Topic] = relationship(lazy="joined")
