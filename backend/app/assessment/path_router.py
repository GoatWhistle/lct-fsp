"""Путь кандидата к категории: опрос → грейд → тест → категория. Путь обязательный — пока
категории нет, кабинет кандидата показывает его шаг."""

from fastapi import APIRouter

from app.assessment import service
from app.assessment.determination import grade_probabilities, grade_up_hint
from app.assessment.models import AttemptOutcome, TestAttempt
from app.assessment.schemas import (
    AnswerIn,
    AttemptIn,
    AttemptProgressOut,
    CategoryOut,
    GradeProbabilityOut,
    ItemOut,
    PathOut,
    SurveyIn,
    SurveyOut,
    TestResultOut,
    level_out,
    skill_profile_out,
)
from app.config import Mechanics, MechanicsDep
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.db import DbSession, UnitOfWorkDep, utcnow
from app.domain import errors
from app.domain.skill import Normal
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role

router = APIRouter(
    prefix="/api/candidate/path",
    tags=["candidate-path"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


@router.get("", summary="Шаг пути к категории и итоги теста")
def get_path(user: CurrentUser, db: DbSession, mechanics: MechanicsDep) -> PathOut:
    return _path_out(service.path(db, user.id, utcnow()), mechanics)


@router.post(
    "/survey",
    summary="Опрос: направление — специализация",
    description="«Отрасль» в ТЗ — IT-направление, то есть специализация. Интересные сферы "
    "бизнеса кандидат по желанию отмечает в профиле. Опрос доступен до начала теста, повторный "
    "заменяет прежний.",
    responses=error_responses(
        errors.StepUnavailable,
        errors.UnknownSpecialization,
        errors.SpecializationWithoutTest,
    ),
)
def submit_survey(
    body: SurveyIn, user: CurrentUser, uow: UnitOfWorkDep, mechanics: MechanicsDep
) -> PathOut:
    service.submit_survey(uow, user, specialization=body.specialization, now=utcnow())
    return _path_out(service.path(uow.session, user.id, utcnow()), mechanics)


@router.post(
    "/attempts",
    summary="Начать тест на грейд",
    description="На шаге `grade` — тест на заявленный грейд. На шаге `offer` — дотест на "
    "предложенный грейд: он продолжает оценку прошлых ответов.",
    responses=error_responses(errors.StepUnavailable, errors.GradeNotOffered, errors.UnknownGrade),
)
def start_attempt(
    body: AttemptIn, user: CurrentUser, uow: UnitOfWorkDep, mechanics: MechanicsDep
) -> PathOut:
    service.start_attempt(uow, user, mechanics, grade=body.grade, now=utcnow())
    return _path_out(service.path(uow.session, user.id, utcnow()), mechanics)


@router.get(
    "/item",
    summary="Текущее задание теста",
    description="Время ответа считается по часам сервера с первого показа задания; повторный "
    "запрос отдаёт то же задание. Эталон и параметры экземпляра не отдаются.",
    responses=error_responses(errors.NoTestInProgress),
)
def get_item(user: CurrentUser, uow: UnitOfWorkDep, mechanics: MechanicsDep) -> ItemOut:
    item = service.current_item(uow, user, mechanics, now=utcnow())
    return ItemOut(
        id=item.presentation.id,
        number=item.presentation.position + 1,
        max_items=mechanics.test_max_items,
        topic=CatalogRef.model_validate(item.topic),
        prompt=item.instance.prompt,
        code=item.instance.code,
        options=list(item.instance.options),
    )


@router.post(
    "/item/answer",
    summary="Ответ на текущее задание",
    description="Ответ проверяет бэкенд; верен ли он, не сообщается. Тест адаптивный: попытка "
    "останавливается, когда уровень определён с нужной точностью или задания кончились, — "
    "тогда возвращается её итог.",
    responses=error_responses(errors.NoTestInProgress, errors.ItemNotCurrent),
)
def answer_item(
    body: AnswerIn, user: CurrentUser, uow: UnitOfWorkDep, mechanics: MechanicsDep
) -> PathOut:
    service.answer(
        uow,
        user,
        mechanics,
        presentation_id=body.presentation_id,
        response=body.response,
        now=utcnow(),
    )
    return _path_out(service.path(uow.session, user.id, utcnow()), mechanics)


def _path_out(view: service.PathView, mechanics: Mechanics) -> PathOut:
    attempt = view.attempt
    finished = attempt is not None and attempt.finished_at is not None
    return PathOut(
        stage=view.stage,
        survey=SurveyOut.model_validate(view.survey) if view.survey else None,
        attempt=(
            AttemptProgressOut(
                grade=attempt.grade_code,
                answered=sum(1 for p in attempt.presentations if p.answered_at is not None),
                max_items=mechanics.test_max_items,
            )
            if attempt is not None and not finished
            else None
        ),
        offer_grade=(
            attempt.outcome_grade_code
            if attempt is not None and attempt.outcome == AttemptOutcome.offered
            else None
        ),
        retest_after=attempt.retest_after if attempt is not None else None,
        category=CategoryOut.model_validate(view.category) if view.category else None,
        result=_result_out(attempt, mechanics) if attempt is not None and finished else None,
        profile=skill_profile_out(view.profile, mechanics) if view.profile else None,
    )


def _result_out(attempt: TestAttempt, mechanics: Mechanics) -> TestResultOut:
    assert attempt.overall_theta is not None and attempt.overall_theta_sd is not None
    overall = Normal(attempt.overall_theta, attempt.overall_theta_sd)
    probabilities = grade_probabilities(overall, mechanics.grade_thresholds)
    hint = None
    # Только тому, кто сразу прошёл заявленный грейд: после каскада грейд выше уже не дался.
    passed_claimed = (
        attempt.outcome == AttemptOutcome.assigned
        and attempt.continues_attempt_id is None
        and attempt.outcome_grade_code == attempt.grade_code
    )
    if passed_claimed:
        hint = grade_up_hint(
            overall,
            attempt.grade_code,
            thresholds=mechanics.grade_thresholds,
            confidence=mechanics.grade_up_hint_confidence,
        )
    return TestResultOut(
        grade=attempt.grade_code,
        overall=level_out(overall, mechanics),
        grade_probabilities=[
            GradeProbabilityOut(grade=g, probability=p) for g, p in probabilities.items()
        ],
        grade_up_hint=hint,
    )
