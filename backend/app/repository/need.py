"""Потребности работодателя в Postgres — реализация портов `NeedReader` и `NeedRepository`.
Изменения не фиксируются — это делает единица работы."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.errors import NeedNotFound
from app.domain.need import NeedRecord, NeedTerms
from app.domain.selection import Need
from app.domain.work import SalaryRange
from app.repository.catalog import grade_of, specialization_of, technology_of
from app.repository.orm.catalog import Specialization, Technology
from app.repository.orm.company import Company
from app.repository.orm.need import Need as NeedRow
from app.repository.orm.need import NeedTopicImportance

_LOADED = (
    selectinload(NeedRow.specialization).selectinload(Specialization.topics),
    selectinload(NeedRow.grade),
    selectinload(NeedRow.stack).selectinload(Technology.topics),
    selectinload(NeedRow.edited_importance),
)


def _need_of(row: NeedRow) -> Need:
    return Need(
        id=row.id,
        title=row.title,
        specialization=specialization_of(row.specialization),
        grade=grade_of(row.grade),
        stack=tuple(technology_of(t) for t in row.stack),
        edited_importance={e.topic_code: e.importance for e in row.edited_importance},
        work_format=row.work_format,
        city=row.city,
        salary=SalaryRange.optional(row.salary_from, row.salary_to),
        updated_at=row.updated_at,
    )


def _record_of(row: NeedRow) -> NeedRecord:
    return NeedRecord(_need_of(row), row.team_description, row.created_at)


class SqlNeeds:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID, need_id: uuid.UUID) -> Need:
        return _need_of(self._row(user_id, need_id))

    def company_industry(self, user_id: uuid.UUID) -> str | None:
        return self._session.scalar(select(Company.industry_code).where(Company.user_id == user_id))

    def records(self, user_id: uuid.UUID) -> list[NeedRecord]:
        rows = self._session.scalars(
            select(NeedRow)
            .where(NeedRow.user_id == user_id)
            .options(*_LOADED)
            .order_by(NeedRow.created_at.desc())
        )
        return [_record_of(row) for row in rows]

    def record(self, user_id: uuid.UUID, need_id: uuid.UUID) -> NeedRecord:
        return _record_of(self._row(user_id, need_id))

    def ensure(self, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
        self._row(user_id, need_id)

    def add(self, user_id: uuid.UUID, terms: NeedTerms, now: datetime) -> uuid.UUID:
        row = NeedRow(user_id=user_id, created_at=now)
        self._fill(row, terms, now)
        self._session.add(row)
        self._written(row)
        return row.id

    def replace(
        self, user_id: uuid.UUID, need_id: uuid.UUID, terms: NeedTerms, now: datetime
    ) -> None:
        # Стек и правки важности лежат в своих таблицах: строка потребности может не измениться,
        # время правки ставится всё равно.
        row = self._row(user_id, need_id)
        self._fill(row, terms, now)
        self._written(row)

    def delete(self, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
        self._session.delete(self._row(user_id, need_id))
        self._session.flush()

    def _row(self, user_id: uuid.UUID, need_id: uuid.UUID) -> NeedRow:
        row = self._session.get(NeedRow, need_id)
        if row is None or row.user_id != user_id:
            raise NeedNotFound()
        return row

    def _written(self, row: NeedRow) -> None:
        """Запись уходит в базу, а связи строки читаются заново: справочники по новым кодам."""
        self._session.flush()
        self._session.expire(row)

    def _fill(self, row: NeedRow, terms: NeedTerms, now: datetime) -> None:
        row.title = terms.title
        row.team_description = terms.team_description
        row.specialization_code = terms.specialization.code
        row.grade_code = terms.grade.code
        row.work_format = terms.work_format
        row.city = terms.city
        row.salary_from = terms.salary.low if terms.salary else None
        row.salary_to = terms.salary.high if terms.salary else None
        # Стек проверен по справочнику в той же сессии: строки технологий уже в ней.
        row.stack = [self._session.get_one(Technology, t.code) for t in terms.stack]
        row.edited_importance = [
            NeedTopicImportance(topic_code=topic, importance=importance)
            for topic, importance in terms.edited_importance.items()
        ]
        row.updated_at = now
