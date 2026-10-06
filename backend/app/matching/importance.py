"""Важность тем потребности (mechanics.md, §12) — чистая функция.

По умолчанию важность выводится из стека: тема, с которой связано не меньше
`need_key_topic_min_technologies` технологий потребности, — ключевая; одна технология — важная;
ни одной — желательная. Правка работодателя важнее вывода. Технологии, не связанные с темами
специализации, на важность не влияют.
"""

import enum
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass


class TopicImportance(enum.StrEnum):
    key = "key"
    important = "important"
    nice = "nice"


@dataclass(frozen=True)
class TopicRow:
    topic: str
    importance: TopicImportance
    # Важность поставил работодатель, а не вывод из стека.
    edited: bool
    # Технологии стека, связанные с темой, — откуда взялась важность по умолчанию.
    technologies: tuple[str, ...]


def topic_importance(
    topics: Sequence[str],
    stack: Mapping[str, Collection[str]],
    edited: Mapping[str, TopicImportance],
    *,
    key_min_technologies: int,
) -> list[TopicRow]:
    """Важность каждой темы специализации в порядке `topics`.

    `stack` — технология потребности → темы, с которыми она связана; `edited` — правки
    работодателя по кодам тем.
    """
    rows = []
    for topic in topics:
        technologies = tuple(tech for tech, linked in stack.items() if topic in linked)
        if topic in edited:
            importance = edited[topic]
        elif len(technologies) >= key_min_technologies:
            importance = TopicImportance.key
        elif technologies:
            importance = TopicImportance.important
        else:
            importance = TopicImportance.nice
        rows.append(TopicRow(topic, importance, topic in edited, technologies))
    return rows
