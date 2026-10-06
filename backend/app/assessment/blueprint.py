"""Фиксированный бланк попытки — пока нет адаптивного выбора (lct-9).

Попытка на грейд g по каждой теме спрашивает до `test_min_items_per_topic` невиданных в этом
определении категории семейств грейдов g и g−1: порог c_g лежит между их экспертными
сложностями, там тест различает лучше всего. Дотест на g−1 — то же правило, поэтому он добирает
семейства грейда g−2: семейства g−1 уже показаны.
"""

from collections.abc import Collection, Sequence

from app.assessment.bank import Family


def fixed_blueprint(
    *,
    topics: Sequence[str],
    families: Sequence[Family],
    grades: Sequence[str],
    grade: str,
    seen: Collection[str],
    per_topic: int,
) -> list[str]:
    """Коды семейств по порядку: сначала грейд ниже, по темам в порядке справочника.

    `grades` — от младшего к старшему; `seen` — семейства, уже показанные в этом определении.
    """
    level = grades.index(grade)
    wanted = grades[max(level - 1, 0) : level + 1]
    picked: list[Family] = []
    for topic in topics:
        candidates = [
            f for f in families if f.topic == topic and f.grade in wanted and f.code not in seen
        ]
        # Ближе к порогу грейда — первыми, если семейств больше, чем помещается в бланк.
        candidates.sort(key=lambda f: -grades.index(f.grade))
        picked += candidates[:per_topic]
    order = {topic: i for i, topic in enumerate(topics)}
    picked.sort(key=lambda f: (grades.index(f.grade), order[f.topic]))
    return [f.code for f in picked]
