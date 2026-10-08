"""Снимок достижений ФСП кандидата — последние полученные из реестра (mechanics.md, §11).

Профиль и подборка читают только снимок: недоступный реестр их не ломает. Снимок заменяется
целиком при каждом ответе реестра и удаляется при отвязке ФСП ID.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.fsp import FspResult
from app.repository.database import Base


class FspSnapshot(Base):
    __tablename__ = "fsp_snapshots"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    fetched_at: Mapped[datetime]

    achievements: Mapped[list["FspAchievement"]] = relationship(
        order_by="FspAchievement.position", cascade="all, delete-orphan"
    )


class FspAchievement(Base):
    """Достижение как его отдал реестр. Дисциплина и роль — кодами без внешних ключей: снимок
    хранится как получен, неизвестный код — только факт в профиле."""

    __tablename__ = "fsp_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fsp_snapshots.user_id", ondelete="CASCADE"), primary_key=True
    )
    # Порядок в ответе реестра.
    position: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String(255))
    # Дата мероприятия — по ней достижение встаёт в порядок сигналов профиля.
    date: Mapped[date]
    discipline_code: Mapped[str] = mapped_column(String(32))
    place: Mapped[int | None]
    result: Mapped[FspResult] = mapped_column(
        Enum(FspResult, native_enum=False, create_constraint=True, length=16, name="fsp_result")
    )
    team_role: Mapped[str | None] = mapped_column(String(32))
