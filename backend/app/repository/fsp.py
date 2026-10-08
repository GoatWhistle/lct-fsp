"""Снимки достижений ФСП и дисциплины в Postgres — реализация порта `FspRepository`. Изменения
не фиксируются — это делает единица работы."""

import uuid
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.catalog import CatalogRef, FspDiscipline
from app.domain.fsp import ConfirmedAchievement, FspAchievement, FspHistory, FspSnapshot
from app.repository.catalog import fsp_discipline_of
from app.repository.orm import catalog as catalog_orm
from app.repository.orm.account import User
from app.repository.orm.fsp import FspAchievement as AchievementRow
from app.repository.orm.fsp import FspSnapshot as SnapshotRow


class SqlFspRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def snapshot(self, user_id: uuid.UUID) -> FspSnapshot | None:
        row = self._session.get(SnapshotRow, user_id)
        if row is None:
            return None
        return FspSnapshot(tuple(_achievement(a) for a in row.achievements), row.fetched_at)

    def disciplines(self) -> dict[str, FspDiscipline]:
        rows = self._session.scalars(
            select(catalog_orm.FspDiscipline).options(
                selectinload(catalog_orm.FspDiscipline.topics)
            )
        )
        return {row.code: fsp_discipline_of(row) for row in rows}

    def history(self, user_id: uuid.UUID) -> FspHistory | None:
        return histories(self._session, [user_id]).get(user_id)

    def save_snapshot(
        self, user_id: uuid.UUID, achievements: Sequence[FspAchievement], now: datetime
    ) -> None:
        self.delete_snapshot(user_id)
        self._session.add(
            SnapshotRow(
                user_id=user_id,
                fetched_at=now,
                achievements=[
                    AchievementRow(
                        position=n,
                        event=a.event,
                        date=a.date,
                        discipline_code=a.discipline,
                        place=a.place,
                        result=a.result,
                        team_role=a.team_role,
                    )
                    for n, a in enumerate(achievements)
                ],
            )
        )
        self._session.flush()

    def delete_snapshot(self, user_id: uuid.UUID) -> None:
        row = self._session.get(SnapshotRow, user_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()


def histories(session: Session, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, FspHistory]:
    """Достижения кандидатов с привязанным ФСП ID — по запросу на часть, без запроса на
    кандидата. Привязан, но реестр ни разу не ответил — пустая история без даты снимка."""
    linked = list(
        session.scalars(select(User.id).where(User.id.in_(ids), User.fsp_id.is_not(None)))
    )
    snapshots = {
        row.user_id: row
        for row in session.scalars(
            select(SnapshotRow)
            .where(SnapshotRow.user_id.in_(linked))
            .options(selectinload(SnapshotRow.achievements))
        )
    }
    if not snapshots:
        return dict.fromkeys(linked, FspHistory((), None))
    disciplines = _names(session, catalog_orm.FspDiscipline)
    roles = _names(session, catalog_orm.Specialization)
    result = {}
    for user_id in linked:
        row = snapshots.get(user_id)
        result[user_id] = (
            FspHistory(
                tuple(_confirmed(a, disciplines, roles) for a in row.achievements), row.fetched_at
            )
            if row
            else FspHistory((), None)
        )
    return result


def _names(
    session: Session, table: type[catalog_orm.FspDiscipline] | type[catalog_orm.Specialization]
) -> dict[str, str]:
    return {code: name for code, name in session.execute(select(table.code, table.name))}


def _confirmed(
    row: AchievementRow, disciplines: Mapping[str, str], roles: Mapping[str, str]
) -> ConfirmedAchievement:
    """Достижение с названиями дисциплины и роли; неизвестный код — название он сам."""
    role, discipline = row.team_role, row.discipline_code
    return ConfirmedAchievement(
        event=row.event,
        date=row.date,
        discipline=CatalogRef(discipline, disciplines.get(discipline, discipline)),
        place=row.place,
        result=row.result,
        team_role=CatalogRef(role, roles.get(role, role)) if role else None,
    )


def _achievement(row: AchievementRow) -> FspAchievement:
    return FspAchievement(
        event=row.event,
        date=row.date,
        discipline=row.discipline_code,
        place=row.place,
        result=row.result,
        team_role=row.team_role,
    )
