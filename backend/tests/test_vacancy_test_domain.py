"""План теста по вакансии — чистая функция потребности (mechanics.md, §6)."""

from datetime import UTC, datetime

from app.domain.catalog import CatalogRef
from app.domain.importance import TopicImportance
from app.domain.selection import NeedContent
from app.domain.skill import Normal
from app.domain.vacancy_test import (
    example_family,
    next_topic,
    vacancy_test_result,
)
from app.domain.work import WorkFormat
from app.usecase.vacancy_test import plan_of_need
from settings import Mechanics, Settings
from validation.main import catalog

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()
T0 = datetime(2026, 10, 10, 12, tzinfo=UTC)


def need(specialization: str, stack: list[str], grade: str = "middle") -> NeedContent:
    return NeedContent(
        title=f"{specialization} {grade}",
        specialization=CATALOG.specializations[specialization],
        grade=CATALOG.grades[grade],
        stack=tuple(CATALOG.technologies[t] for t in stack),
        edited_importance={},
        work_format=WorkFormat.remote,
        city=None,
        salary=None,
        updated_at=T0,
    )


def topics(stack: list[str], specialization: str = "backend") -> list[str]:
    return [t.topic.code for t in plan_of_need(need(specialization, stack), MECHANICS).topics]


def test_different_stacks_give_different_topics() -> None:
    queues = topics(["kafka", "redis", "go"])
    web = topics(["fastapi", "postgresql", "django"])
    assert queues != web
    assert "backend.distributed" in queues and "backend.distributed" not in web
    assert "backend.databases" in web and "backend.databases" not in queues


def test_only_key_and_important_topics_unless_none() -> None:
    plan = plan_of_need(need("backend", ["kafka"]), MECHANICS)
    assert [t.topic.code for t in plan.topics] == ["backend.distributed"]
    assert {t.importance for t in plan.topics} == {TopicImportance.important}
    everything = plan_of_need(need("backend", []), MECHANICS)
    assert len(everything.topics) == len(CATALOG.specializations["backend"].topics)


def test_quotas_add_up_and_follow_weights() -> None:
    plan = plan_of_need(need("backend", ["fastapi", "django", "postgresql", "kafka"]), MECHANICS)
    assert plan.items == MECHANICS.vacancy_test_items
    assert all(t.items >= MECHANICS.vacancy_test_min_items_per_topic for t in plan.topics)
    assert abs(sum(t.weight for t in plan.topics) - 1) < 1e-6
    by_code = {t.topic.code: t for t in plan.topics}
    assert by_code["backend.databases"].importance == TopicImportance.key
    assert by_code["backend.databases"].items > by_code["backend.distributed"].items


def test_requirement_is_grade_threshold() -> None:
    for grade in ("junior", "senior"):
        plan = plan_of_need(need("frontend", ["react"], grade), MECHANICS)
        assert plan.requirement == MECHANICS.grade_thresholds[grade]
        assert plan.grade.code == grade


def test_next_topic_fills_the_largest_gap_first() -> None:
    plan = plan_of_need(need("backend", ["fastapi", "django", "postgresql", "kafka"]), MECHANICS)
    counts: dict[str, int] = {}
    order = []
    while (topic := next_topic(plan, counts)) is not None:
        order.append(topic)
        counts[topic] = counts.get(topic, 0) + 1
    assert counts == plan.quotas()
    assert order[0] == max(plan.topics, key=lambda t: t.items).topic.code


def test_example_family_is_closest_to_requirement() -> None:
    assert example_family({"a": -1.0, "b": 0.4, "c": 1.5}, 0.5) == "b"
    assert example_family({"b": 0.0, "a": 1.0}, 0.5) == "a"
    assert example_family({}, 0.0) is None


def test_result_weights_topic_probabilities() -> None:
    plan = plan_of_need(need("backend", ["kafka", "postgresql"]), MECHANICS)
    levels = {t.topic.code: Normal(plan.requirement, 0.5) for t in plan.topics}
    answers = [(plan.topics[0].topic.code, True), (plan.topics[0].topic.code, False)]
    result = vacancy_test_result(plan, levels, answers, T0)
    assert abs(result.match - 0.5) < 1e-9
    first = result.topics[0]
    assert (first.answered, first.correct) == (2, 1)
    assert result.topics[0].topic == CatalogRef(
        plan.topics[0].topic.code, plan.topics[0].topic.name
    )
