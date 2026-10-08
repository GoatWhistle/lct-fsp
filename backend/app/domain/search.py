"""Фильтры кандидатов и поиск по банку (mechanics.md, §12, «Подборка — объект» и «Поиск по
банку»).

Фильтры — одно правило `admits` для двух путей: поиска по всей базе и уточнения сохранённой
подборки. Форма работодателя и чат-поиск передают одну и ту же структуру `CandidateFilters`.
Фильтр только сужает: места, ранги, скоры и объяснения строк подборки он не трогает.

Поиск по банку — без потребности, поэтому без скора соответствия: внутри категории — по
P(θ̄ ≥ порог грейда категории), выше те, в чьём уровне система увереннее; кандидаты с
заявленным неподтверждённым грейдом — ниже всех подтверждённых.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.domain.candidate import GradeStatus, GradeStatusKind
from app.domain.match import ranking
from app.domain.skill import SkillProfileLevels


@dataclass(frozen=True)
class CategoryFilter:
    specialization: str
    grade: str


@dataclass(frozen=True)
class CandidateFilters:
    """Условия поиска — все необязательны, вместе — пересечение. Пустые фильтры не сужают
    ничего."""

    # Код специализации: категории, у неподтверждённого — цепочки заявленного грейда.
    specialization: str | None = None
    # Код грейда, по которому кандидат в выдаче: категории, у неподтверждённого — заявленный.
    grade: str | None = None
    # Категория по тесту: неподтверждённый грейд её не даёт.
    category: CategoryFilter | None = None
    # Коды технологий: в самоописанном стеке есть хотя бы одна.
    stack: frozenset[str] = frozenset()
    # Есть подтверждённые достижения ФСП.
    fsp_confirmed: bool = False
    # Погрешность общего уровня профиля категории не выше `search_confident_sd`; без категории
    # профиля нет — не проходит.
    confident: bool = False
    # Статус грейда — любой из перечисленных.
    grade_status: frozenset[GradeStatusKind] = frozenset()

    @property
    def empty(self) -> bool:
        return self == NO_FILTERS


NO_FILTERS = CandidateFilters()


@dataclass(frozen=True)
class CandidateFacts:
    """Что фильтры знают о кандидате. Есть только у кандидата со статусом грейда — с категорией
    или заявленным грейдом."""

    candidate_id: uuid.UUID
    # Специализация категории, без неё — цепочки заявленного грейда.
    specialization: str
    status: GradeStatus
    # Самоописанный стек — коды. Скрытый кандидатом из карточки стек пуст: иначе фильтр по
    # технологиям восстановил бы скрытое по одной.
    stack: frozenset[str]
    fsp_confirmed: bool
    # Профиль навыков специализации категории; без категории — нет.
    profile: SkillProfileLevels | None


def admits(filters: CandidateFilters, facts: CandidateFacts, *, confident_sd: float) -> bool:
    """Кандидат проходит все заданные условия."""
    status = facts.status
    grade = status.confirmed or status.claimed
    category = filters.category
    return (
        (filters.specialization is None or facts.specialization == filters.specialization)
        and (filters.grade is None or grade.code == filters.grade)
        and (
            category is None
            or (
                status.confirmed is not None
                and facts.specialization == category.specialization
                and status.confirmed.code == category.grade
            )
        )
        and (not filters.stack or bool(filters.stack & facts.stack))
        and (not filters.fsp_confirmed or facts.fsp_confirmed)
        and (
            not filters.confident
            or (
                status.confirmed is not None
                and facts.profile is not None
                and facts.profile.overall.sd <= confident_sd
            )
        )
        and (not filters.grade_status or status.kind in filters.grade_status)
    )


@dataclass(frozen=True)
class SearchHit:
    facts: CandidateFacts
    # Место в выдаче поиска с 1.
    position: int
    # P(θ̄ ≥ порог грейда категории) — по нему порядок; у неподтверждённого — нет.
    grade_probability: float | None


# Ничьи поиска — по хэшу с постоянной солью: порядок стабилен между запросами и не зависит от
# даты регистрации.
SEARCH_SALT = 0


def search_order(
    found: Iterable[CandidateFacts], thresholds: Mapping[str, float]
) -> list[SearchHit]:
    """Выдача поиска: сначала кандидаты с категорией — категории от старшего грейда к младшему,
    внутри категории по P(θ̄ ≥ порог её грейда); затем — с заявленным неподтверждённым грейдом.
    Вероятности против разных порогов между собой не сравниваются. `thresholds` — пороги
    грейдов: их порядок и есть порядок грейдов."""
    categories: dict[tuple[str, str], dict[uuid.UUID, tuple[CandidateFacts, float | None]]] = {}
    unconfirmed: dict[uuid.UUID, CandidateFacts] = {}
    for facts in found:
        grade = facts.status.confirmed
        if grade is None:
            unconfirmed[facts.candidate_id] = facts
            continue
        profile = facts.profile
        probability = (
            profile.overall.prob_at_least(thresholds[grade.code]) if profile is not None else None
        )
        members = categories.setdefault((facts.specialization, grade.code), {})
        members[facts.candidate_id] = (facts, probability)

    hits: list[SearchHit] = []
    for key in sorted(categories, key=lambda k: (-thresholds[k[1]], k)):
        members = categories[key]
        # Категория без профиля — ниже всех с профилем: уверенности в уровне нет никакой.
        scores = {c: -1.0 if p is None else p for c, (_, p) in members.items()}
        hits.extend(
            SearchHit(members[c][0], n, members[c][1])
            for n, c in enumerate(ranking(scores, SEARCH_SALT), start=len(hits) + 1)
        )
    bottom = ranking(dict.fromkeys(unconfirmed, 0.0), SEARCH_SALT)
    hits.extend(
        SearchHit(unconfirmed[c], n, None) for n, c in enumerate(bottom, start=len(hits) + 1)
    )
    return hits


@dataclass(frozen=True)
class SearchPage:
    filters: CandidateFilters
    # Найдено всего и из них — с неподтверждённым грейдом.
    total: int
    unconfirmed_total: int
    # Страница выдачи с места `offset + 1`.
    hits: tuple[SearchHit, ...]
    offset: int
