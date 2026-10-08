"""Регулярное задание — правила формы и наблюдения по ответу (mechanics.md, §11): чистые функции."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.adapter import irt
from app.domain.catalog import CatalogRef, Grade, Specialization, Topic
from app.domain.errors import (
    AnswerAlreadyGraded,
    ReferenceAnswerMismatch,
    TaskLocked,
    TaskNotGradable,
    TaskTopicNotInSpecialization,
    TaskTopicsCount,
    UnknownGrade,
    UnknownSpecialization,
)
from app.domain.regular_task import (
    AnsweredTask,
    RegularTask,
    TaskAnswer,
    TaskForm,
    TaskKind,
    TaskRules,
    catalog_order,
    pseudonym,
    task_observations,
    task_terms,
)
from app.usecase.skill_profile import profile_prior
from settings import Mechanics, Settings

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
QA = Specialization(
    "qa",
    "QA",
    tuple(Topic(f"qa.{t}", t, "qa") for t in ("sql", "api", "automation", "theory")),
)
MIDDLE = Grade("middle", "Middle", 3)
T0 = datetime(2026, 10, 1, tzinfo=UTC)
RULES = TaskRules(
    thresholds=MECHANICS.grade_thresholds,
    rubric_offsets=MECHANICS.regular_task_rubric_offsets,
    discrimination=MECHANICS.regular_task_discrimination,
    weight=MECHANICS.trust_weight_regular_task,
)


def form(
    topics: tuple[str, ...] = ("qa.sql",),
    kind: TaskKind = TaskKind.reference,
    reference: str | None = "42",
) -> TaskForm:
    return TaskForm("qa", "middle", kind, "Сколько строк вернёт запрос?", topics, reference)


def task(kind: TaskKind = TaskKind.reference, answers: int = 0) -> RegularTask:
    terms = task_terms(
        form(kind=kind, reference="42" if kind == TaskKind.reference else None), QA, MIDDLE
    )
    return RegularTask(
        id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        specialization=CatalogRef("qa", "QA"),
        grade=MIDDLE,
        kind=kind,
        prompt=terms.prompt,
        topics=terms.topics,
        reference_answer=terms.reference_answer,
        created_at=T0,
        updated_at=T0,
        withdrawn_at=None,
        answers=answers,
    )


def test_terms_keep_topics_in_given_order_without_duplicates() -> None:
    terms = task_terms(form(("qa.api", "qa.sql", "qa.api")), QA, MIDDLE)

    assert [t.code for t in terms.topics] == ["qa.api", "qa.sql"]
    assert terms.topics[0].name == "api"


@pytest.mark.parametrize("topics", [(), ("qa.sql", "qa.api", "qa.automation", "qa.theory")])
def test_task_has_one_to_three_topics(topics: tuple[str, ...]) -> None:
    with pytest.raises(TaskTopicsCount):
        task_terms(form(topics), QA, MIDDLE)


def test_topic_must_belong_to_task_specialization() -> None:
    with pytest.raises(TaskTopicNotInSpecialization):
        task_terms(form(("qa.sql", "backend.sql")), QA, MIDDLE)


def test_unknown_catalog_entries_are_rejected() -> None:
    with pytest.raises(UnknownSpecialization):
        task_terms(form(), None, MIDDLE)
    with pytest.raises(UnknownGrade):
        task_terms(form(), QA, None)


@pytest.mark.parametrize(
    ("kind", "reference"),
    [(TaskKind.reference, None), (TaskKind.reference, "  "), (TaskKind.open, "42")],
)
def test_reference_answer_only_for_reference_task(kind: TaskKind, reference: str | None) -> None:
    with pytest.raises(ReferenceAnswerMismatch):
        task_terms(form(kind=kind, reference=reference), QA, MIDDLE)


def test_task_is_locked_after_first_answer() -> None:
    task().ensure_editable()
    with pytest.raises(TaskLocked):
        task(answers=1).ensure_editable()


def test_reference_task_checks_normalized_answer_and_open_waits_for_author() -> None:
    assert task().check(" 42 ") is True
    assert task().check("41") is False
    assert task(TaskKind.open).check("развёрнутый ответ") is None


def test_only_open_answer_is_graded_and_only_once() -> None:
    answer = TaskAnswer(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "x", T0, None, None, None)
    answer.ensure_gradable(task(TaskKind.open))
    with pytest.raises(TaskNotGradable):
        answer.ensure_gradable(task())
    with pytest.raises(AnswerAlreadyGraded):
        TaskAnswer(
            answer.id, answer.task_id, answer.candidate_id, "x", T0, None, 2, T0
        ).ensure_gradable(task(TaskKind.open))


def test_reference_answer_is_one_binary_step_per_topic_at_task_grade_threshold() -> None:
    answer = AnsweredTask("middle", ("qa.sql", "qa.api"), T0, correct=True, rubric=None)

    observations = task_observations(answer, RULES)

    c_g = MECHANICS.grade_thresholds["middle"]
    assert [(o.topic, o.correct, o.difficulty) for o in observations] == [
        ("qa.sql", True, c_g),
        ("qa.api", True, c_g),
    ]
    assert {(o.weight, o.discrimination, o.at) for o in observations} == {
        (MECHANICS.trust_weight_regular_task, MECHANICS.regular_task_discrimination, T0)
    }


def test_rubric_is_three_steps_with_offsets() -> None:
    answer = AnsweredTask("junior", ("qa.sql",), T0, correct=None, rubric=2)

    observations = task_observations(answer, RULES)

    c_g = MECHANICS.grade_thresholds["junior"]
    offsets = MECHANICS.regular_task_rubric_offsets
    assert [(o.correct, o.difficulty) for o in observations] == [
        (True, c_g + offsets[1]),
        (True, c_g + offsets[2]),
        (False, c_g + offsets[3]),
    ]


def test_ungraded_answer_gives_no_observations() -> None:
    assert task_observations(AnsweredTask("middle", ("qa.sql",), T0, None, None), RULES) == []


def test_harder_task_grade_raises_level_more_for_the_same_answer() -> None:
    """Сложность ступени — от грейда задания: тот же верный ответ на middle-задание говорит об
    уровне больше, чем на junior."""
    topics = tuple(t.code for t in QA.topics)
    prior = profile_prior(topics, MECHANICS)

    def level(grade: str) -> float:
        answer = AnsweredTask(grade, ("qa.sql",), T0, correct=None, rubric=3)
        return irt.estimate(prior, task_observations(answer, RULES)).topic("qa.sql").mean

    assert level("middle") > level("junior") > irt.initial(prior).topic("qa.sql").mean


def test_catalog_puts_less_answered_first_then_newer() -> None:
    old, new, popular = task(), task(), task(answers=5)
    new = RegularTask(**{**vars(new), "created_at": T0 + timedelta(days=1)})

    assert catalog_order([popular, old, new]) == [new, old, popular]


def test_pseudonym_is_stable_per_task_and_differs_between_tasks() -> None:
    candidate, first, second = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    assert pseudonym(first, candidate) == pseudonym(first, candidate)
    assert pseudonym(first, candidate) != pseudonym(second, candidate)
    assert pseudonym(first, candidate).startswith("Кандидат ")
