"""Тест по вакансии (mechanics.md, §6): необязательный блок, который работодатель прикладывает к
приглашению. Кандидат проходит его как дополнительный сигнал для этого работодателя — категорию,
грейд и профиль навыков тест не меняет.

План теста — чистая функция потребности: в тест идут ключевые и важные темы, а без них — все темы
специализации; квоты заданий делятся по весам важности методом наибольших остатков, каждой теме —
не меньше `vacancy_test_min_items_per_topic`. Длина фиксированная, как у блока по теме: работодатель
заранее видит, сколько заданий и по каким темам. Внутри темы задание выбирается тем же адаптивным
шагом, что в тесте; тему выбирает недобор квоты.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.catalog import CatalogRef
from app.domain.importance import TopicImportance
from app.domain.selection import NeedSnapshot
from app.domain.skill import Normal, normal_cdf

# Важность, с которой тема попадает в тест; желательные — только когда других нет.
TESTED = (TopicImportance.key, TopicImportance.important)


@dataclass(frozen=True)
class PlannedTopic:
    """Тема теста: важность в потребности, нормированный вес и сколько заданий."""

    topic: CatalogRef
    importance: TopicImportance
    weight: float
    items: int


@dataclass(frozen=True)
class VacancyTestPlan:
    """Темы, квоты и требуемый уровень — порог грейда потребности."""

    specialization: CatalogRef
    grade: CatalogRef
    requirement: float
    topics: tuple[PlannedTopic, ...]

    @property
    def items(self) -> int:
        return sum(t.items for t in self.topics)

    def quotas(self) -> dict[str, int]:
        return {t.topic.code: t.items for t in self.topics}


@dataclass(frozen=True)
class VacancyTest:
    """Тест, приложенный к приглашению: план на момент отправки — правка потребности его не
    меняет."""

    id: uuid.UUID
    invitation_id: uuid.UUID
    need_title: str
    plan: VacancyTestPlan
    created_at: datetime


def vacancy_plan(need: NeedSnapshot, *, total_items: int, min_per_topic: int) -> VacancyTestPlan:
    """План по снимку потребности. Веса тем снимка перенормируются на темы теста. Квоты в сумме —
    `total_items`, но не меньше `min_per_topic` на тему: при большом числе тем тест удлиняется, а
    не теряет тему."""
    tested = [r for r in need.topics if r.importance in TESTED] or list(need.topics)
    norm = sum(r.weight for r in tested)
    shares = [r.weight / norm for r in tested]
    exact = [total_items * share for share in shares]
    counts = [max(min_per_topic, int(x)) for x in exact]
    left = total_items - sum(counts)
    # Наибольшие остатки; ничьи — по порядку тем справочника.
    order = sorted(range(len(tested)), key=lambda i: (-(exact[i] - int(exact[i])), i))
    for i in order[: max(left, 0)]:
        counts[i] += 1
    requirement = tested[0].requirement if tested else 0.0
    return VacancyTestPlan(
        specialization=need.specialization,
        grade=need.grade,
        requirement=requirement,
        topics=tuple(
            PlannedTopic(r.topic, r.importance, round(share, 6), n)
            for r, share, n in zip(tested, shares, counts, strict=True)
        ),
    )


def next_topic(plan: VacancyTestPlan, counts: Mapping[str, int]) -> str | None:
    """Тема следующего задания — с наибольшим недобором квоты; ничьи — по порядку плана. None —
    все квоты выбраны."""
    best: tuple[int, str] | None = None
    for t in plan.topics:
        missing = t.items - counts.get(t.topic.code, 0)
        if missing > 0 and (best is None or missing > best[0]):
            best = (missing, t.topic.code)
    return best[1] if best else None


def example_family(difficulties: Mapping[str, float], requirement: float) -> str | None:
    """Семейство для примера задания: сложность ближе всех к требуемому уровню; ничьи — по коду.
    Два примера по одной вакансии — экземпляры этого семейства с разными seed: задания разные,
    сложность одна."""
    if not difficulties:
        return None
    return min(difficulties, key=lambda code: (abs(difficulties[code] - requirement), code))


@dataclass(frozen=True)
class TopicOutcome:
    """Итог по теме теста: верных из показанных, оценка темы и вероятность выполнить требование."""

    topic: CatalogRef
    weight: float
    answered: int
    correct: int
    level: Normal
    probability: float


@dataclass(frozen=True)
class VacancyTestResult:
    """Итог теста для работодателя: по темам и взвешенная доля выполненных требований — так же,
    как первое слагаемое скора соответствия (§12)."""

    finished_at: datetime
    topics: tuple[TopicOutcome, ...]

    @property
    def match(self) -> float:
        return sum(t.weight * t.probability for t in self.topics)


def vacancy_test_result(
    plan: VacancyTestPlan,
    levels: Mapping[str, Normal],
    answers: Sequence[tuple[str, bool]],
    finished_at: datetime,
) -> VacancyTestResult:
    """Итог по оценкам тем `levels` и ответам теста `answers` — (тема, верно)."""
    outcomes = []
    for planned in plan.topics:
        code = planned.topic.code
        level = levels[code]
        mine = [correct for topic, correct in answers if topic == code]
        outcomes.append(
            TopicOutcome(
                planned.topic,
                planned.weight,
                len(mine),
                sum(mine),
                level,
                normal_cdf((level.mean - plan.requirement) / level.sd),
            )
        )
    return VacancyTestResult(finished_at, tuple(outcomes))
