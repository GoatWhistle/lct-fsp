"""Калибровка в памяти — реализация порта `CalibrationRepository` для сценарных тестов и
стенда валидации.

Ответы для связки шкалы и переоценки читаются из тех же попыток, что пишет
`MemoryAttemptRepository`, — по его индексам: хранилище общее. Блокировок нет — хранилище
однопоточное.
"""

import itertools
from collections.abc import Collection
from datetime import datetime

from app.domain import bank
from app.domain.attempt import Attempt, Presentation
from app.domain.calibration import AnchorAnswer, CalibratedFamily, Link, Parameters, Response
from app.domain.skill import Normal
from app.repository.memory.attempt import (
    ANCHOR_PORTIONS,
    FAMILY_PRESENTATIONS,
    FINISHED,
    REST_READY,
    latest,
)
from app.repository.memory.unit_of_work import MemoryStore

ANCHORS = frozenset(f.code for f in bank.BANK if f.anchor)


class MemoryCalibrationRepository:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def parameters(self, codes: Collection[str]) -> dict[str, CalibratedFamily]:
        families = self._store.collection("families")
        return {code: families[code] for code in codes if code in families}

    def locked(self, code: str, start: Parameters) -> CalibratedFamily:
        families = self._store.collection("families")
        if code not in families:
            families[code] = CalibratedFamily(
                family_code=code,
                discrimination=start.discrimination,
                difficulty=start.difficulty,
            )
        state: CalibratedFamily = families[code]
        return state

    def save(self, family: CalibratedFamily) -> None:
        self._store.collection("families")[family.family_code] = family

    def links(self, specialization: str) -> tuple[Link, Link]:
        stored = self._store.collection("scale_links").get(specialization)
        if stored is None:
            return Link(), Link()
        before, rest, _ = stored
        return before, rest

    def save_links(self, specialization: str, before: Link, rest: Link, now: datetime) -> None:
        self._store.collection("scale_links")[specialization] = (before, rest, now)

    def anchor_answers(
        self, specialization: str, anchors: Collection[str], window_attempts: int
    ) -> list[AnchorAnswer]:
        wanted = set(anchors)
        recent = itertools.islice(
            latest(self._store.collection(FINISHED), specialization), window_attempts
        )
        answers: list[AnchorAnswer] = []
        for attempt in recent:
            answers.extend(a for a in self._portion(attempt) if a.family_code in wanted)
        return answers

    def _portion(self, attempt: Attempt) -> list[AnchorAnswer]:
        """Якорные ответы попытки в порядке предъявлений; собираются один раз, пока
        `save_rest_levels` не обновит итоговые оценки."""
        portions = self._store.collection(ANCHOR_PORTIONS)
        portion: list[AnchorAnswer] | None = portions.get(attempt.id)
        if portion is None:
            portion = portions[attempt.id] = [
                _anchor_answer(p)
                for p in attempt.presentations
                if p.family_code in ANCHORS and p.correct is not None
            ]
        return portion

    def rest_answers(self, code: str) -> list[Response]:
        presentations: list[Presentation] = self._store.collection(FAMILY_PRESENTATIONS).get(
            code, []
        )
        return [
            Response(Normal(p.topic_theta_rest, p.topic_theta_rest_sd), p.correct)
            for p in presentations
            if p.topic_theta_rest is not None
            and p.topic_theta_rest_sd is not None
            and p.correct is not None
        ]

    def ready_responses(self, code: str) -> int:
        return len(self._store.collection(REST_READY).get(code, ()))


def _anchor_answer(p: Presentation) -> AnchorAnswer:
    assert p.correct is not None
    rest = None
    if p.topic_theta_rest is not None and p.topic_theta_rest_sd is not None:
        rest = Response(Normal(p.topic_theta_rest, p.topic_theta_rest_sd), p.correct)
    return AnchorAnswer(
        family_code=p.family_code,
        params=Parameters(p.discrimination, p.difficulty),
        before=Response(Normal(p.topic_theta_before, p.topic_theta_sd_before), p.correct),
        rest=rest,
    )
