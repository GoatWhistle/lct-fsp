"""Пересчёт профиля навыков — сценарий над портами чтения попытки и модели навыка
(mechanics.md, §11): без базы, на подставных реализациях."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.adapter import irt
from app.domain.attempt import AnsweredPresentation
from app.domain.regular_task import AnsweredTask, task_observations
from app.domain.skill import Observation, Prior, SkillEstimate, SkillProfileLevels
from app.usecase.skill_profile import (
    ProfileFreshness,
    profile_prior,
    refresh_skill_profile,
    task_rules,
)
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

    def advance(
        self, prior: Prior, levels: SkillProfileLevels, now: datetime
    ) -> SkillProfileLevels:
        return irt.advance(prior, levels, now)


@dataclass
class Tasks:
    """Подставное чтение ответов на регулярные задания."""

    rows: list[AnsweredTask] = field(default_factory=list)

    def answered(self, user_id: uuid.UUID, specialization_code: str) -> Sequence[AnsweredTask]:
        return self.rows


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

    profile = refresh_skill_profile(attempts, Tasks(), model, MECHANICS, USER, "qa", TOPICS)

    assert attempts.asked == [(USER, "qa")]
    [(prior, observations)] = model.calls
    assert prior == profile_prior(TOPICS, MECHANICS)
    assert prior.decay_sd_per_year == MECHANICS.profile_decay_sd_per_year
    assert observations == [r.observation(MECHANICS.trust_weight_test) for r in rows]
    expected = irt.estimate(prior, observations)
    assert profile.overall == expected.overall()
    assert profile.topics == {t: expected.topic(t) for t in TOPICS}
    assert profile.observations == 3
    assert profile.last_signal_at == START + timedelta(minutes=3)


def test_profile_without_answers_is_the_prior_and_has_no_signal() -> None:
    profile = refresh_skill_profile(
        Attempts([]), Tasks(), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )

    initial = irt.estimate(profile_prior(TOPICS, MECHANICS), [])
    assert profile.overall == initial.overall()
    assert profile.topics == {t: initial.topic(t) for t in TOPICS}
    assert profile.observations == 0
    assert profile.last_signal_at is None


def test_observation_keeps_family_parameters_and_trust_weight() -> None:
    row = answered("qa.api", True, 5)

    assert row.observation(0.5) == Observation(
        "qa.api", True, 1.1, 0.3, weight=0.5, at=START + timedelta(minutes=5)
    )


def task_answer(
    topics: tuple[str, ...], minutes: int, *, correct: bool | None = None, rubric: int | None = None
) -> AnsweredTask:
    return AnsweredTask("middle", topics, START + timedelta(minutes=minutes), correct, rubric)


def test_task_answers_join_test_answers_in_time_order() -> None:
    tests = [answered("qa.sql", True, 1), answered("qa.api", False, 10)]
    reference = task_answer(("qa.api",), 5, correct=True)
    graded = task_answer(("qa.sql",), 20, rubric=2)
    model = RecordingModel()

    profile = refresh_skill_profile(
        Attempts(tests), Tasks([reference, graded]), model, MECHANICS, USER, "qa", TOPICS
    )

    [(_, observations)] = model.calls
    rules = task_rules(MECHANICS)
    assert observations == [
        tests[0].observation(MECHANICS.trust_weight_test),
        *task_observations(reference, rules),
        tests[1].observation(MECHANICS.trust_weight_test),
        *task_observations(graded, rules),
    ]
    assert profile.observations == len(observations)
    assert profile.last_signal_at == START + timedelta(minutes=20)
    assert profile.regular_task_topics == {"qa.sql", "qa.api"}


def test_only_right_answers_confirm_topic_but_every_answer_counts() -> None:
    wrong = task_answer(("qa.sql",), 5, correct=False)
    weak = task_answer(("qa.api",), 6, rubric=1)
    model = RecordingModel()

    profile = refresh_skill_profile(
        Attempts([]), Tasks([wrong, weak]), model, MECHANICS, USER, "qa", TOPICS
    )

    [(_, observations)] = model.calls
    assert len(observations) == 4
    assert profile.regular_task_topics == frozenset()


def test_ungraded_open_answer_is_not_a_signal() -> None:
    tests = [answered("qa.sql", True, 1)]
    waiting = task_answer(("qa.api",), 5)

    with_waiting = refresh_skill_profile(
        Attempts(tests), Tasks([waiting]), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )
    without = refresh_skill_profile(
        Attempts(tests), Tasks(), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )

    assert with_waiting == without
    assert with_waiting.regular_task_topics == frozenset()


def test_rubric_narrows_uncertainty_only_on_task_topics() -> None:
    tests = [answered(t, True, i) for i, t in enumerate(TOPICS * 3)]
    graded = task_answer(("qa.sql",), 30, rubric=3)

    before = refresh_skill_profile(
        Attempts(tests), Tasks(), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )
    after = refresh_skill_profile(
        Attempts(tests), Tasks([graded]), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )

    assert after.topics["qa.sql"].sd < before.topics["qa.sql"].sd
    assert after.topics["qa.sql"].mean > before.topics["qa.sql"].mean
    # Чужая тема сужается только через общую часть уровня — заметно меньше своей.
    sql_gain = before.topics["qa.sql"].sd - after.topics["qa.sql"].sd
    api_gain = before.topics["qa.api"].sd - after.topics["qa.api"].sd
    assert api_gain < sql_gain / 2


def test_freshness_widens_saved_profile_with_time_and_keeps_level() -> None:
    tests = [answered(t, True, i) for i, t in enumerate(TOPICS * 3)]
    saved = refresh_skill_profile(
        Attempts(tests), Tasks(), RecordingModel(), MECHANICS, USER, "qa", TOPICS
    )
    freshness = ProfileFreshness(irt, MECHANICS)
    assert saved.last_signal_at is not None

    same = freshness.levels(saved, saved.last_signal_at)
    later = freshness.levels(saved, saved.last_signal_at + timedelta(days=365))
    much_later = freshness.levels(saved, saved.last_signal_at + timedelta(days=365 * 100))

    assert same == saved
    prior = irt.initial(profile_prior(TOPICS, MECHANICS))
    for topic in TOPICS:
        assert later.topics[topic].mean == saved.topics[topic].mean
        assert saved.topics[topic].sd < later.topics[topic].sd
        assert much_later.topics[topic].sd <= prior.topic(topic).sd + 1e-12
