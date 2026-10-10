"""Планы тестов по вакансии в Postgres — реализация порта `VacancyTestRepository`. Темы плана
лежат списком словарей; собирает и читает их только этот модуль. Изменения не фиксируются — это
делает единица работы."""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import CatalogRef
from app.domain.importance import TopicImportance
from app.domain.vacancy_test import PlannedTopic, VacancyTest, VacancyTestPlan
from app.repository import orm as models


def _topic_row(topic: PlannedTopic) -> dict[str, Any]:
    return {
        "code": topic.topic.code,
        "name": topic.topic.name,
        "importance": topic.importance.value,
        "weight": topic.weight,
        "items": topic.items,
    }


def _test_of(row: models.VacancyTest) -> VacancyTest:
    return VacancyTest(
        id=row.id,
        invitation_id=row.invitation_id,
        need_title=row.need_title,
        plan=VacancyTestPlan(
            specialization=CatalogRef(row.specialization_code, row.specialization.name),
            grade=CatalogRef(row.grade_code, row.grade.name),
            requirement=row.requirement,
            topics=tuple(
                PlannedTopic(
                    CatalogRef(t["code"], t["name"]),
                    TopicImportance(t["importance"]),
                    t["weight"],
                    t["items"],
                )
                for t in row.topics
            ),
        ),
        created_at=row.created_at,
    )


class SqlVacancyTests:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, invitation_id: uuid.UUID, need_title: str, plan: VacancyTestPlan, now: datetime
    ) -> VacancyTest:
        row = models.VacancyTest(
            invitation_id=invitation_id,
            need_title=need_title,
            specialization_code=plan.specialization.code,
            grade_code=plan.grade.code,
            requirement=plan.requirement,
            topics=[_topic_row(t) for t in plan.topics],
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _test_of(row)

    def get(self, test_id: uuid.UUID) -> VacancyTest:
        return _test_of(self._session.get_one(models.VacancyTest, test_id))

    def by_invitations(self, invitation_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, VacancyTest]:
        if not invitation_ids:
            return {}
        rows = self._session.scalars(
            select(models.VacancyTest).where(models.VacancyTest.invitation_id.in_(invitation_ids))
        )
        return {row.invitation_id: _test_of(row) for row in rows}
