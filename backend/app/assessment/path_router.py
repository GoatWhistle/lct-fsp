"""Путь кандидата к категории: опрос → грейд → тест → категория. Путь обязательный — пока
категории нет, кабинет кандидата показывает его шаг.

Правил здесь нет: контроллер вызывает сценарии `app.usecase.attempt` и переводит доменные
представления в схемы API.
"""

from fastapi import APIRouter

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
    level_view,
    skill_profile_view,
)
from app.config import Mechanics, MechanicsDep
from app.controller.deps import CandidatePathDep
from app.controller.errors import error_responses
from app.controller.schemas import CatalogRef
from app.domain import errors
from app.domain.attempt import PathView, TestResult
from app.identity.deps import ROLE_RESPONSES, CurrentUser, role_guard
from app.identity.models import Role

router = APIRouter(
    prefix="/api/candidate/path",
    tags=["candidate-path"],
    dependencies=role_guard(Role.candidate),
    responses=ROLE_RESPONSES,
)


@router.get("", summary="Шаг пути к категории и итоги теста")
def get_path(user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep) -> PathOut:
    return _path_out(paths.path(user.id), mechanics)


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
    body: SurveyIn, user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    view = paths.submit_survey(user.id, specialization=body.specialization)
    return _path_out(view, mechanics)


@router.post(
    "/attempts",
    summary="Начать тест на грейд",
    description="На шаге `grade` — тест на заявленный грейд. На шаге `offer` — дотест на "
    "предложенный грейд: он продолжает оценку прошлых ответов.",
    responses=error_responses(errors.StepUnavailable, errors.GradeNotOffered, errors.UnknownGrade),
)
def start_attempt(
    body: AttemptIn, user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    view = paths.start_attempt(user.id, grade=body.grade)
    return _path_out(view, mechanics)


@router.get(
    "/item",
    summary="Текущее задание теста",
    description="Время ответа считается по часам сервера с первого показа задания; повторный "
    "запрос отдаёт то же задание. Эталон и параметры экземпляра не отдаются.",
    responses=error_responses(errors.NoTestInProgress),
)
def get_item(user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep) -> ItemOut:
    item = paths.current_item(user.id)
    return ItemOut(
        id=item.presentation_id,
        number=item.number,
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
    body: AnswerIn, user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    view = paths.answer(user.id, presentation_id=body.presentation_id, response=body.response)
    return _path_out(view, mechanics)


def _path_out(view: PathView, mechanics: Mechanics) -> PathOut:
    return PathOut(
        stage=view.stage,
        survey=SurveyOut.model_validate(view.survey) if view.survey else None,
        attempt=(
            AttemptProgressOut(
                grade=view.progress.grade,
                answered=view.progress.answered,
                max_items=mechanics.test_max_items,
            )
            if view.progress
            else None
        ),
        offer_grade=view.offer_grade,
        retest_after=view.retest_after,
        category=CategoryOut.model_validate(view.category) if view.category else None,
        result=_result_out(view.result) if view.result else None,
        profile=skill_profile_view(view.profile) if view.profile else None,
    )


def _result_out(result: TestResult) -> TestResultOut:
    return TestResultOut(
        grade=result.grade,
        overall=level_view(result.overall),
        grade_probabilities=[
            GradeProbabilityOut(grade=g, probability=p)
            for g, p in result.grade_probabilities.items()
        ],
        grade_up_hint=result.grade_up_hint,
    )
