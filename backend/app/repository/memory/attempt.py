"""Путь кандидата в памяти — реализация порта `AttemptRepository` для сценарных тестов и
стенда валидации.

Справочник приходит в конструктор доменными типами. Записи — доменные объекты как есть:
изменения сценария видны сразу, откат делает снимок единицы работы. Идентификаторы — по
счётчику: на стенде прогон воспроизводим.
"""

import uuid
import zlib
from collections.abc import Mapping, Sequence
from datetime import datetime

from app.domain import candidate
from app.domain.attempt import AnsweredPresentation, Attempt, PathState, Presentation, Survey
from app.domain.catalog import CatalogRef, Grade, Specialization, Topic
from app.domain.skill import Normal, SkillProfileLevels
from app.repository.memory.unit_of_work import MemoryStore


class MemoryAttemptRepository:
    def __init__(
        self,
        store: MemoryStore,
        specializations: Mapping[str, Specialization],
        grades: Mapping[str, Grade],
        grade_thresholds: Mapping[str, float],
        grade_confidence: float,
    ) -> None:
        self._store = store
        self._specializations = dict(specializations)
        self._grades = dict(grades)
        self._thresholds = tuple(grade_thresholds.items())
        self._confidence = grade_confidence

    # Порт чтения `AttemptReader`.

    def answered(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> Sequence[AnsweredPresentation]:
        attempts = sorted(
            (
                a
                for a in self._attempts().values()
                if a.user_id == user_id and a.specialization_code == specialization_code
            ),
            key=lambda a: a.number,
        )
        return [
            p.answered() for a in attempts for p in a.presentations if p.answered_at is not None
        ]

    # Порт записи `AttemptRepository`.

    def lock_candidate(self, user_id: uuid.UUID) -> None:
        """Хранилище в памяти однопоточное — блокировка не нужна."""

    def specialization_topics(self, code: str) -> tuple[Topic, ...] | None:
        specialization = self._specializations.get(code)
        return specialization.topics if specialization else None

    def state(self, user_id: uuid.UUID) -> PathState:
        surveys = [
            (number, survey)
            for owner, number, survey in self._store.collection("surveys").values()
            if owner == user_id
        ]
        attempts = [a for a in self._attempts().values() if a.user_id == user_id]
        return PathState(
            survey=max(surveys, key=lambda s: s[0])[1] if surveys else None,
            attempt=max(attempts, key=lambda a: a.number) if attempts else None,
            category=self._store.collection("categories").get(user_id),
        )

    def survey(self, survey_id: uuid.UUID) -> Survey:
        survey: Survey = self._store.collection("surveys")[survey_id][2]
        return survey

    def add_survey(self, user_id: uuid.UUID, specialization_code: str, now: datetime) -> Survey:
        surveys = self._store.collection("surveys")
        number = 1 + max(
            (number for owner, number, _ in surveys.values() if owner == user_id), default=0
        )
        survey = Survey(
            id=self._next_id("survey"),
            specialization=self._ref(specialization_code),
            created_at=now,
        )
        surveys[survey.id] = (user_id, number, survey)
        return survey

    def attempt_in_progress(self, user_id: uuid.UUID) -> Attempt | None:
        return next(
            (
                a
                for a in self._attempts().values()
                if a.user_id == user_id and a.finished_at is None
            ),
            None,
        )

    def add_attempt(
        self,
        user_id: uuid.UUID,
        survey: Survey,
        grade_code: str,
        continues: Attempt | None,
        now: datetime,
    ) -> Attempt:
        attempts = self._attempts()
        number = 1 + max((a.number for a in attempts.values() if a.user_id == user_id), default=0)
        attempt = Attempt(
            id=self._next_id("attempt"),
            user_id=user_id,
            number=number,
            survey_id=survey.id,
            specialization_code=survey.specialization_code,
            grade_code=grade_code,
            continues_attempt_id=continues.id if continues else None,
            started_at=now,
        )
        attempts[attempt.id] = attempt
        return attempt

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
        presentation = Presentation(
            id=self._next_id("presentation"),
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
        attempt.presentations.append(presentation)
        return presentation

    def save_answer(self, presentation: Presentation) -> None:
        """Запись — тот же объект в хранилище: ответ уже на месте."""

    def finish_attempt(self, attempt: Attempt) -> None:
        """Запись — тот же объект в хранилище: остановка уже на месте."""

    def save_rest_levels(self, presentations: Sequence[Presentation]) -> None:
        """Запись — те же объекты в хранилище: оценки уже на месте."""

    def add_category(self, attempt: Attempt, now: datetime) -> None:
        assert attempt.outcome_grade_code is not None
        grade = self._grades[attempt.outcome_grade_code]
        self._store.collection("categories")[attempt.user_id] = candidate.Category(
            specialization=self._ref(attempt.specialization_code),
            grade=CatalogRef(grade.code, grade.name),
            assigned_at=now,
        )

    def chain(self, attempt: Attempt) -> list[Attempt]:
        attempts = self._attempts()
        chain = [attempt]
        current = attempt
        while current.continues_attempt_id is not None:
            current = attempts[current.continues_attempt_id]
            chain.insert(0, current)
        return chain

    def exposure(
        self, specialization_code: str, current_attempt_id: uuid.UUID, window: int
    ) -> tuple[int, dict[str, int]]:
        recent = sorted(
            (
                a
                for a in self._attempts().values()
                if a.specialization_code == specialization_code and a.id != current_attempt_id
            ),
            key=lambda a: a.started_at,
            reverse=True,
        )[: window - 1]
        shown: dict[str, int] = {}
        for a in recent:
            for code in a.shown():
                shown[code] = shown.get(code, 0) + 1
        return len(recent), shown

    def seen(self, user_id: uuid.UUID, current_attempt_id: uuid.UUID) -> dict[str, datetime]:
        seen: dict[str, datetime] = {}
        for a in self._attempts().values():
            if a.user_id != user_id or a.id == current_attempt_id:
                continue
            for code in a.shown():
                if code not in seen or seen[code] < a.started_at:
                    seen[code] = a.started_at
        return seen

    def profile(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> candidate.SkillProfile | None:
        stored = self._store.collection("profiles").get((user_id, specialization_code))
        if stored is None:
            return None
        levels, updated_at = stored
        topics = self._specializations[specialization_code].topics
        return candidate.SkillProfile(
            overall=self._level(levels.overall),
            topics=tuple(
                candidate.TopicLevel(CatalogRef(t.code, t.name), self._level(levels.topics[t.code]))
                for t in topics
                if t.code in levels.topics
            ),
            updated_at=updated_at,
            last_signal_at=levels.last_signal_at,
        )

    def save_profile(
        self,
        user_id: uuid.UUID,
        specialization_code: str,
        levels: SkillProfileLevels,
        now: datetime,
    ) -> None:
        self._store.collection("profiles")[(user_id, specialization_code)] = (levels, now)

    def _attempts(self) -> dict[uuid.UUID, Attempt]:
        attempts: dict[uuid.UUID, Attempt] = self._store.collection("attempts")  # type: ignore[assignment]
        return attempts

    def _ref(self, specialization_code: str) -> CatalogRef:
        specialization = self._specializations[specialization_code]
        return CatalogRef(specialization.code, specialization.name)

    def _level(self, level: Normal) -> candidate.Level:
        return candidate.Level(level.mean, level.sd, self._thresholds, self._confidence)

    def _next_id(self, name: str) -> uuid.UUID:
        counters = self._store.collection("counters")
        counters[name] = counters.get(name, 0) + 1
        value: int = counters[name]
        # Пространства счётчиков разводятся по старшим битам: id не пересекаются и стабильны
        # между прогонами.
        return uuid.UUID(int=(zlib.crc32(name.encode()) << 64) | value)
