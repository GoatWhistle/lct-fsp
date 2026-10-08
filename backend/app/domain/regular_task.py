"""Регулярное задание работодателя и ответ кандидата (mechanics.md, §11).

Работодатель публикует задание для категории — специализация × грейд — и отмечает 1–3 темы
специализации. Кандидат с категорией берёт задания своей специализации любого грейда из каталога
и отвечает на каждое один раз. Задание с эталоном проверяет система, как семейства банка;
открытое оценивает по рубрике 0–3 автор задания. Ответ — наблюдения уровня по темам задания
на четвёртом уровне доверия; категорию и грейд он не меняет.
"""

import enum
import hashlib
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from app.domain.bank.family import same_answer
from app.domain.catalog import CatalogRef, Grade, Specialization
from app.domain.errors import (
    AnswerAlreadyGraded,
    ReferenceAnswerMismatch,
    TaskLocked,
    TaskNotGradable,
    TaskTopicNotInSpecialization,
    TaskTopicsCount,
    UnknownGrade,
    UnknownSpecialization,
)
from app.domain.skill import Observation, SignalSource

MIN_TOPICS, MAX_TOPICS = 1, 3
# Длины текстов: условие, эталон — короткая строка или число, ответ.
PROMPT_MAX, REFERENCE_MAX, RESPONSE_MAX = 4000, 200, 4000
# Ступени рубрики: r ≥ 1, r ≥ 2, r = 3.
RUBRIC_STEPS = (1, 2, 3)
# Оценка от «верно в целом» — подтверждение уровня в объяснении подборки.
CONFIRMING = 2

# Ошибки формы задания — в порядке проверки.
TASK_FORM_ERRORS = (
    UnknownSpecialization,
    UnknownGrade,
    TaskTopicsCount,
    TaskTopicNotInSpecialization,
    ReferenceAnswerMismatch,
)


class TaskKind(enum.StrEnum):
    # С эталоном — короткая строка или число; проверяет система.
    reference = "reference"
    # Открытое — скрипт, бизнес-решение; оценивает автор по рубрике 0–3.
    open = "open"


@dataclass(frozen=True)
class TaskForm:
    """Задание, как его прислал работодатель: справочники — кодами."""

    specialization: str
    grade: str
    kind: TaskKind
    prompt: str
    topics: tuple[str, ...]
    reference_answer: str | None


@dataclass(frozen=True)
class TaskTerms:
    """Проверенное задание — то, что хранится."""

    specialization: Specialization
    grade: Grade
    kind: TaskKind
    prompt: str
    # В порядке, в котором их отметил работодатель.
    topics: tuple[CatalogRef, ...]
    reference_answer: str | None


def task_terms(
    form: TaskForm, specialization: Specialization | None, grade: Grade | None
) -> TaskTerms:
    """Правила формы: справочники найдены, 1–3 разные темы специализации задания, эталон — у
    задания с эталоном и только у него."""
    if specialization is None:
        raise UnknownSpecialization()
    if grade is None:
        raise UnknownGrade()
    codes = list(dict.fromkeys(form.topics))
    if not MIN_TOPICS <= len(codes) <= MAX_TOPICS:
        raise TaskTopicsCount()
    known = {t.code: t for t in specialization.topics}
    if any(code not in known for code in codes):
        raise TaskTopicNotInSpecialization()
    reference = (form.reference_answer or "").strip() or None
    if (form.kind == TaskKind.reference) != (reference is not None):
        raise ReferenceAnswerMismatch()
    return TaskTerms(
        specialization=specialization,
        grade=grade,
        kind=form.kind,
        prompt=form.prompt,
        topics=tuple(CatalogRef(known[c].code, known[c].name) for c in codes),
        reference_answer=reference,
    )


@dataclass(frozen=True)
class RegularTask:
    id: uuid.UUID
    author_id: uuid.UUID
    specialization: CatalogRef
    grade: Grade
    kind: TaskKind
    prompt: str
    topics: tuple[CatalogRef, ...]
    # Только для автора и проверки: кандидату эталон не уходит.
    reference_answer: str | None
    created_at: datetime
    updated_at: datetime
    # Снято из каталога; ответы и оценки по нему остаются в профилях.
    withdrawn_at: datetime | None
    answers: int

    @property
    def active(self) -> bool:
        return self.withdrawn_at is None

    @property
    def editable(self) -> bool:
        """После первого ответа задание неизменяемо: ответ уже оценивается по этому условию."""
        return self.active and self.answers == 0

    def ensure_editable(self) -> None:
        if not self.editable:
            raise TaskLocked()

    def check(self, response: str) -> bool | None:
        """Вердикт системы по ответу — у задания с эталоном; открытое ждёт оценки автора."""
        if self.kind == TaskKind.reference:
            assert self.reference_answer is not None
            return same_answer(response, self.reference_answer)
        return None


@dataclass(frozen=True)
class TaskAnswer:
    id: uuid.UUID
    task_id: uuid.UUID
    candidate_id: uuid.UUID
    response: str
    answered_at: datetime
    # Вердикт системы — у задания с эталоном.
    correct: bool | None
    # Оценка автора по рубрике 0–3 — у открытого, после оценки.
    rubric: int | None
    graded_at: datetime | None

    def ensure_gradable(self, task: RegularTask) -> None:
        """Оценивает только открытое задание, один раз."""
        if task.kind != TaskKind.open:
            raise TaskNotGradable()
        if self.rubric is not None:
            raise AnswerAlreadyGraded()

    @property
    def counted(self) -> bool:
        """Ответ уже вошёл в профиль: проверен системой или оценён автором."""
        return self.correct is not None or self.rubric is not None


@dataclass(frozen=True)
class OwnAnswer:
    """Ответ кандидата для него самого — с заданием. Вердикт системы и оценку автора кандидату
    не показывают: видно только, принят ли ответ и оценён ли."""

    task: RegularTask
    answer: TaskAnswer


@dataclass(frozen=True)
class AnsweredTask:
    """Ответ кандидата с тем, что нужно для наблюдений: грейд и темы задания."""

    grade_code: str
    topics: tuple[str, ...]
    answered_at: datetime
    correct: bool | None
    rubric: int | None

    @property
    def counted(self) -> bool:
        """Ответ входит в профиль: проверен системой или оценён автором."""
        return self.correct is not None or self.rubric is not None

    @property
    def confirms(self) -> bool:
        """Ответ подтверждает уровень по темам задания: верен или оценён «верно в целом» и
        выше. Неверный ответ тоже сужает погрешность, но подтверждением его не назвать."""
        return self.correct is True or (self.rubric is not None and self.rubric >= CONFIRMING)


@dataclass(frozen=True)
class TaskRules:
    """Параметры регулярных заданий из `config/mechanics.yaml`."""

    # `grade_thresholds` — сложность ступеней от порога грейда задания.
    thresholds: Mapping[str, float]
    # `regular_task_rubric_offsets`.
    rubric_offsets: Mapping[int, float]
    # `regular_task_discrimination`.
    discrimination: float
    # `trust_weight_regular_task`.
    weight: float


def task_observations(answer: AnsweredTask, rules: TaskRules) -> list[Observation]:
    """Наблюдения уровня по каждой теме задания (§11). Сложность — от порога $c_g$ грейда
    задания, а не кандидата. С эталоном — одна бинарная ступень сложности $c_g$; открытое —
    три ступени $r \\ge 1$, $r \\ge 2$, $r = 3$ со смещениями рубрики. Без вердикта и без оценки
    наблюдений нет."""
    threshold = rules.thresholds[answer.grade_code]
    if answer.correct is not None:
        steps = [(answer.correct, threshold)]
    elif answer.rubric is not None:
        steps = [(answer.rubric >= k, threshold + rules.rubric_offsets[k]) for k in RUBRIC_STEPS]
    else:
        return []
    return [
        Observation(
            topic=topic,
            correct=correct,
            discrimination=rules.discrimination,
            difficulty=difficulty,
            weight=rules.weight,
            source=SignalSource.regular_task,
            at=answer.answered_at,
        )
        for correct, difficulty in steps
        for topic in answer.topics
    ]


@dataclass(frozen=True)
class CatalogFilter:
    grade: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class CatalogTask:
    """Задание в каталоге кандидата: без эталона и автора; `answered` — кандидат уже ответил."""

    task: RegularTask
    answered: bool


def catalog_order(tasks: Collection[RegularTask]) -> list[RegularTask]:
    """Сначала задания с меньшим числом ответов, при равенстве — новые."""
    return sorted(tasks, key=lambda t: (t.answers, -t.created_at.timestamp(), t.id.int))


def pseudonym(task_id: uuid.UUID, candidate_id: uuid.UUID) -> str:
    """Псевдоним кандидата для автора задания — свой в каждом задании: ответы на разные задания
    автора не сводятся в одного человека."""
    digest = hashlib.sha256(task_id.bytes + candidate_id.bytes).hexdigest()
    return f"Кандидат {digest[:6].upper()}"
