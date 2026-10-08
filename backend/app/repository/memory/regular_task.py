"""Регулярные задания и ответы в памяти — реализация порта `RegularTaskRepository` для
сценарных тестов и стенда валидации. Идентификаторы — по счётчику: прогон воспроизводим."""

import dataclasses
import uuid
from collections.abc import Sequence
from datetime import datetime

from app.domain.catalog import CatalogRef
from app.domain.errors import TaskAlreadyAnswered
from app.domain.regular_task import (
    AnsweredTask,
    CatalogFilter,
    OwnAnswer,
    RegularTask,
    TaskAnswer,
    TaskTerms,
)
from app.repository.memory.unit_of_work import MemoryStore

TASKS = "regular_tasks"
ANSWERS = "regular_task_answers"


class MemoryRegularTasks:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def answered(self, user_id: uuid.UUID, specialization_code: str) -> Sequence[AnsweredTask]:
        tasks = self._store.collection(TASKS)
        return [
            AnsweredTask(
                grade_code=tasks[a.task_id].grade.code,
                topics=tuple(t.code for t in tasks[a.task_id].topics),
                answered_at=a.answered_at,
                correct=a.correct,
                rubric=a.rubric,
            )
            for a in self._answers()
            if a.candidate_id == user_id
            and tasks[a.task_id].specialization.code == specialization_code
        ]

    def add(self, author_id: uuid.UUID, terms: TaskTerms, now: datetime) -> RegularTask:
        tasks = self._store.collection(TASKS)
        task = RegularTask(
            id=uuid.UUID(int=len(tasks) + 1),
            author_id=author_id,
            specialization=CatalogRef(terms.specialization.code, terms.specialization.name),
            grade=terms.grade,
            kind=terms.kind,
            prompt=terms.prompt,
            topics=terms.topics,
            reference_answer=terms.reference_answer,
            created_at=now,
            updated_at=now,
            withdrawn_at=None,
            answers=0,
        )
        tasks[task.id] = task
        return task

    def get(self, task_id: uuid.UUID, *, lock: bool = False) -> RegularTask | None:
        task: RegularTask | None = self._store.collection(TASKS).get(task_id)
        if task is None:
            return None
        answers = sum(1 for a in self._answers() if a.task_id == task_id)
        return dataclasses.replace(task, answers=answers)

    def replace(self, task_id: uuid.UUID, terms: TaskTerms, now: datetime) -> None:
        tasks = self._store.collection(TASKS)
        tasks[task_id] = dataclasses.replace(
            tasks[task_id],
            specialization=CatalogRef(terms.specialization.code, terms.specialization.name),
            grade=terms.grade,
            kind=terms.kind,
            prompt=terms.prompt,
            topics=terms.topics,
            reference_answer=terms.reference_answer,
            updated_at=now,
        )

    def withdraw(self, task_id: uuid.UUID, now: datetime) -> None:
        tasks = self._store.collection(TASKS)
        if tasks[task_id].withdrawn_at is None:
            tasks[task_id] = dataclasses.replace(tasks[task_id], withdrawn_at=now)

    def by_author(self, author_id: uuid.UUID) -> list[RegularTask]:
        mine = [t for t in self._tasks() if t.author_id == author_id]
        return sorted(mine, key=lambda t: (-t.created_at.timestamp(), t.id.int))

    def catalog(self, specialization_code: str, filters: CatalogFilter) -> list[RegularTask]:
        return [
            t
            for t in self._tasks()
            if t.active
            and t.specialization.code == specialization_code
            and filters.grade in (None, t.grade.code)
            and (filters.topic is None or filters.topic in {r.code for r in t.topics})
        ]

    def answer(self, task_id: uuid.UUID, candidate_id: uuid.UUID) -> TaskAnswer | None:
        return next(
            (a for a in self._answers() if (a.task_id, a.candidate_id) == (task_id, candidate_id)),
            None,
        )

    def add_answer(
        self,
        task_id: uuid.UUID,
        candidate_id: uuid.UUID,
        response: str,
        correct: bool | None,
        now: datetime,
    ) -> TaskAnswer:
        if self.answer(task_id, candidate_id) is not None:
            raise TaskAlreadyAnswered()
        answers = self._store.collection(ANSWERS)
        answer = TaskAnswer(
            id=uuid.UUID(int=len(answers) + 1),
            task_id=task_id,
            candidate_id=candidate_id,
            response=response,
            answered_at=now,
            correct=correct,
            rubric=None,
            graded_at=None,
        )
        answers[answer.id] = answer
        return answer

    def answers(self, task_id: uuid.UUID) -> list[TaskAnswer]:
        return [a for a in self._answers() if a.task_id == task_id]

    def get_answer(self, answer_id: uuid.UUID) -> TaskAnswer | None:
        answer: TaskAnswer | None = self._store.collection(ANSWERS).get(answer_id)
        return answer

    def answered_task_ids(self, candidate_id: uuid.UUID) -> set[uuid.UUID]:
        return {a.task_id for a in self._answers() if a.candidate_id == candidate_id}

    def own_answers(self, candidate_id: uuid.UUID) -> list[OwnAnswer]:
        mine = [a for a in self._answers() if a.candidate_id == candidate_id]
        mine.sort(key=lambda a: (-a.answered_at.timestamp(), a.id.int))
        return [OwnAnswer(self._task(a.task_id), a) for a in mine]

    def grade(self, answer_id: uuid.UUID, rubric: int, now: datetime) -> TaskAnswer:
        answers = self._store.collection(ANSWERS)
        answers[answer_id] = dataclasses.replace(answers[answer_id], rubric=rubric, graded_at=now)
        graded: TaskAnswer = answers[answer_id]
        return graded

    def _task(self, task_id: uuid.UUID) -> RegularTask:
        task = self.get(task_id)
        assert task is not None
        return task

    def _tasks(self) -> list[RegularTask]:
        return [self._task(t.id) for t in self._store.collection(TASKS).values()]

    def _answers(self) -> list[TaskAnswer]:
        """Ответы по времени, при равном — по порядку записи."""
        answers: list[TaskAnswer] = list(self._store.collection(ANSWERS).values())
        return sorted(answers, key=lambda a: (a.answered_at, a.id.int))
