"""Регулярные задания и ответы в Postgres — реализация портов `RegularTaskReader` и
`RegularTaskRepository`. Изменения не фиксируются — это делает единица работы."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.errors import TaskAlreadyAnswered
from app.domain.regular_task import (
    AnsweredTask,
    CatalogFilter,
    OwnAnswer,
    RegularTask,
    TaskAnswer,
    TaskTerms,
)
from app.repository.catalog import grade_of, ref_of
from app.repository.orm.regular_task import RegularTask as TaskRow
from app.repository.orm.regular_task import RegularTaskAnswer as AnswerRow
from app.repository.orm.regular_task import RegularTaskTopic

_LOADED = (
    selectinload(TaskRow.specialization),
    selectinload(TaskRow.grade),
    selectinload(TaskRow.topics),
)


def _answer_of(row: AnswerRow) -> TaskAnswer:
    return TaskAnswer(
        id=row.id,
        task_id=row.task_id,
        candidate_id=row.candidate_id,
        response=row.response,
        answered_at=row.answered_at,
        correct=row.correct,
        rubric=row.rubric,
        graded_at=row.graded_at,
    )


class SqlRegularTasks:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Порт чтения `RegularTaskReader`.

    def answered(self, user_id: uuid.UUID, specialization_code: str) -> Sequence[AnsweredTask]:
        rows = self._session.execute(
            select(TaskRow, AnswerRow)
            .join(AnswerRow, AnswerRow.task_id == TaskRow.id)
            .where(
                AnswerRow.candidate_id == user_id,
                TaskRow.specialization_code == specialization_code,
            )
            .order_by(AnswerRow.answered_at, AnswerRow.id)
            .options(selectinload(TaskRow.topics))
        ).all()
        return [
            AnsweredTask(
                grade_code=task.grade_code,
                topics=tuple(t.topic_code for t in task.topics),
                answered_at=answer.answered_at,
                correct=answer.correct,
                rubric=answer.rubric,
            )
            for task, answer in rows
        ]

    # Порт записи `RegularTaskRepository`.

    def add(self, author_id: uuid.UUID, terms: TaskTerms, now: datetime) -> RegularTask:
        row = TaskRow(author_id=author_id, created_at=now, withdrawn_at=None)
        self._fill(row, terms, now)
        self._session.add(row)
        self._session.flush()
        task = self.get(row.id)
        assert task is not None
        return task

    def get(self, task_id: uuid.UUID, *, lock: bool = False) -> RegularTask | None:
        if lock:
            self._session.execute(select(TaskRow.id).where(TaskRow.id == task_id).with_for_update())
        rows = self._tasks(select(TaskRow).where(TaskRow.id == task_id))
        return rows[0] if rows else None

    def replace(self, task_id: uuid.UUID, terms: TaskTerms, now: datetime) -> None:
        row = self._session.get_one(TaskRow, task_id)
        row.topics.clear()
        self._session.flush()
        self._fill(row, terms, now)
        self._session.flush()

    def withdraw(self, task_id: uuid.UUID, now: datetime) -> None:
        row = self._session.get_one(TaskRow, task_id)
        if row.withdrawn_at is None:
            row.withdrawn_at = now
        self._session.flush()

    def by_author(self, author_id: uuid.UUID) -> list[RegularTask]:
        return self._tasks(
            select(TaskRow)
            .where(TaskRow.author_id == author_id)
            .order_by(TaskRow.created_at.desc(), TaskRow.id)
        )

    def catalog(self, specialization_code: str, filters: CatalogFilter) -> list[RegularTask]:
        query = select(TaskRow).where(
            TaskRow.specialization_code == specialization_code, TaskRow.withdrawn_at.is_(None)
        )
        if filters.grade is not None:
            query = query.where(TaskRow.grade_code == filters.grade)
        if filters.topic is not None:
            query = query.where(TaskRow.topics.any(RegularTaskTopic.topic_code == filters.topic))
        return self._tasks(query)

    def answer(self, task_id: uuid.UUID, candidate_id: uuid.UUID) -> TaskAnswer | None:
        row = self._session.scalar(
            select(AnswerRow).where(
                AnswerRow.task_id == task_id, AnswerRow.candidate_id == candidate_id
            )
        )
        return _answer_of(row) if row else None

    def add_answer(
        self,
        task_id: uuid.UUID,
        candidate_id: uuid.UUID,
        response: str,
        correct: bool | None,
        now: datetime,
    ) -> TaskAnswer:
        row = AnswerRow(
            task_id=task_id,
            candidate_id=candidate_id,
            response=response,
            answered_at=now,
            correct=correct,
            rubric=None,
            graded_at=None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as exc:
            raise TaskAlreadyAnswered() from exc
        return _answer_of(row)

    def answers(self, task_id: uuid.UUID) -> list[TaskAnswer]:
        rows = self._session.scalars(
            select(AnswerRow)
            .where(AnswerRow.task_id == task_id)
            .order_by(AnswerRow.answered_at, AnswerRow.id)
        )
        return [_answer_of(row) for row in rows]

    def get_answer(self, answer_id: uuid.UUID) -> TaskAnswer | None:
        row = self._session.get(AnswerRow, answer_id)
        return _answer_of(row) if row else None

    def answered_task_ids(self, candidate_id: uuid.UUID) -> set[uuid.UUID]:
        return set(
            self._session.scalars(
                select(AnswerRow.task_id).where(AnswerRow.candidate_id == candidate_id)
            )
        )

    def own_answers(self, candidate_id: uuid.UUID) -> list[OwnAnswer]:
        answers = self._session.scalars(
            select(AnswerRow)
            .where(AnswerRow.candidate_id == candidate_id)
            .order_by(AnswerRow.answered_at.desc(), AnswerRow.id)
        ).all()
        tasks = {
            t.id: t
            for t in self._tasks(
                select(TaskRow).where(TaskRow.id.in_({a.task_id for a in answers}))
            )
        }
        return [OwnAnswer(tasks[a.task_id], _answer_of(a)) for a in answers]

    def grade(self, answer_id: uuid.UUID, rubric: int, now: datetime) -> TaskAnswer:
        row = self._session.get_one(AnswerRow, answer_id)
        row.rubric, row.graded_at = rubric, now
        self._session.flush()
        return _answer_of(row)

    def _fill(self, row: TaskRow, terms: TaskTerms, now: datetime) -> None:
        row.specialization_code = terms.specialization.code
        row.grade_code = terms.grade.code
        row.kind = terms.kind
        row.prompt = terms.prompt
        row.reference_answer = terms.reference_answer
        row.updated_at = now
        row.topics.extend(
            RegularTaskTopic(topic_code=t.code, position=i) for i, t in enumerate(terms.topics)
        )

    def _tasks(self, query: Select[TaskRow]) -> list[RegularTask]:
        rows = self._session.scalars(query.options(*_LOADED)).all()
        counts = dict(
            self._session.execute(
                select(AnswerRow.task_id, func.count())
                .where(AnswerRow.task_id.in_([r.id for r in rows]))
                .group_by(AnswerRow.task_id)
            ).all()
        )
        return [
            RegularTask(
                id=row.id,
                author_id=row.author_id,
                specialization=ref_of(row.specialization),
                grade=grade_of(row.grade),
                kind=row.kind,
                prompt=row.prompt,
                topics=tuple(ref_of(t.topic) for t in row.topics),
                reference_answer=row.reference_answer,
                created_at=row.created_at,
                updated_at=row.updated_at,
                withdrawn_at=row.withdrawn_at,
                answers=counts.get(row.id, 0),
            )
            for row in rows
        ]
