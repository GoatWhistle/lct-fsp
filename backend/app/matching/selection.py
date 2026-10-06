"""Подборка по потребности (mechanics.md, §12): кто попадает, скор, порядок и сохранение.

Категория отсекает: в подборку попадают только кандидаты с категорией по тесту — точные
(специализация и грейд потребности) и «близкие» (грейд на `nearby_grade_distance` от грейда
потребности). Внутри блока порядок — по взаимному скору: соответствие × P(принятия). Пока модели
принятия нет, P(принятия) не считается и множитель равен 1.

Подборка сохраняется целиком — снимок потребности и выдача со скорами и вкладами — и потом
открывается с той же выдачей. Работодатель видит только свои подборки: чужая — 404.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, insert, select
from sqlalchemy.orm import Session, selectinload

from app.assessment.models import CandidateCategory, Grade
from app.assessment.schemas import CatalogRef
from app.config import Mechanics
from app.db import utcnow
from app.errors import AppError
from app.matching.models import Need, Selection, SelectionBlock, SelectionEntry
from app.matching.schemas import (
    Explanation,
    NeedSnapshot,
    RequirementOut,
    StackFitData,
    TopicFitData,
)
from app.matching.score import Match, Requirement, match_score, ranking, requirements, verdict
from app.matching.service import get_need, need_topics
from app.profile.models import candidate_technologies
from app.skills.irt import Normal
from app.skills.models import SkillProfile, SkillProfileTopic


class SelectionNotFound(AppError):
    status_code = 404
    code = "selection_not_found"
    message = "Подборка не найдена"


@dataclass(frozen=True)
class Page:
    selection: Selection
    need: NeedSnapshot
    entries: list[SelectionEntry]
    offset: int


@dataclass
class _Candidate:
    user_id: uuid.UUID
    grade_code: str
    block: SelectionBlock
    last_signal_at: datetime | None
    levels: dict[str, Normal]


def build(
    db: Session, user_id: uuid.UUID, need_id: uuid.UUID, mechanics: Mechanics, *, limit: int
) -> Page:
    """Строит подборку по текущей потребности и профилям навыков и сохраняет её."""
    need = get_need(db, user_id, need_id)
    snapshot = need_snapshot(need, mechanics)
    need_reqs = [Requirement(t.topic.code, t.weight, t.requirement) for t in snapshot.topics]
    need_stack = [t.code for t in snapshot.stack]
    pool = _pool(db, need, mechanics)
    stacks = _stacks(db, need, need_stack)
    now = utcnow()

    selection = Selection(
        id=uuid.uuid4(),
        user_id=user_id,
        need_id=need.id,
        need_snapshot=snapshot.model_dump(mode="json"),
        stack_cap=mechanics.self_reported_stack_cap,
        exact_total=sum(c.block == SelectionBlock.exact for c in pool),
        nearby_total=sum(c.block == SelectionBlock.nearby for c in pool),
        created_at=now,
    )
    matches = {
        c.user_id: match_score(
            need_reqs,
            c.levels,
            need_stack,
            stacks[c.user_id],
            stack_cap=mechanics.self_reported_stack_cap,
        )
        for c in pool
    }
    # Модель принятия (§13) ещё не обучена: P(принятия) нет, множитель 1.
    acceptance: dict[uuid.UUID, float | None] = dict.fromkeys(matches)
    mutual = {c: _mutual(m.score, acceptance[c]) for c, m in matches.items()}

    by_id = {c.user_id: c for c in pool}
    rows: list[dict[str, Any]] = []
    for block in SelectionBlock:
        scores = {c.user_id: mutual[c.user_id] for c in pool if c.block == block}
        for rank, candidate_id in enumerate(ranking(scores, selection.id), start=1):
            candidate = by_id[candidate_id]
            rows.append(
                {
                    "selection_id": selection.id,
                    "position": len(rows) + 1,
                    "candidate_id": candidate_id,
                    "block": block,
                    "rank": rank,
                    "grade_code": candidate.grade_code,
                    "match_score": matches[candidate_id].score,
                    "acceptance_probability": acceptance[candidate_id],
                    "mutual_score": mutual[candidate_id],
                    "explanation": _explanation(matches[candidate_id], mechanics).model_dump(
                        mode="json"
                    ),
                    "stale": _stale(candidate.last_signal_at, now, mechanics),
                }
            )

    db.add(selection)
    db.flush()
    if rows:
        db.execute(insert(SelectionEntry), rows)
    db.commit()
    return get_page(db, user_id, selection.id, offset=0, limit=limit)


def get_page(
    db: Session, user_id: uuid.UUID, selection_id: uuid.UUID, *, offset: int, limit: int
) -> Page:
    selection = db.get(Selection, selection_id)
    if selection is None or selection.user_id != user_id:
        raise SelectionNotFound()
    entries = db.scalars(
        select(SelectionEntry)
        .where(SelectionEntry.selection_id == selection.id)
        .options(selectinload(SelectionEntry.grade))
        .order_by(SelectionEntry.position)
        .offset(offset)
        .limit(limit)
    ).all()
    return Page(selection, snapshot_of(selection), list(entries), offset)


def list_selections(db: Session, user_id: uuid.UUID, need_id: uuid.UUID | None) -> list[Selection]:
    query = select(Selection).where(Selection.user_id == user_id)
    if need_id is not None:
        query = query.where(Selection.need_id == need_id)
    return list(db.scalars(query.order_by(Selection.created_at.desc())))


def snapshot_of(selection: Selection) -> NeedSnapshot:
    return NeedSnapshot.model_validate(selection.need_snapshot)


def need_snapshot(need: Need, mechanics: Mechanics) -> NeedSnapshot:
    """Потребность с весами тем и требованиями: требуемый уровень у всех тем — порог грейда."""
    views = need_topics(need, mechanics)
    reqs = requirements(
        [(view.topic.code, view.importance) for view in views],
        requirement=mechanics.grade_thresholds[need.grade_code],
        importance_weights=mechanics.need_importance_weights,
    )
    return NeedSnapshot(
        title=need.title,
        specialization=CatalogRef.model_validate(need.specialization),
        grade=CatalogRef.model_validate(need.grade),
        stack=[CatalogRef.model_validate(t) for t in need.stack],
        work_format=need.work_format,
        city=need.city,
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        topics=[
            RequirementOut(
                topic=CatalogRef.model_validate(view.topic),
                importance=view.importance,
                edited=view.edited,
                weight=req.weight,
                requirement=req.level,
            )
            for view, req in zip(views, reqs, strict=True)
        ],
        updated_at=need.updated_at,
    )


def _pool(db: Session, need: Need, mechanics: Mechanics) -> list[_Candidate]:
    """Кандидаты с категорией специализации потребности и грейдом не дальше
    `nearby_grade_distance` — с уровнями по темам из профиля навыков этой специализации."""
    distance = mechanics.nearby_grade_distance
    rows = db.execute(
        select(
            CandidateCategory.user_id,
            CandidateCategory.grade_code,
            Grade.rank,
            SkillProfile.last_signal_at,
            SkillProfileTopic.topic_code,
            SkillProfileTopic.theta,
            SkillProfileTopic.theta_sd,
        )
        .join(Grade, Grade.code == CandidateCategory.grade_code)
        .join(
            SkillProfile,
            and_(
                SkillProfile.user_id == CandidateCategory.user_id,
                SkillProfile.specialization_code == CandidateCategory.specialization_code,
            ),
        )
        .join(SkillProfileTopic, SkillProfileTopic.profile_id == SkillProfile.id)
        .where(
            CandidateCategory.specialization_code == need.specialization_code,
            Grade.rank.between(need.grade.rank - distance, need.grade.rank + distance),
        )
    ).all()

    pool: dict[uuid.UUID, _Candidate] = {}
    for user_id, grade_code, rank, last_signal_at, topic, theta, theta_sd in rows:
        if user_id not in pool:
            block = SelectionBlock.exact if rank == need.grade.rank else SelectionBlock.nearby
            pool[user_id] = _Candidate(user_id, grade_code, block, last_signal_at, {})
        pool[user_id].levels[topic] = Normal(theta, theta_sd)
    return list(pool.values())


def _stacks(db: Session, need: Need, need_stack: list[str]) -> defaultdict[uuid.UUID, set[str]]:
    """Технологии потребности в самоописании кандидатов её специализации."""
    stacks: defaultdict[uuid.UUID, set[str]] = defaultdict(set)
    if not need_stack:
        return stacks
    rows = db.execute(
        select(candidate_technologies.c.user_id, candidate_technologies.c.technology_code)
        .join(CandidateCategory, CandidateCategory.user_id == candidate_technologies.c.user_id)
        .where(
            CandidateCategory.specialization_code == need.specialization_code,
            candidate_technologies.c.technology_code.in_(need_stack),
        )
    ).all()
    for user_id, technology in rows:
        stacks[user_id].add(technology)
    return stacks


def _explanation(match: Match, mechanics: Mechanics) -> Explanation:
    return Explanation(
        topics=[
            TopicFitData(
                topic=fit.topic,
                theta=fit.level.mean,
                theta_sd=fit.level.sd,
                probability=fit.probability,
                contribution=fit.contribution,
                verdict=verdict(fit.probability, mechanics.confidence_language_bands),
                low_data=fit.level.sd > mechanics.topic_low_data_sd,
            )
            for fit in match.topics
        ],
        stack=StackFitData(
            matched=list(match.stack.matched),
            overlap=match.stack.overlap,
            contribution=match.stack.contribution,
        ),
    )


def _mutual(score: float, acceptance: float | None) -> float:
    return score if acceptance is None else score * acceptance


def _stale(last_signal_at: datetime | None, now: datetime, mechanics: Mechanics) -> bool:
    return last_signal_at is None or now - last_signal_at > timedelta(
        days=mechanics.profile_stale_days
    )
