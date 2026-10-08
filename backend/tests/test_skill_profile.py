"""Пересчёт профиля навыков — сценарий над портами чтения попытки и модели навыка
(mechanics.md, §11): без базы, на подставных реализациях."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest

from app.adapter import irt
from app.adapter.catalog_file import load_catalog
from app.domain.attempt import AnsweredPresentation
from app.domain.catalog import Topic
from app.domain.fsp import (
    FspAchievement,
    FspEvidence,
    FspResult,
    achievement_topics,
    divergences,
)
from app.domain.skill import Observation, Prior, SignalSource, SkillEstimate, SkillProfileLevels
from app.usecase.skill_profile import refresh_skill_profile, specialization_prior
from settings import CATALOG_FILE, Mechanics, Settings

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = load_catalog(CATALOG_FILE)
DISCIPLINES = {d.code: d for d in CATALOG.fsp_disciplines}
TOPICS = tuple(t.code for s in CATALOG.specializations if s.code == "qa" for t in s.topics)
ROLES = {s.code: tuple(t.code for t in s.topics) for s in CATALOG.specializations}
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

    calls: list[tuple[Prior, list[Observation], bool]] = field(default_factory=list)

    def initial(self, prior: Prior) -> SkillEstimate:
        return irt.initial(prior)

    def estimate(
        self, prior: Prior, observations: Iterable[Observation], *, to_mode: bool = False
    ) -> SkillEstimate:
        observed = list(observations)
        self.calls.append((prior, observed, to_mode))
        return irt.estimate(prior, observed, to_mode=to_mode)


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


def achievement(
    result: FspResult,
    discipline: str = "product",
    *,
    team_role: str | None = None,
    day: date = date(2025, 5, 20),
) -> FspAchievement:
    return FspAchievement(
        event="Чемпионат по продуктовому программированию",
        date=day,
        discipline=discipline,
        place=1,
        result=result,
        team_role=team_role,
    )


def evidence(*achievements: FspAchievement) -> FspEvidence:
    return FspEvidence(achievements, DISCIPLINES, ROLES)


def profile(rows: list[AnsweredPresentation], fsp: FspEvidence | None = None) -> SkillProfileLevels:
    return refresh_skill_profile(Attempts(rows), irt, MECHANICS, USER, "qa", TOPICS, fsp)


def recorded(fsp: FspEvidence, rows: list[AnsweredPresentation] | None = None) -> list[Observation]:
    """Наблюдения, которые профиль отдал модели."""
    model = RecordingModel()
    refresh_skill_profile(Attempts(rows or []), model, MECHANICS, USER, "qa", TOPICS, fsp)
    [(_, observations, _)] = model.calls
    return observations


TEST_ROWS = [answered("qa.api", True, 1), answered("qa.theory", False, 2)]
PRODUCT_QA = {"qa.theory", "qa.api", "qa.automation"}


def test_profile_is_the_model_estimate_to_the_mode_over_answers_with_test_trust_weight() -> None:
    attempts, model = Attempts(TEST_ROWS), RecordingModel()

    levels = refresh_skill_profile(attempts, model, MECHANICS, USER, "qa", TOPICS)

    assert attempts.asked == [(USER, "qa")]
    [(prior, observations, to_mode)] = model.calls
    assert prior == specialization_prior(TOPICS, MECHANICS)
    assert observations == [r.observation(MECHANICS.trust_weight_test) for r in TEST_ROWS]
    assert to_mode
    expected = irt.estimate(prior, observations, to_mode=True)
    assert levels.overall == expected.overall()
    assert levels.topics == {t: expected.topic(t) for t in TOPICS}
    assert levels.observations == 2
    assert levels.last_signal_at == START + timedelta(minutes=2)
    assert levels.sources == {"qa.api": {SignalSource.test}, "qa.theory": {SignalSource.test}}


def test_profile_without_answers_is_the_prior_and_has_no_signal() -> None:
    levels = profile([])

    initial = irt.estimate(specialization_prior(TOPICS, MECHANICS), [])
    assert levels.overall == initial.overall()
    assert levels.topics == {t: initial.topic(t) for t in TOPICS}
    assert levels.observations == 0
    assert levels.last_signal_at is None
    assert levels.sources == {}


def test_observation_keeps_family_parameters_and_trust_weight() -> None:
    row = answered("qa.api", True, 5)

    assert row.observation(0.5) == Observation("qa.api", True, 1.1, 0.3, weight=0.5)


def test_without_fsp_history_profile_is_exactly_the_test_profile() -> None:
    """Кандидат без истории ФСП — профиль ровно тот, что при выключенном модуле ФСП (§11)."""
    assert profile(TEST_ROWS, evidence()) == profile(TEST_ROWS)


def test_fsp_result_narrows_mapped_topics_and_marks_them_confirmed() -> None:
    before = profile(TEST_ROWS)

    after = profile(TEST_ROWS, evidence(achievement(FspResult.winner)))

    assert set(DISCIPLINES["product"].topics) & set(TOPICS) == PRODUCT_QA
    for topic in PRODUCT_QA:
        assert after.topics[topic].sd < before.topics[topic].sd
        assert SignalSource.fsp in after.sources[topic]
    assert "qa.performance" not in after.sources
    assert after.observations == before.observations + len(PRODUCT_QA)


def test_fsp_observation_is_a_solved_task_of_result_difficulty_with_fsp_trust() -> None:
    observations = recorded(evidence(achievement(FspResult.prize)))

    assert {o.topic for o in observations} == PRODUCT_QA
    for o in observations:
        assert o.correct
        assert o.difficulty == MECHANICS.fsp_result_difficulty["prize"]
        assert o.discrimination == MECHANICS.fsp_result_discrimination
        assert o.weight == MECHANICS.trust_weight_fsp
        assert o.source == SignalSource.fsp


@pytest.mark.parametrize(
    "fsp",
    [
        evidence(achievement(FspResult.participant)),
        evidence(achievement(FspResult.winner, discipline="robotics")),
        evidence(achievement(FspResult.winner, discipline="unknown-discipline")),
    ],
    ids=["participant", "discipline-without-topics", "unknown-discipline"],
)
def test_participation_and_disciplines_without_topics_do_not_change_profile(
    fsp: FspEvidence,
) -> None:
    assert profile(TEST_ROWS, fsp) == profile(TEST_ROWS)


def test_more_results_narrow_more_than_one() -> None:
    """Число соревнований входит само: каждый результат — отдельное наблюдение (§11)."""
    one = profile(TEST_ROWS, evidence(achievement(FspResult.finalist)))
    ten = profile(TEST_ROWS, evidence(*[achievement(FspResult.finalist)] * 10))

    assert ten.topics["qa.api"].sd < one.topics["qa.api"].sd
    assert ten.topics["qa.api"].mean > one.topics["qa.api"].mean


def test_team_result_with_role_observes_only_role_topics_within_discipline() -> None:
    observations = recorded(evidence(achievement(FspResult.winner, team_role="qa")))

    assert {o.topic for o in observations} == PRODUCT_QA


def test_team_role_outside_profile_specialization_gives_no_observations() -> None:
    """Роль фронтендера в команде говорит о темах фронтенда, а не QA."""
    team = achievement(FspResult.winner, team_role="frontend")

    assert profile(TEST_ROWS, evidence(team)) == profile(TEST_ROWS)


def test_role_topics_within_discipline_and_role_topics_without_intersection() -> None:
    frontend_team = achievement(FspResult.winner, team_role="frontend")
    qa_in_algorithms = achievement(FspResult.winner, discipline="algorithmic", team_role="qa")
    personal = achievement(FspResult.winner)

    assert achievement_topics(frontend_team, evidence()) == (
        "frontend.frameworks",
        "frontend.markup",
        "frontend.browser",
    )
    assert achievement_topics(qa_in_algorithms, evidence()) == TOPICS
    assert achievement_topics(personal, evidence()) == DISCIPLINES["product"].topics


def test_signals_go_to_the_model_in_time_order() -> None:
    early = achievement(FspResult.winner, day=date(2020, 1, 1))
    late = achievement(FspResult.finalist, day=date(2030, 1, 1))

    observations = recorded(evidence(late, early), TEST_ROWS)

    difficulty = MECHANICS.fsp_result_difficulty
    assert [o.difficulty for o in observations[:3]] == [difficulty["winner"]] * 3
    assert observations[3:5] == [r.observation(MECHANICS.trust_weight_test) for r in TEST_ROWS]
    assert [o.difficulty for o in observations[5:]] == [difficulty["finalist"]] * 3
    last = profile(TEST_ROWS, evidence(late, early)).last_signal_at
    assert last == datetime(2030, 1, 1, tzinfo=UTC)


QA = [Topic(code, code, "qa") for code in TOPICS]


def test_divergence_when_test_is_far_below_the_result() -> None:
    winner = MECHANICS.fsp_result_difficulty["winner"]
    theta = MECHANICS.fsp_divergence_theta
    test_levels = dict.fromkeys(TOPICS, winner) | {"qa.api": winner - theta - 0.1}

    found = divergences(
        evidence(achievement(FspResult.finalist), achievement(FspResult.winner)),
        QA,
        test_levels,
        difficulty=MECHANICS.fsp_result_difficulty,
        threshold=theta,
    )

    assert [(d.topic.code, d.result, d.result_level) for d in found] == [
        ("qa.api", FspResult.winner, winner)
    ]


def test_test_above_the_result_and_participation_are_not_divergences() -> None:
    found = divergences(
        evidence(achievement(FspResult.finalist), achievement(FspResult.participant)),
        QA,
        dict.fromkeys(TOPICS, -3.0) | dict.fromkeys(PRODUCT_QA, 3.0),
        difficulty=MECHANICS.fsp_result_difficulty,
        threshold=MECHANICS.fsp_divergence_theta,
    )

    assert found == []
