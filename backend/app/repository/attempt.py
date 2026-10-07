"""Попытки теста из Postgres — реализация порта `AttemptReader`.

ORM попытки пока живёт в `app.assessment.models`; сюда он переедет вместе с репозиториями.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.models import Presentation, TestAttempt
from app.domain.attempt import AnsweredPresentation


def answered_of(row: Presentation) -> AnsweredPresentation:
    if row.correct is None or row.answered_at is None:
        raise ValueError("наблюдение — только отвеченное предъявление")
    return AnsweredPresentation(
        family_code=row.family_code,
        topic=row.topic_code,
        params=dict(row.params),
        discrimination=row.discrimination,
        difficulty=row.difficulty,
        correct=row.correct,
        answered_at=row.answered_at,
    )


class SqlAttemptReader:
    """Читает в сессии единицы работы: записанное в ней до `flush` видно, коммитов здесь нет."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def answered(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> Sequence[AnsweredPresentation]:
        rows = self.session.scalars(
            select(Presentation)
            .join(TestAttempt)
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.specialization_code == specialization_code,
                Presentation.answered_at.is_not(None),
            )
            .order_by(TestAttempt.number, Presentation.position)
        )
        return [answered_of(row) for row in rows]
