"""Пересчёт профиля навыков — сценарий над портами чтения попытки и модели навыка
(mechanics.md, §11): без базы, на подставных реализациях."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.adapter import irt
from app.domain.attempt import AnsweredPresentation
from app.domain.skill import Observation, Prior, SkillEstimate
from app.usecase.skill_profile import refresh_skill_profile, specialization_prior
from settings import Mechanics, Settings

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
TOPICS = ("qa.sql", "qa.api")
USER = uuid.uuid4()
START = datetime(2026, 10, 1, 12, tzinfo=UTC)


@dataclass
class Attempts:
    """Подставное чтение попыток: ответы одного кандидата по одной специализации."""

    rows: list[AnsweredPresentation]
    asked: list[tuple[uuid.UUID, str]] = field(default_factory=list)

    def answered(
        self, user_id: uuid.UUID, specialization_code: str
    ) -> Sequence[AnsweredPresentation]:
        self.asked.append((user_id, specialization_code))
        return self.rows


@dataclass
class RecordingModel:
    """Модель навыка, которая запоминает вызов и отдаёт оценку IRT."""

    calls: list[tuple[Prior, list[Observation]]] = field(default_factory=list)

    def initial(self, prior: Prior) -> SkillEstimate:
        return irt.initial(prior)

    def estimate(self, prior: Prior, observations: Iterable[Observation]) -> SkillEstimate:
        observed = list(observations)
        self.calls.append((prior, observed))
        return irt.estimate(prior, observed)


def answered(topic: str, correct: bool, minutes: int) -> AnsweredPresentation:
    return AnsweredPresentation(
        family_code=f"{topic}.family",
        topic=topic,
        params={"n": minutes},
        discrimination=1.1,
        difficulty=0.3,
        correct=correct,
        answered_at=START + timedelta(minutes=minutes),
    )


def test_profile_is_the_model_estimate_over_answers_with_test_trust_weight() -> None:
    rows = [answered("qa.sql", True, 1), answered("qa.api", False, 2), answered("qa.sql", True, 3)]
    attempts, model = Attempts(rows), RecordingModel()

    profile = refresh_skill_profile(attempts, model, MECHANICS, USER, "qa", TOPICS)

    assert attempts.asked == [(USER, "qa")]
    [(prior, observations)] = model.calls
    assert prior == specialization_prior(TOPICS, MECHANICS)
    assert observations == [r.observation(MECHANICS.trust_weight_test) for r in rows]
    expected = irt.estimate(prior, observations)
    assert profile.overall == expected.overall()
    assert profile.topics == {t: expected.topic(t) for t in TOPICS}
    assert profile.observations == 3
    assert profile.last_signal_at == START + timedelta(minutes=3)


def test_profile_without_answers_is_the_prior_and_has_no_signal() -> None:
    profile = refresh_skill_profile(Attempts([]), RecordingModel(), MECHANICS, USER, "qa", TOPICS)

    initial = irt.estimate(specialization_prior(TOPICS, MECHANICS), [])
    assert profile.overall == initial.overall()
    assert profile.topics == {t: initial.topic(t) for t in TOPICS}
    assert profile.observations == 0
    assert profile.last_signal_at is None


def test_observation_keeps_family_parameters_and_trust_weight() -> None:
    row = answered("qa.api", True, 5)

    assert row.observation(0.5) == Observation("qa.api", True, 1.1, 0.3, weight=0.5)
