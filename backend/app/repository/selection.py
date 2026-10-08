"""Пул кандидатов и подборки в Postgres — реализации портов подборки.

Снимок потребности и объяснение лежат в JSONB. Формат задают кодеки этого модуля, а не схемы
API: правка схемы подборки хранимое не меняет, сохранённые подборки открываются без миграции
данных. Правка формата — вместе с миграцией данных.
"""

import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, insert, select
from sqlalchemy.orm import Session

from app.domain.catalog import CatalogRef, Grade
from app.domain.errors import SelectionNotFound
from app.domain.importance import TopicImportance
from app.domain.match import Verdict
from app.domain.selection import (
    Expectations,
    Explanation,
    NeedRequirement,
    NeedSnapshot,
    Page,
    PoolCandidate,
    Selection,
    SelectionBlock,
    SelectionDraft,
    SelectionEntry,
    StackExplanation,
    Summary,
    TopicExplanation,
)
from app.domain.skill import Normal
from app.domain.work import SalaryBasis, SalaryRange, WorkFormat
from app.repository.orm.attempt import CandidateCategory
from app.repository.orm.candidate import CandidateProfile, candidate_technologies
from app.repository.orm.catalog import Grade as GradeRow
from app.repository.orm.need import Selection as SelectionRow
from app.repository.orm.need import SelectionEntry as EntryRow
from app.repository.orm.skill_profile import SkillProfile, SkillProfileTopic

Json = dict[str, Any]


class SqlCandidatePool:
    def __init__(self, session: Session) -> None:
        self._session = session

    def in_reach(
        self, specialization: str, grade_rank: int, distance: int, technologies: Collection[str]
    ) -> list[PoolCandidate]:
        reach = (
            CandidateCategory.specialization_code == specialization,
            GradeRow.rank.between(grade_rank - distance, grade_rank + distance),
        )
        levels = self._session.execute(
            select(
                CandidateCategory.user_id,
                GradeRow.code,
                GradeRow.name,
                GradeRow.rank,
                SkillProfile.last_signal_at,
                SkillProfile.overall_theta,
                SkillProfile.overall_theta_sd,
                SkillProfileTopic.topic_code,
                SkillProfileTopic.theta,
                SkillProfileTopic.theta_sd,
                SkillProfileTopic.regular_task,
            )
            .join(GradeRow, GradeRow.code == CandidateCategory.grade_code)
            .join(
                SkillProfile,
                and_(
                    SkillProfile.user_id == CandidateCategory.user_id,
                    SkillProfile.specialization_code == CandidateCategory.specialization_code,
                ),
            )
            .join(SkillProfileTopic, SkillProfileTopic.profile_id == SkillProfile.id)
            .where(*reach)
        ).all()

        heads: dict[uuid.UUID, tuple[Grade, datetime | None, Normal]] = {}
        topics: dict[uuid.UUID, dict[str, Normal]] = {}
        confirmed: dict[uuid.UUID, set[str]] = {}
        for (
            user_id,
            code,
            name,
            rank,
            last_signal_at,
            overall,
            overall_sd,
            topic,
            theta,
            theta_sd,
            regular_task,
        ) in levels:
            if user_id not in heads:
                heads[user_id] = (
                    Grade(code, name, rank),
                    last_signal_at,
                    Normal(overall, overall_sd),
                )
                topics[user_id], confirmed[user_id] = {}, set()
            topics[user_id][topic] = Normal(theta, theta_sd)
            if regular_task:
                confirmed[user_id].add(topic)

        stacks = self._stacks(reach, technologies)
        expectations = self._expectations(reach)
        return [
            PoolCandidate(
                candidate_id=user_id,
                specialization=specialization,
                grade=grade,
                overall=overall,
                levels=topics[user_id],
                stack=frozenset(stacks.get(user_id, ())),
                last_signal_at=last_signal_at,
                expectations=expectations.get(user_id),
                regular_task_topics=frozenset(confirmed[user_id]),
            )
            for user_id, (grade, last_signal_at, overall) in heads.items()
        ]

    def _stacks(
        self, reach: tuple[ColumnElement[bool], ...], technologies: Collection[str]
    ) -> dict[uuid.UUID, set[str]]:
        if not technologies:
            return {}
        rows = self._session.execute(
            select(candidate_technologies.c.user_id, candidate_technologies.c.technology_code)
            .join(CandidateCategory, CandidateCategory.user_id == candidate_technologies.c.user_id)
            .join(GradeRow, GradeRow.code == CandidateCategory.grade_code)
            .where(*reach, candidate_technologies.c.technology_code.in_(technologies))
        ).all()
        stacks: dict[uuid.UUID, set[str]] = {}
        for user_id, technology in rows:
            stacks.setdefault(user_id, set()).add(technology)
        return stacks

    def _expectations(
        self, reach: tuple[ColumnElement[bool], ...]
    ) -> dict[uuid.UUID, Expectations]:
        rows = self._session.execute(
            select(
                CandidateProfile.user_id,
                CandidateProfile.salary_from,
                CandidateProfile.work_formats,
                CandidateProfile.city,
                CandidateProfile.relocation,
            )
            .join(CandidateCategory, CandidateCategory.user_id == CandidateProfile.user_id)
            .join(GradeRow, GradeRow.code == CandidateCategory.grade_code)
            .where(*reach)
        ).all()
        return {
            user_id: Expectations(
                salary_from, tuple(WorkFormat(f) for f in formats), city, relocation
            )
            for user_id, salary_from, formats, city, relocation in rows
        }


class SqlSelections:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: SelectionDraft, entries: Sequence[SelectionEntry]) -> Selection:
        row = SelectionRow(
            user_id=draft.user_id,
            need_id=draft.need_id,
            need_snapshot=snapshot_json(draft.need),
            stack_cap=draft.stack_cap,
            created_at=draft.created_at,
        )
        self._session.add(row)
        self._session.flush()
        if entries:
            self._session.execute(
                insert(EntryRow),
                [
                    {
                        "selection_id": row.id,
                        "position": e.position,
                        "candidate_id": e.candidate_id,
                        "block": e.block,
                        "rank": e.rank,
                        "grade_code": e.grade.code,
                        "grade_name": e.grade.name,
                        "match_score": e.match_score,
                        "acceptance_probability": e.acceptance_probability,
                        "mutual_score": e.mutual_score,
                        "explanation": explanation_json(e.explanation),
                        "stale": e.stale,
                    }
                    for e in entries
                ],
            )
        return _selection(row)

    def page(self, user_id: uuid.UUID, selection_id: uuid.UUID, *, offset: int, limit: int) -> Page:
        row = self._session.get(SelectionRow, selection_id)
        if row is None or row.user_id != user_id:
            raise SelectionNotFound()
        entries = self._session.scalars(
            select(EntryRow)
            .where(EntryRow.selection_id == row.id)
            .order_by(EntryRow.position)
            .offset(offset)
            .limit(limit)
        ).all()
        (summary,) = self._summaries([row])
        return Page(summary.selection, summary.totals, tuple(_entry(e) for e in entries), offset)

    def summaries(
        self, user_id: uuid.UUID, need_id: uuid.UUID | None, *, limit: int
    ) -> list[Summary]:
        query = select(SelectionRow).where(SelectionRow.user_id == user_id)
        if need_id is not None:
            query = query.where(SelectionRow.need_id == need_id)
        rows = self._session.scalars(
            query.order_by(SelectionRow.created_at.desc(), SelectionRow.id).limit(limit)
        )
        return self._summaries(list(rows))

    def _summaries(self, rows: Sequence[SelectionRow]) -> list[Summary]:
        totals = {row.id: dict.fromkeys(SelectionBlock, 0) for row in rows}
        counts = self._session.execute(
            select(EntryRow.selection_id, EntryRow.block, func.count())
            .where(EntryRow.selection_id.in_(totals))
            .group_by(EntryRow.selection_id, EntryRow.block)
        ).all()
        for selection_id, block, count in counts:
            totals[selection_id][block] = count
        return [Summary(_selection(row), totals[row.id]) for row in rows]


def _selection(row: SelectionRow) -> Selection:
    return Selection(
        user_id=row.user_id,
        need_id=row.need_id,
        need=snapshot_of(row.need_snapshot),
        stack_cap=row.stack_cap,
        created_at=row.created_at,
        id=row.id,
    )


def _entry(row: EntryRow) -> SelectionEntry:
    return SelectionEntry(
        candidate_id=row.candidate_id,
        position=row.position,
        block=row.block,
        rank=row.rank,
        grade=CatalogRef(row.grade_code, row.grade_name),
        match_score=row.match_score,
        acceptance_probability=row.acceptance_probability,
        mutual_score=row.mutual_score,
        explanation=explanation_of(row.explanation),
        stale=row.stale,
    )


def snapshot_json(snapshot: NeedSnapshot) -> Json:
    """Снимок потребности в JSONB. Ключи и формат — как у подборок, сохранённых раньше."""
    salary = snapshot.salary
    return {
        "title": snapshot.title,
        "specialization": _ref_json(snapshot.specialization),
        "grade": _ref_json(snapshot.grade),
        "stack": [_ref_json(t) for t in snapshot.stack],
        "work_format": snapshot.work_format.value,
        "city": snapshot.city,
        "salary_from": salary.low if salary else None,
        "salary_to": salary.high if salary else None,
        "topics": [
            {
                "topic": _ref_json(t.topic),
                "importance": t.importance.value,
                "edited": t.edited,
                "weight": float(t.weight),
                "requirement": float(t.requirement),
            }
            for t in snapshot.topics
        ],
        "updated_at": _datetime_json(snapshot.updated_at),
        "salary_basis": SalaryBasis.gross.value,
    }


def snapshot_of(data: Json) -> NeedSnapshot:
    return NeedSnapshot(
        title=data["title"],
        specialization=_ref_of(data["specialization"]),
        grade=_ref_of(data["grade"]),
        stack=tuple(_ref_of(t) for t in data["stack"]),
        work_format=WorkFormat(data["work_format"]),
        city=data["city"],
        salary=SalaryRange.optional(data["salary_from"], data["salary_to"]),
        topics=tuple(
            NeedRequirement(
                topic=_ref_of(t["topic"]),
                importance=TopicImportance(t["importance"]),
                edited=t["edited"],
                weight=float(t["weight"]),
                requirement=float(t["requirement"]),
            )
            for t in data["topics"]
        ),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def explanation_json(explanation: Explanation) -> Json:
    """Объяснение в JSONB: коды тем и технологий, названия — из снимка."""
    stack = explanation.stack
    return {
        "topics": [
            {
                "topic": t.topic,
                "theta": float(t.theta),
                "theta_sd": float(t.theta_sd),
                "probability": float(t.probability),
                "contribution": float(t.contribution),
                "verdict": t.verdict.value,
                "low_data": t.low_data,
                "regular_task": t.regular_task,
            }
            for t in explanation.topics
        ],
        "stack": {
            "matched": list(stack.matched),
            "overlap": float(stack.overlap),
            "contribution": float(stack.contribution),
        },
    }


def explanation_of(data: Json) -> Explanation:
    stack = data["stack"]
    return Explanation(
        topics=tuple(
            TopicExplanation(
                topic=t["topic"],
                theta=float(t["theta"]),
                theta_sd=float(t["theta_sd"]),
                probability=float(t["probability"]),
                contribution=float(t["contribution"]),
                verdict=Verdict(t["verdict"]),
                low_data=t["low_data"],
                regular_task=t["regular_task"],
            )
            for t in data["topics"]
        ),
        stack=StackExplanation(
            tuple(stack["matched"]), float(stack["overlap"]), float(stack["contribution"])
        ),
    )


def _ref_json(ref: CatalogRef) -> Json:
    return {"code": ref.code, "name": ref.name}


def _ref_of(data: Json) -> CatalogRef:
    return CatalogRef(data["code"], data["name"])


def _datetime_json(value: datetime) -> str:
    # Как писала схема API раньше: UTC с «Z».
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
