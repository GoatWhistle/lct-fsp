"""Подборка по потребности (mechanics.md, §12–13): кто попадает, в какой блок, скор, объяснение и
порядок.

Категория отсекает: в подборку попадают только кандидаты с категорией по тесту — точные
(специализация и грейд потребности) и «близкие» (грейд на `nearby_grade_distance` от грейда
потребности). Блоки идут в порядке `BLOCK_ORDER`, внутри блока — по взаимному скору S × P.
P(принятия) приходит снаружи, из модели принятия; скор, вклады и их сумма считаются здесь, и
модель на них не влияет: сумма вкладов равна S при любой P.

Подборка — снимок потребности и выдача на момент построения. Хранится и открывается позже с той
же выдачей; перестроение — новая подборка.
"""

import enum
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.catalog import CatalogRef, Grade, Specialization, Technology
from app.domain.importance import TopicImportance, topic_importance
from app.domain.match import (
    Match,
    Requirement,
    Verdict,
    match_score,
    ranking,
    requirements,
    verdict,
)
from app.domain.skill import Normal
from app.domain.work import SalaryRange, WorkFormat


class SelectionBlock(enum.StrEnum):
    # Категория кандидата — специализация и грейд потребности.
    exact = "exact"
    # Та же специализация, грейд на `nearby_grade_distance` от грейда потребности.
    nearby = "nearby"


# Блоки выдачи сверху вниз. Блок неподтверждённого грейда встанет последним: он никогда не выше
# подтверждённых (docs/adr/0001-layers-and-ports.md).
BLOCK_ORDER: tuple[SelectionBlock, ...] = (SelectionBlock.exact, SelectionBlock.nearby)


def block_of(need_rank: int, candidate_rank: int, distance: int) -> SelectionBlock | None:
    """Досягаемость по рангу грейда: тот же грейд — точные, не дальше `distance` — близкие,
    дальше — мимо подборки."""
    gap = abs(candidate_rank - need_rank)
    if gap == 0:
        return SelectionBlock.exact
    if gap <= distance:
        return SelectionBlock.nearby
    return None


@dataclass(frozen=True)
class Need:
    """Потребность, как её ввёл работодатель: стек с темами технологий и правки важности."""

    id: uuid.UUID
    title: str
    specialization: Specialization
    grade: Grade
    # По названию технологии.
    stack: tuple[Technology, ...]
    # Код темы → важность, которую работодатель поставил сам.
    edited_importance: Mapping[str, TopicImportance]
    work_format: WorkFormat
    city: str | None
    salary: SalaryRange | None
    updated_at: datetime


@dataclass(frozen=True)
class NeedRequirement:
    topic: CatalogRef
    importance: TopicImportance
    # Важность поставил работодатель, а не вывод из стека.
    edited: bool
    # Вес темы в скоре — вес важности, нормированный на сумму.
    weight: float
    # Требуемый уровень θ — порог грейда потребности.
    requirement: float


@dataclass(frozen=True)
class NeedSnapshot:
    """Потребность на момент построения подборки — с весами и требованиями по темам."""

    title: str
    specialization: CatalogRef
    grade: CatalogRef
    stack: tuple[CatalogRef, ...]
    work_format: WorkFormat
    city: str | None
    salary: SalaryRange | None
    # Все темы специализации по порядку.
    topics: tuple[NeedRequirement, ...]
    # Версия потребности, по которой построена подборка.
    updated_at: datetime


def need_snapshot(
    need: Need,
    *,
    requirement: float,
    importance_weights: Mapping[str, float],
    key_min_technologies: int,
) -> NeedSnapshot:
    """Снимок потребности: важность тем — из стека и правок, требуемый уровень у всех тем —
    `requirement`, порог грейда потребности."""
    topics = need.specialization.topics
    rows = topic_importance(
        [t.code for t in topics],
        {tech.code: set(tech.topics) for tech in need.stack},
        need.edited_importance,
        key_min_technologies=key_min_technologies,
    )
    reqs = requirements(
        [(row.topic, row.importance) for row in rows],
        requirement=requirement,
        importance_weights=importance_weights,
    )
    return NeedSnapshot(
        title=need.title,
        specialization=CatalogRef(need.specialization.code, need.specialization.name),
        grade=CatalogRef(need.grade.code, need.grade.name),
        stack=tuple(CatalogRef(t.code, t.name) for t in need.stack),
        work_format=need.work_format,
        city=need.city,
        salary=need.salary,
        topics=tuple(
            NeedRequirement(
                CatalogRef(topic.code, topic.name),
                row.importance,
                row.edited,
                req.weight,
                req.level,
            )
            for topic, row, req in zip(topics, rows, reqs, strict=True)
        ),
        updated_at=need.updated_at,
    )


@dataclass(frozen=True)
class Expectations:
    """Ожидания из самоописания кандидата — вход модели принятия. Ожидаемая зарплата
    работодателю не показывается никогда (§13)."""

    # Ожидаемая зарплата «от».
    salary_from: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool


@dataclass(frozen=True)
class PoolCandidate:
    """Кандидат с категорией по тесту — то, из чего подборка строит место в выдаче."""

    candidate_id: uuid.UUID
    specialization: str
    grade: Grade
    # Тема → уровень из профиля навыков категории; тем, добавленных после пересчёта, нет.
    levels: Mapping[str, Normal]
    # Технологии потребности в самоописанном стеке — коды; остальные подборке не нужны.
    stack: frozenset[str]
    last_signal_at: datetime | None
    # Без заполненного профиля кандидата ожиданий нет.
    expectations: Expectations | None


@dataclass(frozen=True)
class SelectionRules:
    """Параметры подборки из `config/mechanics.yaml`."""

    # λ — потолок вклада самоописания.
    stack_cap: float
    nearby_grade_distance: int
    # `confidence_language_bands`.
    verdict_bands: tuple[float, ...]
    # `topic_low_data_sd`.
    low_data_sd: float
    # `profile_stale_days`.
    stale_after: timedelta
    # Уровень по теме, которой нет в профиле: тему добавили в справочник, а профиль пересчитается
    # со следующим сигналом. До тех пор — априорный (§3) с поправкой погрешности, «данных мало».
    missing_level: Normal


@dataclass(frozen=True)
class Scored:
    candidate: PoolCandidate
    block: SelectionBlock
    match: Match


def score(
    need: NeedSnapshot, need_rank: int, pool: Iterable[PoolCandidate], rules: SelectionRules
) -> list[Scored]:
    """Блок и скор соответствия каждого досягаемого кандидата; кандидаты другой специализации и
    дальше `nearby_grade_distance` отсекаются, что бы ни отдал пул."""
    reqs = [Requirement(t.topic.code, t.weight, t.requirement) for t in need.topics]
    need_stack = [t.code for t in need.stack]
    scored = []
    for candidate in pool:
        block = block_of(need_rank, candidate.grade.rank, rules.nearby_grade_distance)
        if block is None or candidate.specialization != need.specialization.code:
            continue
        levels = {r.topic: candidate.levels.get(r.topic, rules.missing_level) for r in reqs}
        match = match_score(reqs, levels, need_stack, candidate.stack, stack_cap=rules.stack_cap)
        scored.append(Scored(candidate, block, match))
    return scored


@dataclass(frozen=True)
class AcceptanceFeatures:
    """Признаки модели принятия (§13), для которых сейчас есть данные. Пола, возраста и вуза
    нет по построению (§17): их нет ни здесь, ни в профиле кандидата."""

    # Вилка потребности; может отсутствовать.
    salary: SalaryRange | None
    # Ожидаемая зарплата кандидата «от»; нет — профиль не заполнен.
    expected_salary: int | None
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool | None
    need_work_format: WorkFormat
    need_city: str | None
    # Код грейда категории кандидата.
    grade: str
    # S — скор соответствия.
    match_score: float


def acceptance_features(need: NeedSnapshot, scored: Scored) -> AcceptanceFeatures:
    expectations = scored.candidate.expectations
    return AcceptanceFeatures(
        salary=need.salary,
        expected_salary=expectations.salary_from if expectations else None,
        work_formats=expectations.work_formats if expectations else (),
        city=expectations.city if expectations else None,
        relocation=expectations.relocation if expectations else None,
        need_work_format=need.work_format,
        need_city=need.city,
        grade=scored.candidate.grade.code,
        match_score=scored.match.score,
    )


def mutual_score(match: float, acceptance: float | None) -> float:
    """S × P; без P(принятия) — множитель 1, а не выдуманные 100 %."""
    if acceptance is None:
        return match
    if not 0.0 <= acceptance <= 1.0:
        raise ValueError(f"P(принятия) вне [0, 1]: {acceptance}")
    return match * acceptance


@dataclass(frozen=True)
class TopicExplanation:
    """Вклад темы — код темы; названия берутся из снимка потребности."""

    topic: str
    theta: float
    theta_sd: float
    probability: float
    contribution: float
    verdict: Verdict
    # Погрешность выше `topic_low_data_sd`.
    low_data: bool


@dataclass(frozen=True)
class StackExplanation:
    # Технологии потребности в самоописании кандидата.
    matched: tuple[str, ...]
    overlap: float
    contribution: float


@dataclass(frozen=True)
class Explanation:
    """Вклады слагаемых скора: их сумма равна S."""

    topics: tuple[TopicExplanation, ...]
    stack: StackExplanation


def explain(match: Match, rules: SelectionRules) -> Explanation:
    return Explanation(
        topics=tuple(
            TopicExplanation(
                topic=fit.topic,
                theta=fit.level.mean,
                theta_sd=fit.level.sd,
                probability=fit.probability,
                contribution=fit.contribution,
                verdict=verdict(fit.probability, rules.verdict_bands),
                low_data=fit.level.sd > rules.low_data_sd,
            )
            for fit in match.topics
        ),
        stack=StackExplanation(match.stack.matched, match.stack.overlap, match.stack.contribution),
    )


@dataclass(frozen=True)
class SelectionEntry:
    """Кандидат в выдаче: место, скоры и вклады на момент построения."""

    candidate_id: uuid.UUID
    # Место в общей выдаче с 1 — по порядку блоков.
    position: int
    block: SelectionBlock
    # Место внутри блока с 1.
    rank: int
    # Грейд категории кандидата — со снимком названия.
    grade: CatalogRef
    match_score: float
    # None — модели принятия нет, множитель 1.
    acceptance_probability: float | None
    mutual_score: float
    explanation: Explanation
    # Последний сигнал профиля старше `profile_stale_days`.
    stale: bool


def arrange(
    scored: Sequence[Scored],
    acceptance: Sequence[float | None],
    *,
    salt: int,
    now: datetime,
    rules: SelectionRules,
) -> list[SelectionEntry]:
    """Выдача: блоки в порядке `BLOCK_ORDER`, внутри блока — по S × P, ничьи — по соли.
    `acceptance` — P(принятия) по порядку `scored`."""
    if len(acceptance) != len(scored):
        raise ValueError("P(принятия) — по одной на кандидата")
    blocks: defaultdict[SelectionBlock, dict[uuid.UUID, tuple[Scored, float | None]]]
    blocks = defaultdict(dict)
    for item, probability in zip(scored, acceptance, strict=True):
        blocks[item.block][item.candidate.candidate_id] = (item, probability)

    entries: list[SelectionEntry] = []
    for block in BLOCK_ORDER:
        members = blocks.pop(block, {})
        mutual = {c: mutual_score(item.match.score, p) for c, (item, p) in members.items()}
        for rank, candidate_id in enumerate(ranking(mutual, salt), start=1):
            item, probability = members[candidate_id]
            grade = item.candidate.grade
            entries.append(
                SelectionEntry(
                    candidate_id=candidate_id,
                    position=len(entries) + 1,
                    block=block,
                    rank=rank,
                    grade=CatalogRef(grade.code, grade.name),
                    match_score=item.match.score,
                    acceptance_probability=probability,
                    mutual_score=mutual[candidate_id],
                    explanation=explain(item.match, rules),
                    stale=is_stale(item.candidate.last_signal_at, now, rules.stale_after),
                )
            )
    if blocks:
        raise ValueError(f"блоков нет в BLOCK_ORDER: {sorted(blocks)}")
    return entries


def is_stale(last_signal_at: datetime | None, now: datetime, stale_after: timedelta) -> bool:
    return last_signal_at is None or now - last_signal_at > stale_after


def block_totals(entries: Iterable[SelectionEntry]) -> dict[SelectionBlock, int]:
    """Кандидатов в каждом блоке — нули у пустых блоков."""
    counts = Counter(e.block for e in entries)
    return {block: counts[block] for block in BLOCK_ORDER}


@dataclass(frozen=True)
class SelectionDraft:
    """Подборка до сохранения — без id: его даёт хранилище."""

    user_id: uuid.UUID
    # None — потребность удалена: подборка открывается по снимку.
    need_id: uuid.UUID | None
    need: NeedSnapshot
    # λ на момент построения.
    stack_cap: float
    created_at: datetime


@dataclass(frozen=True)
class Selection(SelectionDraft):
    id: uuid.UUID


@dataclass(frozen=True)
class Summary:
    selection: Selection
    # Кандидатов в каждом блоке — по строкам выдачи: кандидат, удаливший учётку, уходит из
    # подборки целиком.
    totals: Mapping[SelectionBlock, int]


@dataclass(frozen=True)
class Page(Summary):
    # Страница общей выдачи с места `offset + 1`.
    entries: tuple[SelectionEntry, ...]
    offset: int
