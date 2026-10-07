"""Семейства в базе: текущие параметры, калибровка после ответа, пакетная переоценка, связка
шкалы и доля показов (mechanics.md, §6–§7). Формулы — в `calibration` и `adaptive`, здесь —
чтение и запись.
"""

import logging
from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assessment import bank
from app.assessment.adaptive import Exposure, Option
from app.assessment.calibration import (
    Link,
    Parameters,
    Response,
    elo_update,
    expert,
    fit_link,
    needs_review,
    refit,
)
from app.assessment.models import (
    FamilyCalibration,
    FamilyStatus,
    Presentation,
    ScaleLink,
    TestAttempt,
)
from app.config import Mechanics
from app.skills.irt import Normal

log = logging.getLogger(__name__)


def options(
    db: Session,
    attempt: TestAttempt,
    families: Sequence[bank.Family],
    mechanics: Mechanics,
) -> tuple[list[Option], Exposure]:
    """Кандидаты на следующее задание попытки с параметрами, долей показов и давностью показа
    кандидату. Показанные в этой попытке и выведенные из выдачи сюда не попадают."""
    shown_here = {p.family_code for p in attempt.presentations}
    params = current(db, [f for f in families if f.code not in shown_here], mechanics)
    window, shown = _exposure(db, attempt, mechanics.exposure_window_attempts)
    seen = _seen(db, attempt)
    result = [
        Option(
            code,
            bank.get_family(code).topic,
            p.discrimination,
            p.difficulty,
            shown=shown.get(code, 0),
            seen_at=seen.get(code),
        )
        for code, p in params.items()
    ]
    return result, Exposure.from_mechanics(window, mechanics)


def current(
    db: Session, families: Sequence[bank.Family], mechanics: Mechanics
) -> dict[str, Parameters]:
    """Текущие параметры семейств в выдаче; до первого ответа — экспертные."""
    rows = _rows(db, [f.code for f in families])
    result = {}
    for family in families:
        row = rows.get(family.code)
        if row is None:
            result[family.code] = expert(family.grade, mechanics)
        elif row.status == FamilyStatus.active:
            result[family.code] = Parameters(row.discrimination, row.difficulty)
    return result


def learn(db: Session, presentation: Presentation, mechanics: Mechanics) -> None:
    """Эло после ответа: сложность семейства сдвигается по неожиданности ответа (§7).

    Строка семейства блокируется до конца транзакции: два ответа на одно семейство не
    затирают шаги друг друга. У якорного и у переоценённого семейства растёт только счётчик
    ответов: после пакетной переоценки текущие параметры — опорные.
    """
    family = bank.get_family(presentation.family_code)
    row = _locked(db, family, mechanics)
    if not family.anchor and row.refitted_at is None:
        assert presentation.correct is not None
        before = Normal(presentation.topic_theta_before, presentation.topic_theta_sd_before)
        link = links(db, presentation.attempt.specialization_code)[0]
        updated = elo_update(
            Parameters(row.discrimination, row.difficulty),
            Response(link.apply(before), presentation.correct),
            row.responses,
            mechanics,
        )
        row.difficulty = updated.difficulty
    row.responses += 1


def links(db: Session, specialization: str) -> tuple[Link, Link]:
    """Связки шкалы специализации: по оценкам до ответа (для Эло) и без ответа (для переоценки)."""
    row = db.get(ScaleLink, specialization)
    if row is None:
        return Link(), Link()
    return Link(row.before_shift, row.before_scale), Link(row.rest_shift, row.rest_scale)


def relink(db: Session, specialization: str, mechanics: Mechanics, now: datetime) -> None:
    """Пересчёт связок шкалы по ответам на якорные семейства из последних
    `calibration_link_window_attempts` попыток по специализации (§7)."""
    anchors = [f.code for f in bank.BANK if f.anchor]
    recent = (
        select(TestAttempt.id)
        .where(TestAttempt.specialization_code == specialization)
        .order_by(TestAttempt.started_at.desc())
        .limit(mechanics.calibration_link_window_attempts)
    )
    rows = db.execute(
        select(
            Presentation.discrimination,
            Presentation.difficulty,
            Presentation.correct,
            Presentation.topic_theta_before,
            Presentation.topic_theta_sd_before,
            Presentation.topic_theta_rest,
            Presentation.topic_theta_rest_sd,
        ).where(
            Presentation.family_code.in_(anchors),
            Presentation.attempt_id.in_(recent),
            Presentation.correct.is_not(None),
        )
    ).all()
    before = [
        (Parameters(a, b), Response(Normal(m, s), c))
        for a, b, c, m, s, _, _ in rows
        if c is not None
    ]
    rest = [
        (Parameters(a, b), Response(Normal(m, s), c))
        for a, b, c, _, _, m, s in rows
        if c is not None and m is not None and s is not None
    ]
    before_link, rest_link = fit_link(before, mechanics), fit_link(rest, mechanics)
    values = {
        "before_shift": before_link.shift,
        "before_scale": before_link.scale,
        "rest_shift": rest_link.shift,
        "rest_scale": rest_link.scale,
        "updated_at": now,
    }
    db.execute(
        pg_insert(ScaleLink)
        .values(specialization_code=specialization, **values)
        .on_conflict_do_update(index_elements=["specialization_code"], set_=values)
    )
    db.commit()


def refit_due(
    db: Session, codes: Iterable[str], specialization: str, mechanics: Mechanics, now: datetime
) -> None:
    """Пакетная переоценка семейств, набравших `calibration_refit_min_responses` ответов с
    итоговыми оценками кандидатов. Каждое семейство — своя транзакция: блокировки не копятся.

    Уровни кандидатов переводятся связкой шкалы. Результат — новые текущие и опорные параметры.
    Опорная сложность легче экспертной больше допустимого — семейство уходит из выдачи до ручной
    проверки.
    """
    link = links(db, specialization)[1]
    for code in sorted(set(codes)):
        family = bank.get_family(code)
        if family.anchor or _ready(db, code) < mechanics.calibration_refit_min_responses:
            continue
        row = _locked(db, family, mechanics)
        if row.refitted_at is not None:
            db.commit()
            continue
        answers = db.execute(
            select(
                Presentation.topic_theta_rest,
                Presentation.topic_theta_rest_sd,
                Presentation.correct,
            ).where(
                Presentation.family_code == code,
                Presentation.topic_theta_rest.is_not(None),
            )
        ).all()
        start = expert(family.grade, mechanics)
        responses = [
            Response(link.apply(Normal(m, s)), c)
            for m, s, c in answers
            if m is not None and s is not None and c is not None
        ]
        fitted = refit(responses, start, mechanics)
        row.discrimination = row.reference_discrimination = fitted.discrimination
        row.difficulty = row.reference_difficulty = fitted.difficulty
        row.refitted_at = now
        if needs_review(fitted, start, mechanics):
            row.status = FamilyStatus.review
            log.warning(
                "Семейство %s легче экспертной оценки: b = %.2f при экспертной %.2f — выведено "
                "из выдачи до ручной проверки",
                code,
                fitted.difficulty,
                start.difficulty,
            )
        db.commit()


def _ready(db: Session, code: str) -> int:
    """Ответов на семейство с итоговой оценкой кандидата — из остановленных попыток."""
    count = db.scalar(
        select(func.count()).where(
            Presentation.family_code == code, Presentation.topic_theta_rest.is_not(None)
        )
    )
    return count or 0


def _locked(db: Session, family: bank.Family, mechanics: Mechanics) -> FamilyCalibration:
    start = expert(family.grade, mechanics)
    db.execute(
        pg_insert(FamilyCalibration)
        .values(
            family_code=family.code,
            discrimination=start.discrimination,
            difficulty=start.difficulty,
            responses=0,
            status=FamilyStatus.active,
        )
        .on_conflict_do_nothing(index_elements=["family_code"])
    )
    return db.scalars(
        select(FamilyCalibration)
        .where(FamilyCalibration.family_code == family.code)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def _rows(db: Session, codes: Sequence[str]) -> dict[str, FamilyCalibration]:
    rows = db.scalars(select(FamilyCalibration).where(FamilyCalibration.family_code.in_(codes)))
    return {row.family_code: row for row in rows}


def _exposure(db: Session, attempt: TestAttempt, window: int) -> tuple[int, dict[str, int]]:
    """Окно показов: последние `window − 1` попыток по специализации до текущей — вместе с ней
    окно из `window`. Возвращает число попыток в окне и в скольких из них показано семейство."""
    recent = (
        select(TestAttempt.id)
        .where(
            TestAttempt.specialization_code == attempt.specialization_code,
            TestAttempt.id != attempt.id,
        )
        .order_by(TestAttempt.started_at.desc())
        .limit(window - 1)
        .subquery()
    )
    attempts = db.scalar(select(func.count()).select_from(recent)) or 0
    shown = db.execute(
        select(Presentation.family_code, func.count(distinct(Presentation.attempt_id)))
        .where(Presentation.attempt_id.in_(select(recent.c.id)))
        .group_by(Presentation.family_code)
    ).all()
    return attempts, {code: count for code, count in shown}


def _seen(db: Session, attempt: TestAttempt) -> dict[str, datetime]:
    """Семейства, которые кандидат видел в прошлых попытках, — с началом последней из них."""
    rows = db.execute(
        select(Presentation.family_code, func.max(TestAttempt.started_at))
        .join(TestAttempt)
        .where(TestAttempt.user_id == attempt.user_id, TestAttempt.id != attempt.id)
        .group_by(Presentation.family_code)
    ).all()
    return {code: seen_at for code, seen_at in rows}
