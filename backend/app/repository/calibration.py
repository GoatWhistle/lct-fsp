"""Калибровка в Postgres — реализация порта `CalibrationRepository`: состояния семейств и
связки шкалы. Изменения не фиксируются — это делает единица работы; блокировки строк держатся
до её конца."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.calibration import AnchorAnswer, CalibratedFamily, Link, Parameters, Response
from app.domain.skill import Normal
from app.repository.orm.attempt import FamilyCalibration, FamilyStatus, ScaleLink, TestAttempt
from app.repository.orm.attempt import Presentation as PresentationRow


def _state_of(row: FamilyCalibration) -> CalibratedFamily:
    reference = None
    if row.reference_discrimination is not None and row.reference_difficulty is not None:
        reference = Parameters(row.reference_discrimination, row.reference_difficulty)
    return CalibratedFamily(
        family_code=row.family_code,
        discrimination=row.discrimination,
        difficulty=row.difficulty,
        responses=row.responses,
        reference=reference,
        refitted_at=row.refitted_at,
        in_rotation=row.status == FamilyStatus.active,
    )


class SqlCalibrationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def parameters(self, codes: Collection[str]) -> dict[str, CalibratedFamily]:
        rows = self.session.scalars(
            select(FamilyCalibration).where(FamilyCalibration.family_code.in_(codes))
        )
        return {row.family_code: _state_of(row) for row in rows}

    def locked(self, code: str, start: Parameters) -> CalibratedFamily:
        self.session.execute(
            pg_insert(FamilyCalibration)
            .values(
                family_code=code,
                discrimination=start.discrimination,
                difficulty=start.difficulty,
                responses=0,
                status=FamilyStatus.active,
            )
            .on_conflict_do_nothing(index_elements=["family_code"])
        )
        row = self.session.scalars(
            select(FamilyCalibration)
            .where(FamilyCalibration.family_code == code)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        return _state_of(row)

    def save(self, family: CalibratedFamily) -> None:
        row = self.session.get_one(FamilyCalibration, family.family_code)
        row.discrimination = family.discrimination
        row.difficulty = family.difficulty
        row.responses = family.responses
        if family.reference is not None:
            row.reference_discrimination = family.reference.discrimination
            row.reference_difficulty = family.reference.difficulty
        row.refitted_at = family.refitted_at
        row.status = FamilyStatus.active if family.in_rotation else FamilyStatus.review
        self.session.flush()

    def links(self, specialization: str) -> tuple[Link, Link]:
        row = self.session.get(ScaleLink, specialization)
        if row is None:
            return Link(), Link()
        return Link(row.before_shift, row.before_scale), Link(row.rest_shift, row.rest_scale)

    def save_links(self, specialization: str, before: Link, rest: Link, now: datetime) -> None:
        values = {
            "before_shift": before.shift,
            "before_scale": before.scale,
            "rest_shift": rest.shift,
            "rest_scale": rest.scale,
            "updated_at": now,
        }
        self.session.execute(
            pg_insert(ScaleLink)
            .values(specialization_code=specialization, **values)
            .on_conflict_do_update(index_elements=["specialization_code"], set_=values)
        )
        # Строка могла быть прочитана в этой же транзакции (шаг Эло): без сброса `links` после
        # пересчёта вернул бы её из identity map со старыми значениями.
        cached = self.session.get(ScaleLink, specialization)
        if cached is not None:
            self.session.expire(cached)

    def anchor_answers(
        self, specialization: str, anchors: Collection[str], window_attempts: int
    ) -> list[AnchorAnswer]:
        recent = (
            select(TestAttempt.id)
            .where(
                TestAttempt.specialization_code == specialization,
                TestAttempt.finished_at.is_not(None),
            )
            .order_by(TestAttempt.finished_at.desc())
            .limit(window_attempts)
        )
        rows = self.session.execute(
            select(
                PresentationRow.family_code,
                PresentationRow.discrimination,
                PresentationRow.difficulty,
                PresentationRow.correct,
                PresentationRow.topic_theta_before,
                PresentationRow.topic_theta_sd_before,
                PresentationRow.topic_theta_rest,
                PresentationRow.topic_theta_rest_sd,
            ).where(
                PresentationRow.family_code.in_(anchors),
                PresentationRow.attempt_id.in_(recent),
                PresentationRow.correct.is_not(None),
            )
        ).all()
        return [
            AnchorAnswer(
                family_code=code,
                params=Parameters(a, b),
                before=Response(Normal(before_mean, before_sd), correct),
                rest=(
                    Response(Normal(rest_mean, rest_sd), correct)
                    if rest_mean is not None and rest_sd is not None
                    else None
                ),
            )
            for code, a, b, correct, before_mean, before_sd, rest_mean, rest_sd in rows
            if correct is not None
        ]

    def rest_answers(self, code: str) -> list[Response]:
        rows = self.session.execute(
            select(
                PresentationRow.topic_theta_rest,
                PresentationRow.topic_theta_rest_sd,
                PresentationRow.correct,
            ).where(
                PresentationRow.family_code == code,
                PresentationRow.topic_theta_rest.is_not(None),
            )
        ).all()
        return [
            Response(Normal(mean, sd), correct)
            for mean, sd, correct in rows
            if mean is not None and sd is not None and correct is not None
        ]

    def ready_responses(self, code: str) -> int:
        count = self.session.scalar(
            select(func.count()).where(
                PresentationRow.family_code == code,
                PresentationRow.topic_theta_rest.is_not(None),
            )
        )
        return count or 0
