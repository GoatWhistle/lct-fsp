"""Путь кандидата к категории: опрос, попытки теста, предъявления, калибровка семейств и
категория."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.attempt import AttemptOutcome
from app.repository.database import Base
from app.repository.orm.catalog import Grade, Specialization


class Survey(Base):
    """Опрос — первый шаг пути: направление, то есть специализация («отрасль» в ТЗ). Последний
    опрос кандидата — текущий."""

    __tablename__ = "surveys"
    __table_args__ = (UniqueConstraint("user_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Номер опроса кандидата с 1. Порядок — по нему: часы сервера при синхронизации отходят назад.
    number: Mapped[int]
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    created_at: Mapped[datetime]

    specialization: Mapped[Specialization] = relationship()


class TestAttempt(Base):
    """Попытка — прохождение теста на один грейд. Дотест каскада продолжает оценку попытки,
    на которую ссылается `continues_attempt_id`: вместе они — одно определение категории."""

    __tablename__ = "test_attempts"
    __table_args__ = (UniqueConstraint("user_id", "number"),)
    __test__ = False  # имя начинается с Test — pytest не должен собирать класс как тест

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Номер попытки кандидата с 1. Порядок — по нему, а не по часам, как у опросов.
    number: Mapped[int]
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"))
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    continues_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"), unique=True
    )
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]

    # Оценка теста на момент остановки: общий уровень θ̄ и его погрешность.
    overall_theta: Mapped[float | None]
    overall_theta_sd: Mapped[float | None]
    outcome: Mapped[AttemptOutcome | None] = mapped_column(
        Enum(
            AttemptOutcome,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="attempt_outcome",
        )
    )
    # Присвоенный или предложенный для дотеста грейд — по `outcome`.
    outcome_grade_code: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    retest_after: Mapped[datetime | None]

    presentations: Mapped[list["Presentation"]] = relationship(
        order_by="Presentation.position", back_populates="attempt"
    )


class Presentation(Base):
    """Предъявление экземпляра семейства: всё, на чём стоят калибровка, защита и валидация.

    Параметры семейства (a, b) записаны на момент показа: калибровка их потом сдвигает, а оценка
    попытки должна пересчитываться в то же значение. Эталон не хранится — он вычисляется из
    семейства и seed.
    """

    __tablename__ = "presentations"
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE")
    )
    position: Mapped[int]
    family_code: Mapped[str] = mapped_column(String(128), index=True)
    topic_code: Mapped[str] = mapped_column(ForeignKey("topics.code"))
    seed: Mapped[int] = mapped_column(BigInteger)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    discrimination: Mapped[float]
    difficulty: Mapped[float]
    # Оценка теста по теме до ответа (μ_t, σ_t).
    topic_theta_before: Mapped[float]
    topic_theta_sd_before: Mapped[float]
    # Время — по часам сервера: клиентские подделываются.
    shown_at: Mapped[datetime]
    answered_at: Mapped[datetime | None]
    response: Mapped[str | None] = mapped_column(String(500))
    correct: Mapped[bool | None]
    response_time_ms: Mapped[int | None]
    # Итоговая оценка теста по теме без этого ответа — пишется при остановке попытки. По ней
    # переоценивают параметры семейства: ответ не сравнивается с оценкой, в которую вошёл сам.
    topic_theta_rest: Mapped[float | None]
    topic_theta_rest_sd: Mapped[float | None]

    attempt: Mapped[TestAttempt] = relationship(back_populates="presentations")


class FamilyStatus(enum.StrEnum):
    # В выдаче.
    active = "active"
    # Опорная сложность оказалась легче экспертной больше допустимого: утечка во время разогрева
    # или ошибка эксперта. Из выдачи до ручной проверки (mechanics.md, §7).
    review = "review"


class FamilyCalibration(Base):
    """Текущие параметры семейства и их история калибровки (mechanics.md, §7).

    Строки нет, пока на семейство не ответили: до первого ответа параметры — экспертные из
    банка. У якорных семейств параметры заморожены, растёт только счётчик ответов.
    """

    __tablename__ = "family_calibrations"

    family_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    discrimination: Mapped[float]
    difficulty: Mapped[float]
    # Ответов на семейство — от него шаг Эло K_n.
    responses: Mapped[int] = mapped_column(default=0)
    # Опорные параметры — результат первой пакетной переоценки; от них меряется дрейф (§8).
    reference_discrimination: Mapped[float | None]
    reference_difficulty: Mapped[float | None]
    refitted_at: Mapped[datetime | None]
    status: Mapped[FamilyStatus] = mapped_column(
        Enum(
            FamilyStatus,
            native_enum=False,
            create_constraint=True,
            length=16,
            name="family_status",
        ),
        default=FamilyStatus.active,
    )


class ScaleLink(Base):
    """Связка шкалы специализации по якорным семействам (mechanics.md, §7): уровень, с которым
    калибровка сравнивает ответ, — shift + scale · μ. Пересчитывается при остановке попытки.

    Строки нет, пока попыток по специализации не было: связка тождественная.
    """

    __tablename__ = "scale_links"

    specialization_code: Mapped[str] = mapped_column(
        ForeignKey("specializations.code", ondelete="CASCADE"), primary_key=True
    )
    # По оценкам темы до ответа — для шага Эло.
    before_shift: Mapped[float]
    before_scale: Mapped[float]
    # По итоговым оценкам темы без ответа — для пакетной переоценки.
    rest_shift: Mapped[float]
    rest_scale: Mapped[float]
    updated_at: Mapped[datetime]


class CandidateCategory(Base):
    """Категория кандидата — специализация × грейд. Строку пишет только присвоение по тесту:
    выдача работодателя строится по этой таблице, кандидата без строки в ней нет."""

    __tablename__ = "candidate_categories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    specialization_code: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade_code: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_attempts.id"))
    assigned_at: Mapped[datetime]

    specialization: Mapped[Specialization] = relationship()
    grade: Mapped[Grade] = relationship()
