"""Пул кандидатов и подборки в Postgres — реализации портов подборки.

Снимок потребности и объяснение лежат в JSONB. Формат задают кодеки этого модуля, а не схемы
API: правка схемы подборки хранимое не меняет, сохранённые подборки открываются без миграции
данных. Правка формата — вместе с миграцией данных.
"""

import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, delete, exists, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from app.domain.candidate import GradeStatus, GradeStatusKind, HideableField, grade_status
from app.domain.catalog import CatalogRef, Grade
from app.domain.errors import SelectionNotFound
from app.domain.feedback import CandidateSelection
from app.domain.importance import TopicImportance
from app.domain.match import Verdict
from app.domain.search import NO_FILTERS, CandidateFacts, CandidateFilters, CategoryFilter
from app.domain.selection import (
    Expectations,
    Explanation,
    NeedRequirement,
    NeedSnapshot,
    PoolCandidate,
    Selection,
    SelectionBlock,
    SelectionDraft,
    SelectionEntry,
    StackExplanation,
    Summary,
    TopicExplanation,
    UnconfirmedCandidate,
)
from app.domain.skill import Normal, SignalSource, SkillProfileLevels
from app.domain.work import SalaryBasis, SalaryRange, WorkFormat
from app.repository.candidate import claimed_grades
from app.repository.fsp import histories
from app.repository.orm.attempt import CandidateCategory, Survey, TestAttempt
from app.repository.orm.candidate import CandidateProfile, candidate_technologies
from app.repository.orm.catalog import Grade as GradeRow
from app.repository.orm.need import Selection as SelectionRow
from app.repository.orm.need import SelectionEntry as EntryRow
from app.repository.orm.need import selection_shortlist
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
                SkillProfileTopic.sources,
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
        fsp_topics: dict[uuid.UUID, set[str]] = {}
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
            sources,
        ) in levels:
            if user_id not in heads:
                heads[user_id] = (
                    Grade(code, name, rank),
                    last_signal_at,
                    Normal(overall, overall_sd),
                )
                topics[user_id], confirmed[user_id], fsp_topics[user_id] = {}, set(), set()
            topics[user_id][topic] = Normal(theta, theta_sd)
            if regular_task:
                confirmed[user_id].add(topic)
            if SignalSource.fsp in sources:
                fsp_topics[user_id].add(topic)

        stacks = self._stacks(reach, technologies)
        expectations = self._expectations(reach)
        claimed = claimed_grades(
            self._session,
            select(CandidateCategory.user_id)
            .join(GradeRow, GradeRow.code == CandidateCategory.grade_code)
            .where(*reach),
        )
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
                claimed=claim.grade if (claim := claimed.get(user_id)) else None,
                fsp_topics=frozenset(fsp_topics[user_id]),
            )
            for user_id, (grade, last_signal_at, overall) in heads.items()
        ]

    def unconfirmed(
        self, specialization: str, grade: str, technologies: Collection[str]
    ) -> list[UnconfirmedCandidate]:
        # Последний опрос — по `specialization`, категории нет.
        later = aliased(Survey)
        surveyed = select(Survey.user_id).where(
            Survey.specialization_code == specialization,
            ~exists().where(later.user_id == Survey.user_id, later.number > Survey.number),
            ~exists().where(CandidateCategory.user_id == Survey.user_id),
        )
        # Заявка — по той же специализации, что опрос: попытка по прошлому опросу не в счёт.
        claimed = {
            user_id: claim.grade
            for user_id, claim in claimed_grades(self._session, surveyed).items()
            if claim.specialization == specialization and claim.grade.code == grade
        }
        stacks: dict[uuid.UUID, set[str]] = {}
        if claimed and technologies:
            for user_id, technology in self._session.execute(
                select(
                    candidate_technologies.c.user_id, candidate_technologies.c.technology_code
                ).where(
                    candidate_technologies.c.user_id.in_(claimed),
                    candidate_technologies.c.technology_code.in_(technologies),
                )
            ):
                stacks.setdefault(user_id, set()).add(technology)
        return [
            UnconfirmedCandidate(user_id, specialization, claim, frozenset(stacks.get(user_id, ())))
            for user_id, claim in claimed.items()
        ]

    def facts(self, candidate_ids: Collection[uuid.UUID]) -> list[CandidateFacts]:
        return self._facts(list(candidate_ids)) if candidate_ids else []

    def searchable(self) -> list[CandidateFacts]:
        # Подзапросом, а не списком id: база не гоняет весь банк через параметры запроса.
        everyone = select(CandidateCategory.user_id).union(select(TestAttempt.user_id))
        return self._facts(select(everyone.subquery().c.user_id))

    def _facts(self, ids: Collection[uuid.UUID] | Select[uuid.UUID]) -> list[CandidateFacts]:
        db = self._session
        categories = {
            user_id: (specialization, Grade(code, name, rank))
            for user_id, specialization, code, name, rank in db.execute(
                select(
                    CandidateCategory.user_id,
                    CandidateCategory.specialization_code,
                    GradeRow.code,
                    GradeRow.name,
                    GradeRow.rank,
                )
                .join(GradeRow, GradeRow.code == CandidateCategory.grade_code)
                .where(CandidateCategory.user_id.in_(ids))
            )
        }
        claims = claimed_grades(db, ids)
        in_category = and_(
            SkillProfile.user_id == CandidateCategory.user_id,
            SkillProfile.specialization_code == CandidateCategory.specialization_code,
        )
        topics: dict[uuid.UUID, dict[str, Normal]] = {}
        for user_id, topic, theta, theta_sd in db.execute(
            select(
                SkillProfile.user_id,
                SkillProfileTopic.topic_code,
                SkillProfileTopic.theta,
                SkillProfileTopic.theta_sd,
            )
            .join(SkillProfileTopic, SkillProfileTopic.profile_id == SkillProfile.id)
            .join(CandidateCategory, in_category)
            .where(SkillProfile.user_id.in_(ids))
        ):
            topics.setdefault(user_id, {})[topic] = Normal(theta, theta_sd)
        profiles = {
            user_id: SkillProfileLevels(
                Normal(theta, theta_sd), topics.get(user_id, {}), 0, last_signal_at
            )
            for user_id, theta, theta_sd, last_signal_at in db.execute(
                select(
                    SkillProfile.user_id,
                    SkillProfile.overall_theta,
                    SkillProfile.overall_theta_sd,
                    SkillProfile.last_signal_at,
                )
                .join(CandidateCategory, in_category)
                .where(SkillProfile.user_id.in_(ids))
            )
        }
        stacks: dict[uuid.UUID, set[str]] = {}
        for user_id, technology in db.execute(
            select(
                candidate_technologies.c.user_id, candidate_technologies.c.technology_code
            ).where(
                candidate_technologies.c.user_id.in_(ids),
                # Скрытый из карточки стек фильтр не видит.
                ~exists().where(
                    CandidateProfile.user_id == candidate_technologies.c.user_id,
                    CandidateProfile.hidden_fields.any_() == HideableField.stack.value,
                ),
            )
        ):
            stacks.setdefault(user_id, set()).add(technology)
        fsp = histories(db, ids)

        found = []
        for user_id in categories.keys() | claims.keys():
            category = categories.get(user_id)
            claim = claims.get(user_id)
            status = grade_status(category[1] if category else None, claim.grade if claim else None)
            if status is None:
                continue
            # Без категории статус есть только с заявкой.
            specialization = category[0] if category else claim.specialization if claim else ""
            history = fsp.get(user_id)
            found.append(
                CandidateFacts(
                    candidate_id=user_id,
                    specialization=specialization,
                    status=status,
                    stack=frozenset(stacks.get(user_id, ())),
                    fsp_confirmed=bool(history and history.achievements),
                    profile=profiles.get(user_id),
                )
            )
        return found

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
            filters=filters_json(NO_FILTERS),
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
                        "grade_status": e.status.kind,
                        "claimed_grade_code": e.status.claimed.code,
                        "claimed_grade_name": e.status.claimed.name,
                        "match_score": e.match_score,
                        "acceptance_probability": e.acceptance_probability,
                        "mutual_score": e.mutual_score,
                        "explanation": explanation_json(e.explanation),
                        "stale": e.stale,
                    }
                    for e in entries
                ],
            )
        return _selection(row, ())

    def get(
        self, user_id: uuid.UUID, selection_id: uuid.UUID
    ) -> tuple[Selection, tuple[SelectionEntry, ...]]:
        row = self._session.get(SelectionRow, selection_id)
        if row is None or row.user_id != user_id:
            raise SelectionNotFound()
        entries = self._session.scalars(
            select(EntryRow).where(EntryRow.selection_id == row.id).order_by(EntryRow.position)
        ).all()
        shortlist = self._shortlists([row.id]).get(row.id, ())
        return _selection(row, shortlist), tuple(_entry(e) for e in entries)

    def save_filters(self, selection_id: uuid.UUID, filters: CandidateFilters) -> None:
        self._session.execute(
            update(SelectionRow)
            .where(SelectionRow.id == selection_id)
            .values(filters=filters_json(filters))
        )

    def set_shortlisted(
        self, selection_id: uuid.UUID, candidate_id: uuid.UUID, shortlisted: bool
    ) -> None:
        if shortlisted:
            self._session.execute(
                pg_insert(selection_shortlist)
                .values(selection_id=selection_id, candidate_id=candidate_id)
                .on_conflict_do_nothing()
            )
        else:
            self._session.execute(
                delete(selection_shortlist).where(
                    selection_shortlist.c.selection_id == selection_id,
                    selection_shortlist.c.candidate_id == candidate_id,
                )
            )

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

    def with_candidate(self, candidate_id: uuid.UUID, since: datetime) -> list[CandidateSelection]:
        own = aliased(EntryRow)
        rows = self._session.execute(
            select(SelectionRow, own.position, own.block)
            .join(own, own.selection_id == SelectionRow.id)
            .where(own.candidate_id == candidate_id, SelectionRow.created_at >= since)
            .order_by(SelectionRow.created_at, SelectionRow.id)
        ).all()
        neighbors: dict[uuid.UUID, list[float]] = {row.id: [] for row, _, _ in rows}
        if neighbors:
            mine = aliased(EntryRow)
            for selection_id, score in self._session.execute(
                select(EntryRow.selection_id, EntryRow.match_score)
                .join(
                    mine,
                    and_(
                        mine.selection_id == EntryRow.selection_id,
                        mine.block == EntryRow.block,
                        mine.candidate_id == candidate_id,
                    ),
                )
                .where(
                    EntryRow.selection_id.in_(neighbors),
                    EntryRow.candidate_id != candidate_id,
                )
            ):
                # Нижний блок скора не имеет.
                if score is not None:
                    neighbors[selection_id].append(score)
        return [
            CandidateSelection(
                selection_id=row.id,
                owner=row.user_id,
                need_id=row.need_id,
                need=snapshot_of(row.need_snapshot),
                stack_cap=row.stack_cap,
                created_at=row.created_at,
                position=position,
                block=block,
                neighbors=tuple(neighbors[row.id]),
            )
            for row, position, block in rows
        ]

    def _summaries(self, rows: Sequence[SelectionRow]) -> list[Summary]:
        totals = {row.id: dict.fromkeys(SelectionBlock, 0) for row in rows}
        counts = self._session.execute(
            select(EntryRow.selection_id, EntryRow.block, func.count())
            .where(EntryRow.selection_id.in_(totals))
            .group_by(EntryRow.selection_id, EntryRow.block)
        ).all()
        for selection_id, block, count in counts:
            totals[selection_id][block] = count
        shortlists = self._shortlists(totals)
        return [
            Summary(_selection(row, shortlists.get(row.id, ())), totals[row.id]) for row in rows
        ]

    def _shortlists(
        self, selection_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[uuid.UUID, ...]]:
        """Шортлисты подборок — в порядке выдачи."""
        listed: dict[uuid.UUID, list[uuid.UUID]] = {}
        for selection_id, candidate_id in self._session.execute(
            select(EntryRow.selection_id, EntryRow.candidate_id)
            .join(
                selection_shortlist,
                and_(
                    selection_shortlist.c.selection_id == EntryRow.selection_id,
                    selection_shortlist.c.candidate_id == EntryRow.candidate_id,
                ),
            )
            .where(EntryRow.selection_id.in_(selection_ids))
            .order_by(EntryRow.selection_id, EntryRow.position)
        ):
            listed.setdefault(selection_id, []).append(candidate_id)
        return {s: tuple(c) for s, c in listed.items()}


def _selection(row: SelectionRow, shortlist: tuple[uuid.UUID, ...]) -> Selection:
    return Selection(
        user_id=row.user_id,
        need_id=row.need_id,
        need=snapshot_of(row.need_snapshot),
        stack_cap=row.stack_cap,
        created_at=row.created_at,
        id=row.id,
        filters=filters_of(row.filters),
        shortlist=shortlist,
    )


def _entry(row: EntryRow) -> SelectionEntry:
    return SelectionEntry(
        candidate_id=row.candidate_id,
        position=row.position,
        block=row.block,
        rank=row.rank,
        status=GradeStatus(
            row.grade_status,
            CatalogRef(row.claimed_grade_code, row.claimed_grade_name),
            None
            if row.grade_status is GradeStatusKind.unconfirmed
            else CatalogRef(row.grade_code, row.grade_name),
        ),
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


def filters_json(filters: CandidateFilters) -> Json:
    """Фильтры подборки в JSONB — только заданные условия: пустые фильтры — `{}`."""
    data: Json = {}
    if filters.specialization is not None:
        data["specialization"] = filters.specialization
    if filters.grade is not None:
        data["grade"] = filters.grade
    if filters.category is not None:
        data["category"] = {
            "specialization": filters.category.specialization,
            "grade": filters.category.grade,
        }
    if filters.stack:
        data["stack"] = sorted(filters.stack)
    if filters.fsp_confirmed:
        data["fsp_confirmed"] = True
    if filters.confident:
        data["confident"] = True
    if filters.grade_status:
        data["grade_status"] = sorted(k.value for k in filters.grade_status)
    return data


def filters_of(data: Json) -> CandidateFilters:
    category = data.get("category")
    return CandidateFilters(
        specialization=data.get("specialization"),
        grade=data.get("grade"),
        category=CategoryFilter(category["specialization"], category["grade"])
        if category
        else None,
        stack=frozenset(data.get("stack", ())),
        fsp_confirmed=data.get("fsp_confirmed", False),
        confident=data.get("confident", False),
        grade_status=frozenset(GradeStatusKind(k) for k in data.get("grade_status", ())),
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
                "fsp_confirmed": t.fsp_confirmed,
            }
            for t in explanation.topics
        ],
        "stack": {
            "matched": list(stack.matched),
            "overlap": float(stack.overlap),
            "contribution": None if stack.contribution is None else float(stack.contribution),
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
                fsp_confirmed=t["fsp_confirmed"],
            )
            for t in data["topics"]
        ),
        stack=StackExplanation(
            tuple(stack["matched"]),
            float(stack["overlap"]),
            None if stack["contribution"] is None else float(stack["contribution"]),
        ),
    )


def _ref_json(ref: CatalogRef) -> Json:
    return {"code": ref.code, "name": ref.name}


def _ref_of(data: Json) -> CatalogRef:
    return CatalogRef(data["code"], data["name"])


def _datetime_json(value: datetime) -> str:
    # Как писала схема API раньше: UTC с «Z».
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
