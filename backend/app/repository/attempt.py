"""Попытки теста в Postgres — реализация портов `AttemptReader` и `AttemptRepository`.

Профиль навыков кандидата пишется здесь же: его пересчитывает путь кандидата. Изменения не
фиксируются — это делает единица работы.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app.domain import candidate
from app.domain.attempt import (
    AnsweredPresentation,
    Attempt,
    AttemptPurpose,
    CategoryChange,
    ChangeKind,
    PathState,
    Presentation,
    Survey,
)
from app.domain.catalog import CatalogRef, Topic
from app.domain.skill import Normal, SignalSource, SkillProfileLevels
from app.repository import orm as models
from app.repository.catalog import ref_of, topic_of
from app.repository.orm import SkillProfile, SkillProfileTopic, User


def answered_of(row: models.Presentation) -> AnsweredPresentation:
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


def _presentation_of(row: models.Presentation) -> Presentation:
    return Presentation(
        id=row.id,
        attempt_id=row.attempt_id,
        position=row.position,
        family_code=row.family_code,
        topic_code=row.topic_code,
        seed=row.seed,
        params=dict(row.params),
        discrimination=row.discrimination,
        difficulty=row.difficulty,
        topic_theta_before=row.topic_theta_before,
        topic_theta_sd_before=row.topic_theta_sd_before,
        shown_at=row.shown_at,
        answered_at=row.answered_at,
        response=row.response,
        correct=row.correct,
        response_time_ms=row.response_time_ms,
        topic_theta_rest=row.topic_theta_rest,
        topic_theta_rest_sd=row.topic_theta_rest_sd,
    )


def _attempt_of(row: models.TestAttempt, *, presentations: bool = True) -> Attempt:
    """`presentations=False` — без предъявлений: их отношение не загружается."""
    overall = None
    if row.overall_theta is not None and row.overall_theta_sd is not None:
        overall = Normal(row.overall_theta, row.overall_theta_sd)
    return Attempt(
        id=row.id,
        user_id=row.user_id,
        number=row.number,
        survey_id=row.survey_id,
        specialization_code=row.specialization_code,
        grade_code=row.grade_code,
        continues_attempt_id=row.continues_attempt_id,
        started_at=row.started_at,
        purpose=row.purpose,
        finished_at=row.finished_at,
        overall=overall,
        outcome=row.outcome,
        outcome_grade_code=row.outcome_grade_code,
        retest_after=row.retest_after,
        presentations=[_presentation_of(p) for p in row.presentations] if presentations else [],
    )


def _survey_of(row: models.Survey) -> Survey:
    return Survey(id=row.id, specialization=ref_of(row.specialization), created_at=row.created_at)


class SqlAttemptReader:
    """Читает в сессии единицы работы: записанное в ней до `flush` видно, коммитов здесь нет."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def answered(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> Sequence[AnsweredPresentation]:
        rows = self.session.scalars(
            select(models.Presentation)
            .join(models.TestAttempt)
            .where(
                models.TestAttempt.user_id == user_id,
                models.TestAttempt.specialization_code == specialization_code,
                models.Presentation.answered_at.is_not(None),
            )
            .order_by(models.TestAttempt.number, models.Presentation.position)
        )
        return [answered_of(row) for row in rows]


class SqlAttemptRepository(SqlAttemptReader):
    """Путь кандидата на запись. Уровни словами в профиле считаются здесь же, по порогам
    грейдов и порогу уверенности из `config/mechanics.yaml`: их передаёт сборка."""

    def __init__(
        self, session: Session, grade_thresholds: Mapping[str, float], grade_confidence: float
    ) -> None:
        super().__init__(session)
        self._thresholds = dict(grade_thresholds)
        self._confidence = grade_confidence

    def lock_candidate(self, user_id: uuid.UUID) -> None:
        self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

    def specialization_topics(self, code: str) -> tuple[Topic, ...] | None:
        specialization = self.session.get(models.Specialization, code)
        if specialization is None:
            return None
        return tuple(topic_of(t) for t in specialization.topics)

    def state(self, user_id: uuid.UUID) -> PathState:
        db = self.session
        survey = db.scalar(
            select(models.Survey)
            .where(models.Survey.user_id == user_id)
            .order_by(models.Survey.number.desc())
            .limit(1)
        )
        attempt = db.scalar(
            select(models.TestAttempt)
            .where(models.TestAttempt.user_id == user_id)
            .order_by(models.TestAttempt.number.desc())
            .limit(1)
        )
        category = db.get(models.CandidateCategory, user_id)
        return PathState(
            survey=_survey_of(survey) if survey else None,
            attempt=_attempt_of(attempt) if attempt else None,
            category=(
                candidate.Category(
                    ref_of(category.specialization), ref_of(category.grade), category.assigned_at
                )
                if category
                else None
            ),
        )

    def survey(self, survey_id: uuid.UUID) -> Survey:
        return _survey_of(self.session.get_one(models.Survey, survey_id))

    def add_survey(self, user_id: uuid.UUID, specialization_code: str, now: datetime) -> Survey:
        row = models.Survey(
            user_id=user_id,
            number=self._next_number(models.Survey, user_id),
            specialization_code=specialization_code,
            created_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return _survey_of(row)

    def attempt_in_progress(self, user_id: uuid.UUID) -> Attempt | None:
        row = self.session.scalar(
            select(models.TestAttempt).where(
                models.TestAttempt.user_id == user_id, models.TestAttempt.finished_at.is_(None)
            )
        )
        return _attempt_of(row) if row else None

    def add_attempt(
        self,
        user_id: uuid.UUID,
        survey: Survey,
        grade_code: str,
        continues: Attempt | None,
        now: datetime,
        purpose: AttemptPurpose = AttemptPurpose.determination,
    ) -> Attempt:
        row = models.TestAttempt(
            user_id=user_id,
            number=self._next_number(models.TestAttempt, user_id),
            survey_id=survey.id,
            specialization_code=survey.specialization_code,
            grade_code=grade_code,
            continues_attempt_id=continues.id if continues else None,
            started_at=now,
            purpose=purpose,
        )
        self.session.add(row)
        self.session.flush()
        return _attempt_of(row)

    def attempts(self, user_id: uuid.UUID) -> list[Attempt]:
        rows = self.session.scalars(
            select(models.TestAttempt)
            .where(models.TestAttempt.user_id == user_id)
            .order_by(models.TestAttempt.number)
        )
        return [_attempt_of(row, presentations=False) for row in rows]

    def add_presentation(
        self,
        attempt: Attempt,
        *,
        family_code: str,
        topic_code: str,
        seed: int,
        params: Mapping[str, object],
        discrimination: float,
        difficulty: float,
        level_before: Normal,
        shown_at: datetime,
    ) -> Presentation:
        row = models.Presentation(
            attempt_id=attempt.id,
            position=len(attempt.presentations),
            family_code=family_code,
            topic_code=topic_code,
            seed=seed,
            params=dict(params),
            discrimination=discrimination,
            difficulty=difficulty,
            topic_theta_before=level_before.mean,
            topic_theta_sd_before=level_before.sd,
            shown_at=shown_at,
        )
        self.session.add(row)
        self.session.flush()
        presentation = _presentation_of(row)
        attempt.presentations.append(presentation)
        return presentation

    def save_answer(self, presentation: Presentation) -> None:
        row = self.session.get_one(models.Presentation, presentation.id)
        row.response = presentation.response
        row.correct = presentation.correct
        row.answered_at = presentation.answered_at
        row.response_time_ms = presentation.response_time_ms
        self.session.flush()

    def finish_attempt(self, attempt: Attempt) -> None:
        row = self.session.get_one(models.TestAttempt, attempt.id)
        row.finished_at = attempt.finished_at
        if attempt.overall is not None:
            row.overall_theta, row.overall_theta_sd = attempt.overall.mean, attempt.overall.sd
        row.outcome = attempt.outcome
        row.outcome_grade_code = attempt.outcome_grade_code
        row.retest_after = attempt.retest_after
        self.session.flush()

    def save_rest_levels(self, presentations: Sequence[Presentation]) -> None:
        for presentation in presentations:
            row = self.session.get_one(models.Presentation, presentation.id)
            row.topic_theta_rest = presentation.topic_theta_rest
            row.topic_theta_rest_sd = presentation.topic_theta_rest_sd
        self.session.flush()

    def add_category(self, attempt: Attempt, now: datetime) -> None:
        assert attempt.outcome_grade_code is not None
        self.session.add(
            models.CandidateCategory(
                user_id=attempt.user_id,
                specialization_code=attempt.specialization_code,
                grade_code=attempt.outcome_grade_code,
                attempt_id=attempt.id,
                assigned_at=now,
            )
        )
        self._log_change(
            attempt.user_id,
            attempt.specialization_code,
            attempt.outcome_grade_code,
            ChangeKind.determined,
            attempt.id,
            now,
        )

    def raise_category(self, attempt: Attempt, now: datetime) -> None:
        assert attempt.outcome_grade_code is not None
        row = self.session.get_one(models.CandidateCategory, attempt.user_id)
        row.grade_code, row.attempt_id, row.assigned_at = (
            attempt.outcome_grade_code,
            attempt.id,
            now,
        )
        self._log_change(
            attempt.user_id, row.specialization_code, row.grade_code, ChangeKind.up, attempt.id, now
        )

    def lower_category(self, user_id: uuid.UUID, grade_code: str, now: datetime) -> None:
        row = self.session.get_one(models.CandidateCategory, user_id)
        row.grade_code, row.assigned_at = grade_code, now
        self._log_change(
            user_id, row.specialization_code, grade_code, ChangeKind.down, row.attempt_id, now
        )

    def category_changes(self, user_id: uuid.UUID) -> list[CategoryChange]:
        rows = self.session.scalars(
            select(models.CategoryChange)
            .where(models.CategoryChange.user_id == user_id)
            .order_by(models.CategoryChange.number)
        )
        return [CategoryChange(row.grade_code, row.kind, row.changed_at) for row in rows]

    def _log_change(
        self,
        user_id: uuid.UUID,
        specialization_code: str,
        grade_code: str,
        kind: ChangeKind,
        attempt_id: uuid.UUID,
        now: datetime,
    ) -> None:
        self.session.add(
            models.CategoryChange(
                user_id=user_id,
                number=self._next_number(models.CategoryChange, user_id),
                specialization_code=specialization_code,
                grade_code=grade_code,
                kind=kind,
                attempt_id=attempt_id,
                changed_at=now,
            )
        )
        self.session.flush()

    def chain(self, attempt: Attempt) -> list[Attempt]:
        """Ссылки `continues` определения берутся одним запросом по попыткам специализации,
        предъявления — вторым и только для звеньев цепочки; последнее звено — сам `attempt`."""
        links = dict(
            self.session.execute(
                select(models.TestAttempt.id, models.TestAttempt.continues_attempt_id).where(
                    models.TestAttempt.user_id == attempt.user_id,
                    models.TestAttempt.specialization_code == attempt.specialization_code,
                )
            ).all()
        )
        previous = []
        current = links[attempt.id]
        while current is not None:
            previous.append(current)
            current = links[current]
        if not previous:
            return [attempt]
        rows = self.session.scalars(
            select(models.TestAttempt)
            .options(selectinload(models.TestAttempt.presentations))
            .where(models.TestAttempt.id.in_(previous))
            .order_by(models.TestAttempt.number)
        )
        return [*(_attempt_of(row) for row in rows), attempt]

    def exposure(
        self, specialization_code: str, current_attempt_id: uuid.UUID, window: int
    ) -> tuple[int, dict[str, int]]:
        recent = (
            select(models.TestAttempt.id)
            .where(
                models.TestAttempt.specialization_code == specialization_code,
                models.TestAttempt.id != current_attempt_id,
                # Задание раскрыто показом: попытка без предъявлений места в окне не занимает.
                select(models.Presentation.id)
                .where(models.Presentation.attempt_id == models.TestAttempt.id)
                .exists(),
            )
            .order_by(models.TestAttempt.started_at.desc())
            .limit(window - 1)
            .subquery()
        )
        attempts = self.session.scalar(select(func.count()).select_from(recent)) or 0
        shown = self.session.execute(
            select(
                models.Presentation.family_code,
                func.count(distinct(models.Presentation.attempt_id)),
            )
            .where(models.Presentation.attempt_id.in_(select(recent.c.id)))
            .group_by(models.Presentation.family_code)
        ).all()
        return attempts, {code: count for code, count in shown}

    def seen(self, user_id: uuid.UUID, current_attempt_id: uuid.UUID) -> dict[str, datetime]:
        rows = self.session.execute(
            select(models.Presentation.family_code, func.max(models.TestAttempt.started_at))
            .join(models.TestAttempt)
            .where(
                models.TestAttempt.user_id == user_id,
                models.TestAttempt.id != current_attempt_id,
            )
            .group_by(models.Presentation.family_code)
        ).all()
        return {code: seen_at for code, seen_at in rows}

    def profile(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> candidate.SkillProfile | None:
        row = self.session.scalar(
            select(SkillProfile).where(
                SkillProfile.user_id == user_id,
                SkillProfile.specialization_code == specialization_code,
            )
        )
        if row is None:
            return None
        topics = sorted(row.topics, key=lambda t: t.topic.position)
        return candidate.SkillProfile(
            overall=self._level(row.overall_theta, row.overall_theta_sd),
            topics=tuple(
                candidate.TopicLevel(
                    CatalogRef(t.topic.code, t.topic.name),
                    self._level(t.theta, t.theta_sd),
                    frozenset(SignalSource(source) for source in t.sources),
                )
                for t in topics
            ),
            updated_at=row.updated_at,
            last_signal_at=row.last_signal_at,
        )

    def save_profile(
        self,
        user_id: uuid.UUID,
        specialization_code: str,
        levels: SkillProfileLevels,
        now: datetime,
    ) -> None:
        profile = self.session.scalar(
            select(SkillProfile).where(
                SkillProfile.user_id == user_id,
                SkillProfile.specialization_code == specialization_code,
            )
        )
        if profile is None:
            profile = SkillProfile(user_id=user_id, specialization_code=specialization_code)
            self.session.add(profile)
        profile.overall_theta, profile.overall_theta_sd = levels.overall.mean, levels.overall.sd
        profile.observations = levels.observations
        profile.updated_at = now
        profile.last_signal_at = levels.last_signal_at
        rows = {row.topic_code: row for row in profile.topics}
        for topic, level in levels.topics.items():
            if topic not in rows:
                rows[topic] = SkillProfileTopic(topic_code=topic)
                profile.topics.append(rows[topic])
            rows[topic].theta, rows[topic].theta_sd = level.mean, level.sd
            rows[topic].regular_task = topic in levels.regular_task_topics
            rows[topic].sources = sorted(levels.sources.get(topic, ()))
        self.session.flush()

    def profiled_specializations(self, user_id: uuid.UUID) -> list[str]:
        return list(
            self.session.scalars(
                select(SkillProfile.specialization_code)
                .where(SkillProfile.user_id == user_id)
                .order_by(SkillProfile.specialization_code)
            )
        )

    def _level(self, theta: float, theta_sd: float) -> candidate.Level:
        return candidate.Level(theta, theta_sd, tuple(self._thresholds.items()), self._confidence)

    def _next_number(
        self,
        model: type[models.Survey] | type[models.TestAttempt] | type[models.CategoryChange],
        user_id: uuid.UUID,
    ) -> int:
        """Следующий номер записи кандидата; гонку исключает блокировка `lock_candidate`."""
        last = self.session.scalar(select(func.max(model.number)).where(model.user_id == user_id))
        return (last or 0) + 1
