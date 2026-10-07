"""Важность тем потребности из стека — чистая функция (mechanics.md, §12)."""

from app.domain.importance import TopicImportance, topic_importance

KEY, IMPORTANT, NICE = TopicImportance.key, TopicImportance.important, TopicImportance.nice
TOPICS = ["databases", "api", "security"]


def importance(
    stack: dict[str, set[str]],
    edited: dict[str, TopicImportance] | None = None,
    key_min: int = 2,
) -> dict[str, TopicImportance]:
    rows = topic_importance(TOPICS, stack, edited or {}, key_min_technologies=key_min)
    return {row.topic: row.importance for row in rows}


def test_two_technologies_make_topic_key_one_important_none_nice() -> None:
    stack = {"postgresql": {"databases"}, "django": {"databases", "api"}}

    assert importance(stack) == {"databases": KEY, "api": IMPORTANT, "security": NICE}


def test_key_threshold_comes_from_config() -> None:
    assert importance({"django": {"databases", "api"}}, key_min=1) == {
        "databases": KEY,
        "api": KEY,
        "security": NICE,
    }


def test_empty_stack_makes_every_topic_nice() -> None:
    assert set(importance({}).values()) == {NICE}


def test_technologies_outside_specialization_change_nothing() -> None:
    assert importance({"docker": {"containers"}}) == importance({})


def test_employer_edit_beats_stack() -> None:
    stack = {"postgresql": {"databases"}, "django": {"databases", "api"}}

    rows = topic_importance(
        TOPICS, stack, {"databases": NICE, "security": KEY}, key_min_technologies=2
    )

    assert [(r.topic, r.importance, r.edited) for r in rows] == [
        ("databases", NICE, True),
        ("api", IMPORTANT, False),
        ("security", KEY, True),
    ]


def test_row_names_technologies_behind_topic() -> None:
    stack = {"postgresql": {"databases"}, "django": {"databases", "api"}, "redis": {"cache"}}

    rows = topic_importance(TOPICS, stack, {}, key_min_technologies=2)

    assert [(r.topic, r.technologies) for r in rows] == [
        ("databases", ("postgresql", "django")),
        ("api", ("django",)),
        ("security", ()),
    ]
