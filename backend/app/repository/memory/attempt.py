"""Путь кандидата в памяти — реализация порта `AttemptRepository` для сценарных тестов и
стенда валидации.

Справочник приходит в конструктор доменными типами. Записи — доменные объекты как есть:
изменения сценария видны сразу, откат делает снимок единицы работы. Идентификаторы — по
счётчику: на стенде прогон воспроизводим.

Рядом с записями хранилище держит индексы: попытки кандидата, попытки специализации по времени,
предъявления семейства. В индексах те же объекты, что в записях, и откатываются они вместе с
ними. Без индексов каждый шаг читал бы все попытки, и стенд на тысячах кандидатов не дождался бы
конца прогона.
"""

import bisect
import itertools
import uuid
import zlib
from collections import Counter
from collections.abc import Hashable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from app.domain import candidate
from app.domain.attempt import AnsweredPresentation, Attempt, PathState, Presentation, Survey
from app.domain.catalog import CatalogRef, Grade, Specialization, Topic
from app.domain.skill import Normal, SkillProfileLevels
from app.repository.memory.unit_of_work import MemoryStore

# Индексы попыток специализации по времени — по началу и по остановке — и предъявлений семейства.
# Остановленные попытки, предъявления семейства и id предъявлений с итоговой оценкой читает и
# `MemoryCalibrationRepository`.
STARTED = "specialization_started"
FINISHED = "specialization_finished"
FAMILY_PRESENTATIONS = "family_presentations"
REST_READY = "family_rest_ready"
FINISHED_SHOWN = "finished_shown"
# Окно показов специализации: последний подсчёт и отметки изменений после него.
EXPOSURE_CACHE = "exposure_cache"
EXPOSURE_CHANGES = "exposure_changes"


def _insort(index: dict[Hashable, Any], key: str, attempt: Attempt, at: datetime) -> None:
    """Попытка в список индекса по времени `at`; при равном времени — после прежних."""
    bisect.insort_right(index.setdefault(key, []), (at, attempt), key=lambda entry: entry[0])


def latest(index: dict[Hashable, Any], key: str) -> Iterator[Attempt]:
    """Попытки из списка индекса — от поздних к ранним."""
    return (attempt for _, attempt in reversed(index.get(key, [])))


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
        return [
            p.answered()
            for a in self._of_user(user_id)
            if a.specialization_code == specialization_code
            for p in a.presentations
            if p.answered_at is not None
        ]

    # Порт записи `AttemptRepository`.

    def lock_candidate(self, user_id: uuid.UUID) -> None:
        """Хранилище в памяти однопоточное — блокировка не нужна."""

    def specialization_topics(self, code: str) -> tuple[Topic, ...] | None:
        specialization = self._specializations.get(code)
        return specialization.topics if specialization else None

    def state(self, user_id: uuid.UUID) -> PathState:
        surveys = self._store.collection("user_surveys").get(user_id, [])
        attempts = self._of_user(user_id)
        return PathState(
            survey=surveys[-1] if surveys else None,
            attempt=attempts[-1] if attempts else None,
            category=self._store.collection("categories").get(user_id),
        )

    def survey(self, survey_id: uuid.UUID) -> Survey:
        survey: Survey = self._store.collection("surveys")[survey_id]
        return survey

    def add_survey(self, user_id: uuid.UUID, specialization_code: str, now: datetime) -> Survey:
        survey = Survey(
            id=self._next_id("survey"),
            specialization=self._ref(specialization_code),
            created_at=now,
        )
        self._store.collection("surveys")[survey.id] = survey
        self._store.collection("user_surveys").setdefault(user_id, []).append(survey)
        return survey

    def attempt_in_progress(self, user_id: uuid.UUID) -> Attempt | None:
        return next((a for a in self._of_user(user_id) if a.finished_at is None), None)

    def add_attempt(
        self,
        user_id: uuid.UUID,
        survey: Survey,
        grade_code: str,
        continues: Attempt | None,
        now: datetime,
    ) -> Attempt:
        mine = self._store.collection("user_attempts").setdefault(user_id, [])
        attempt = Attempt(
            id=self._next_id("attempt"),
            user_id=user_id,
            number=len(mine) + 1,
            survey_id=survey.id,
            specialization_code=survey.specialization_code,
            grade_code=grade_code,
            continues_attempt_id=continues.id if continues else None,
            started_at=now,
        )
        self._attempts()[attempt.id] = attempt
        mine.append(attempt)
        _insort(self._store.collection(STARTED), survey.specialization_code, attempt, now)
        self._exposure_changed(attempt)
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
        by_family = self._store.collection(FAMILY_PRESENTATIONS)
        by_family.setdefault(family_code, []).append(presentation)
        self._exposure_changed(attempt)
        return presentation

    def save_answer(self, presentation: Presentation) -> None:
        """Запись — тот же объект в хранилище: ответ уже на месте."""

    def finish_attempt(self, attempt: Attempt) -> None:
        """Запись — тот же объект в хранилище: остановка уже на месте. Попытка встаёт в индекс
        остановленных по времени остановки, её семейства — в набор показанных."""
        assert attempt.finished_at is not None
        finished = self._store.collection(FINISHED_SHOWN)
        if attempt.id not in finished:
            finished[attempt.id] = frozenset(attempt.shown())
            by_finish = self._store.collection(FINISHED)
            _insort(by_finish, attempt.specialization_code, attempt, attempt.finished_at)

    def save_rest_levels(self, presentations: Sequence[Presentation]) -> None:
        """Запись — те же объекты в хранилище: оценки уже на месте. Предъявления встают в счёт
        ответов семейства с итоговой оценкой."""
        ready = self._store.collection(REST_READY)
        for p in presentations:
            if p.topic_theta_rest is not None:
                ready.setdefault(p.family_code, set()).add(p.id)

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
        """Окно считается заново, только если с прошлого подсчёта для той же попытки что-то
        поменяла другая попытка: свои показы текущей попытки в окно не входят, а подсчёт по
        сотням попыток — самый дорогой шаг стенда."""
        cache = self._store.collection(EXPOSURE_CACHE)
        cached = cache.get(specialization_code)
        changes = self._store.collection(EXPOSURE_CHANGES).get(specialization_code, (0, None, 0))
        if cached is not None:
            attempt_id, cached_window, at_change, counted = cached
            total, owner, run_start = changes
            # Все изменения после подсчёта — от текущей попытки.
            own = owner == current_attempt_id and run_start <= at_change + 1
            if (
                attempt_id == current_attempt_id
                and cached_window == window
                and (total == at_change or own)
            ):
                return counted[0], dict(counted[1])
        candidates = latest(self._store.collection(STARTED), specialization_code)
        recent = list(
            itertools.islice(
                (a for a in candidates if a.id != current_attempt_id and a.presentations),
                max(window - 1, 0),
            )
        )
        # Семейства остановленной попытки больше не меняются — их набор взят при остановке.
        finished = self._store.collection(FINISHED_SHOWN)
        shown = Counter(
            itertools.chain.from_iterable(finished.get(a.id) or a.shown() for a in recent)
        )
        counted = len(recent), dict(shown)
        cache[specialization_code] = (current_attempt_id, window, changes[0], counted)
        return counted[0], dict(counted[1])

    def seen(self, user_id: uuid.UUID, current_attempt_id: uuid.UUID) -> dict[str, datetime]:
        seen: dict[str, datetime] = {}
        for a in self._of_user(user_id):
            if a.id == current_attempt_id:
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

    def _exposure_changed(self, attempt: Attempt) -> None:
        """Отметка изменения окна показов специализации: номер изменения, попытка и номер, с
        которого она меняет окно без перерыва."""
        changes = self._store.collection(EXPOSURE_CHANGES)
        total, owner, run_start = changes.get(attempt.specialization_code, (0, None, 0))
        total += 1
        if owner != attempt.id:
            owner, run_start = attempt.id, total
        changes[attempt.specialization_code] = (total, owner, run_start)

    def _of_user(self, user_id: uuid.UUID) -> list[Attempt]:
        """Попытки кандидата по номеру."""
        attempts: list[Attempt] = self._store.collection("user_attempts").get(user_id, [])
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
