"""Сценарии теста по вакансии (mechanics.md, §6): превью для работодателя, старт кандидатом из
приглашения и итог для пригласившей компании.

Превью показывает, как система формирует тест по потребности: темы с весами, сколько заданий по
каждой и пример экземпляра на тему. Пример — экземпляр семейства, сложность которого ближе всех к
требуемому уровню, со свежим seed: два превью одной вакансии дают разные задания одной
сложности. Эталон в превью не уходит, показом превью не считается — окно показов и калибровку оно
не трогает.

Задания теста выбирает путь кандидата (`app.usecase.attempt`) — тем же адаптивным шагом, что в
тесте. Итог видит только пригласившая компания; в профиль навыков, категорию и грейд он не входит.
"""

import enum
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from app.domain import bank
from app.domain.attempt import Attempt, AttemptPurpose
from app.domain.bank.runner import CodeRunner
from app.domain.errors import (
    AttemptInProgress,
    CategoryRequired,
    InvitationNotFound,
    VacancyTestClosed,
    VacancyTestNotFound,
    VacancyTestSpecializationMismatch,
    VacancyTestTaken,
)
from app.domain.invitation import InvitationStatus
from app.domain.selection import Need, need_snapshot
from app.domain.skill import Observation
from app.domain.vacancy_test import (
    PlannedTopic,
    VacancyTest,
    VacancyTestPlan,
    VacancyTestResult,
    example_family,
    vacancy_plan,
    vacancy_test_result,
)
from app.usecase.interface import (
    AttemptRepository,
    Calibration,
    Clock,
    InvitationRepository,
    NeedReader,
    SeedSource,
    SkillModel,
    UnitOfWork,
    VacancyTestRepository,
)
from app.usecase.skill_profile import specialization_prior
from settings import Mechanics


def plan_of_need(need: Need, mechanics: Mechanics) -> VacancyTestPlan:
    """План теста по потребности: важность и веса тем — как у подборки (§12)."""
    snapshot = need_snapshot(
        need,
        requirement=mechanics.grade_thresholds[need.grade.code],
        importance_weights=mechanics.need_importance_weights,
        key_min_technologies=mechanics.need_key_topic_min_technologies,
    )
    return vacancy_plan(
        snapshot,
        total_items=mechanics.vacancy_test_items,
        min_per_topic=mechanics.vacancy_test_min_items_per_topic,
    )


@dataclass(frozen=True)
class Example:
    """Пример задания темы: экземпляр без эталона и сложность его семейства."""

    topic: PlannedTopic
    family_code: str
    difficulty: float
    instance: bank.Instance


@dataclass(frozen=True)
class VacancyTestPreview:
    plan: VacancyTestPlan
    examples: tuple[Example, ...]


class VacancyTestStatus(enum.StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    finished = "finished"


@dataclass(frozen=True)
class VacancyTestView:
    """Тест приглашения: план, ход и — только для работодателя — итог."""

    test: VacancyTest
    status: VacancyTestStatus
    answered: int
    result: VacancyTestResult | None


class VacancyTests:
    def __init__(
        self,
        uow: UnitOfWork,
        needs: NeedReader,
        tests: VacancyTestRepository,
        invitations: InvitationRepository,
        attempts: AttemptRepository,
        calibration: Calibration,
        skill_model: SkillModel,
        clock: Clock,
        seeds: SeedSource,
        runner: CodeRunner,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._needs = needs
        self._tests = tests
        self._invitations = invitations
        self._attempts = attempts
        self._calibration = calibration
        self._skill_model = skill_model
        self._clock = clock
        self._seeds = seeds
        self._runner = runner
        self._mechanics = mechanics

    def preview(self, employer_id: uuid.UUID, need_id: uuid.UUID) -> VacancyTestPreview:
        """Темы, задания по темам и пример экземпляра на тему; чужая потребность —
        `NeedNotFound`."""
        with self._uow:
            plan = plan_of_need(self._needs.get(employer_id, need_id), self._mechanics)
            examples = []
            for planned in plan.topics:
                params = self._calibration.current(bank.families_for_topics([planned.topic.code]))
                code = example_family(
                    {c: p.difficulty for c, p in params.items()}, plan.requirement
                )
                if code is None:
                    continue
                family = bank.get_family(code)
                instance = family.instance(self._seeds.seed(), self._runner)
                examples.append(Example(planned, code, params[code].difficulty, instance))
            return VacancyTestPreview(plan, tuple(examples))

    def start(self, candidate_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        """Тест из приглашения: пока приглашение не отклонено и не истекло, один раз. Начатый и
        брошенный тест продолжается с того же задания — путём кандидата."""
        with self._uow:
            self._attempts.lock_candidate(candidate_id)
            now = self._clock.now()
            invitation = self._invitations.get(invitation_id)
            if invitation is None or invitation.candidate_id != candidate_id:
                raise InvitationNotFound()
            test = self._tests.by_invitations([invitation_id]).get(invitation_id)
            if test is None:
                raise VacancyTestNotFound()
            if self._attempts.vacancy_attempts([test.id]).get(test.id) is not None:
                raise VacancyTestTaken()
            current = invitation.at(now, self._invitation_ttl())
            if current.status in (InvitationStatus.declined, InvitationStatus.expired):
                raise VacancyTestClosed()
            if self._attempts.attempt_in_progress(candidate_id) is not None:
                raise AttemptInProgress()
            state = self._attempts.state(candidate_id)
            if state.category is None or state.survey is None:
                raise CategoryRequired()
            if state.survey.specialization_code != test.plan.specialization.code:
                raise VacancyTestSpecializationMismatch()
            self._attempts.add_attempt(
                candidate_id,
                state.survey,
                state.category.grade.code,
                None,
                now,
                AttemptPurpose.vacancy_test,
                vacancy_test_id=test.id,
            )

    def views(
        self, invitation_ids: Sequence[uuid.UUID], *, with_result: bool
    ) -> dict[uuid.UUID, VacancyTestView]:
        """Тесты приглашений по id приглашения; итог — только с `with_result` (работодателю)."""
        with self._uow:
            tests = self._tests.by_invitations(invitation_ids)
            attempts = self._attempts.vacancy_attempts([t.id for t in tests.values()])
            return {
                invitation_id: self._view(test, attempts.get(test.id), with_result=with_result)
                for invitation_id, test in tests.items()
            }

    def _view(
        self, test: VacancyTest, attempt: Attempt | None, *, with_result: bool
    ) -> VacancyTestView:
        if attempt is None:
            return VacancyTestView(test, VacancyTestStatus.not_started, 0, None)
        answered = attempt.answered_count
        if attempt.finished_at is None:
            return VacancyTestView(test, VacancyTestStatus.in_progress, answered, None)
        result = self._result(test, attempt) if with_result else None
        return VacancyTestView(test, VacancyTestStatus.finished, answered, result)

    def _result(self, test: VacancyTest, attempt: Attempt) -> VacancyTestResult:
        """Итог — чистая функция записей: оценка тем по ответам теста по вакансии и ответам
        кандидата по специализации до его остановки."""
        assert attempt.finished_at is not None
        finished = attempt.finished_at
        topics = self._attempts.specialization_topics(attempt.specialization_code) or ()
        prior = specialization_prior([t.code for t in topics], self._mechanics)
        mine = [p for p in attempt.presentations if p.answered_at is not None]
        observations: list[Observation] = [
            o.observation()
            for o in self._attempts.answered(attempt.user_id, attempt.specialization_code)
            if o.answered_at <= finished
        ]
        observations += [p.answered().observation() for p in mine]
        estimate = self._skill_model.estimate(prior, observations)
        levels = {t.topic.code: estimate.topic(t.topic.code) for t in test.plan.topics}
        answers = [(p.topic_code, bool(p.correct)) for p in mine]
        return vacancy_test_result(test.plan, levels, answers, finished)

    def _invitation_ttl(self) -> timedelta:
        return timedelta(days=self._mechanics.invitation_ttl_days)
