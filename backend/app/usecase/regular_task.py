"""Сценарии регулярных заданий (mechanics.md, §11): кабинет работодателя — задания, ответы на
свои задания и их оценка; кабинет кандидата — каталог, ответ и свои ответы.

Чужое задание для работодателя не существует — 404, а не 403, как у потребностей. Ответ,
проверенный системой или оценённый автором, сразу пересчитывает профиль навыков кандидата —
той же функцией, что и остановка теста; категорию ответ не трогает.
"""

import uuid
from dataclasses import dataclass

from app.domain.errors import (
    CategoryRequired,
    CompanyRequired,
    TaskAlreadyAnswered,
    TaskAnswerNotFound,
    TaskNotFound,
)
from app.domain.regular_task import (
    CatalogFilter,
    CatalogTask,
    OwnAnswer,
    RegularTask,
    TaskAnswer,
    TaskForm,
    TaskTerms,
    catalog_order,
    pseudonym,
    task_terms,
)
from app.usecase.interface import (
    AttemptRepository,
    CatalogRepository,
    Clock,
    CompanyRepository,
    FspEvidenceReader,
    RegularTaskRepository,
    SkillModel,
    UnitOfWork,
)
from app.usecase.skill_profile import fsp_evidence, refresh_skill_profile
from settings import Mechanics


@dataclass(frozen=True)
class AuthorAnswer:
    """Ответ для автора задания — обезличенно: псевдоним вместо кандидата."""

    answer: TaskAnswer
    pseudonym: str


class RegularTasks:
    def __init__(
        self,
        uow: UnitOfWork,
        tasks: RegularTaskRepository,
        attempts: AttemptRepository,
        catalog: CatalogRepository,
        companies: CompanyRepository,
        fsp: FspEvidenceReader,
        skill_model: SkillModel,
        clock: Clock,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._tasks = tasks
        self._attempts = attempts
        self._catalog = catalog
        self._companies = companies
        self._fsp = fsp
        self._skill_model = skill_model
        self._clock = clock
        self._mechanics = mechanics

    # Работодатель.

    def create(self, author_id: uuid.UUID, form: TaskForm) -> RegularTask:
        """Задание для любой категории; нужен профиль компании."""
        with self._uow:
            if self._companies.get(author_id) is None:
                raise CompanyRequired()
            return self._tasks.add(author_id, self._terms(form), self._clock.now())

    def mine(self, author_id: uuid.UUID) -> list[RegularTask]:
        with self._uow:
            return self._tasks.by_author(author_id)

    def update(self, author_id: uuid.UUID, task_id: uuid.UUID, form: TaskForm) -> RegularTask:
        """Правка — только пока ответов нет; чужое проверяется раньше формы."""
        with self._uow:
            task = self._own(author_id, task_id, lock=True)
            task.ensure_editable()
            self._tasks.replace(task.id, self._terms(form), self._clock.now())
            return self._own(author_id, task_id)

    def withdraw(self, author_id: uuid.UUID, task_id: uuid.UUID) -> RegularTask:
        """Снять из каталога: ответы и оценки по заданию остаются в профилях."""
        with self._uow:
            self._own(author_id, task_id, lock=True)
            self._tasks.withdraw(task_id, self._clock.now())
            return self._own(author_id, task_id)

    def answers(self, author_id: uuid.UUID, task_id: uuid.UUID) -> list[AuthorAnswer]:
        with self._uow:
            task = self._own(author_id, task_id)
            return [
                AuthorAnswer(a, pseudonym(task.id, a.candidate_id))
                for a in self._tasks.answers(task.id)
            ]

    def grade(
        self, author_id: uuid.UUID, task_id: uuid.UUID, answer_id: uuid.UUID, rubric: int
    ) -> AuthorAnswer:
        """Оценка открытого ответа по рубрике 0–3 — один раз; профиль кандидата пересчитывается
        по темам задания."""
        with self._uow:
            self._own(author_id, task_id)
            found = self._tasks.get_answer(answer_id)
            if found is None or found.task_id != task_id:
                raise TaskAnswerNotFound()
            # Блокировки — в том же порядке, что у ответа: кандидат, затем задание.
            self._attempts.lock_candidate(found.candidate_id)
            task = self._own(author_id, task_id, lock=True)
            answer = self._tasks.get_answer(answer_id)
            assert answer is not None
            answer.ensure_gradable(task)
            graded = self._tasks.grade(answer.id, rubric, self._clock.now())
            self._refresh(answer.candidate_id, task.specialization.code)
            return AuthorAnswer(graded, pseudonym(task.id, graded.candidate_id))

    # Кандидат.

    def catalog(self, candidate_id: uuid.UUID, filters: CatalogFilter) -> list[CatalogTask]:
        """Активные задания специализации категории, всех грейдов; только кандидату с
        категорией по тесту."""
        with self._uow:
            specialization = self._category_specialization(candidate_id)
            answered = self._tasks.answered_task_ids(candidate_id)
            tasks = catalog_order(self._tasks.catalog(specialization, filters))
            return [CatalogTask(t, t.id in answered) for t in tasks]

    def answer(self, candidate_id: uuid.UUID, task_id: uuid.UUID, response: str) -> OwnAnswer:
        """Один ответ на задание. С эталоном — проверка системой и пересчёт профиля сразу;
        открытое ждёт оценки автора. Вердикт кандидату не отдаётся."""
        with self._uow:
            self._attempts.lock_candidate(candidate_id)
            specialization = self._category_specialization(candidate_id)
            task = self._tasks.get(task_id, lock=True)
            if task is None or not task.active or task.specialization.code != specialization:
                raise TaskNotFound()
            if self._tasks.answer(task.id, candidate_id) is not None:
                raise TaskAlreadyAnswered()
            answer = self._tasks.add_answer(
                task.id, candidate_id, response, task.check(response), self._clock.now()
            )
            if answer.counted:
                self._refresh(candidate_id, specialization)
            fresh = self._tasks.get(task.id)
            assert fresh is not None
            return OwnAnswer(fresh, answer)

    def own_answers(self, candidate_id: uuid.UUID) -> list[OwnAnswer]:
        with self._uow:
            return self._tasks.own_answers(candidate_id)

    def _own(self, author_id: uuid.UUID, task_id: uuid.UUID, *, lock: bool = False) -> RegularTask:
        task = self._tasks.get(task_id, lock=lock)
        if task is None or task.author_id != author_id:
            raise TaskNotFound()
        return task

    def _category_specialization(self, candidate_id: uuid.UUID) -> str:
        category = self._attempts.state(candidate_id).category
        if category is None:
            raise CategoryRequired()
        return category.specialization.code

    def _terms(self, form: TaskForm) -> TaskTerms:
        return task_terms(
            form,
            self._catalog.specialization(form.specialization),
            self._catalog.grade(form.grade),
        )

    def _refresh(self, candidate_id: uuid.UUID, specialization: str) -> None:
        topics = self._attempts.specialization_topics(specialization)
        if not topics:
            return
        levels = refresh_skill_profile(
            self._attempts,
            self._tasks,
            self._skill_model,
            self._mechanics,
            candidate_id,
            specialization,
            [t.code for t in topics],
            fsp_evidence(self._attempts, self._fsp, candidate_id),
        )
        self._attempts.save_profile(candidate_id, specialization, levels, self._clock.now())
