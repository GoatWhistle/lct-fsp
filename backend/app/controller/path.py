"""Путь кандидата к категории: опрос → грейд → тест → категория, затем смена грейда. Путь
обязательный — пока категории нет, кабинет кандидата показывает его шаг.

Правил здесь нет: контроллер вызывает сценарии `app.usecase.attempt` и переводит доменные
представления в схемы API. После ответа он сразу запускает калибровку
(`app.usecase.calibration`) — её сбой пишется в лог, ответ уже зафиксирован (mechanics.md, §7).
"""

import logging

from fastapi import APIRouter

from app.controller.deps import (
    ROLE_RESPONSES,
    AnswerCalibrationDep,
    CandidatePathDep,
    CurrentUser,
    MechanicsDep,
    role_guard,
)
from app.controller.errors import error_responses
from app.controller.path_schemas import (
    AnswerIn,
    AttemptIn,
    AttemptProgressOut,
    CategoryOut,
    ExpressOut,
    GradeProbabilityOut,
    GradeUpOut,
    HistoryEntryOut,
    ItemOut,
    OptionOut,
    PathOut,
    SurveyIn,
    SurveyOut,
    TestResultOut,
    TopicBlockIn,
    TopicBlockOut,
    VerificationOut,
    VerificationProgressOut,
    VerificationResultOut,
    level_view,
    skill_profile_view,
)
from app.controller.schemas import CatalogRef
from app.domain import errors
from app.domain.account import Role
from app.domain.attempt import HistoryEntry, PathView, TestResult, VerificationView
from settings import Mechanics

log = logging.getLogger(__name__)

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
    "предложенный грейд: он продолжает оценку прошлых ответов. На шаге `category` — попытка на "
    "следующий грейд с чистого листа: категория меняется, только если грейд подтверждён. "
    "Раньше срока по правилу ожидания попытка не начинается — ошибка несёт `available_at`.",
    responses=error_responses(
        errors.StepUnavailable,
        errors.GradeNotOffered,
        errors.GradeNotNext,
        errors.GradeChangeTooEarly,
        errors.AttemptInProgress,
        errors.UnknownGrade,
        errors.VerificationPending,
        errors.ExpressUnavailable,
    ),
)
def start_attempt(
    body: AttemptIn, user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    view = paths.start_attempt(
        user.id, grade=body.grade, focus_consent=body.focus_consent, express=body.express
    )
    return _path_out(view, mechanics)


@router.post(
    "/express/continue",
    summary="Продолжить экспресс-тест полным",
    description="Экспресс-тест, дошедший до лимита без уверенности для категории, ждёт "
    "продолжения: лимит снимается, ответы остаются в оценке, тест идёт как обычный.",
    responses=error_responses(errors.ExpressNotPaused),
)
def continue_express(
    user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    return _path_out(paths.continue_full(user.id), mechanics)


@router.post(
    "/step-down",
    summary="Перейти на грейд ниже",
    description="Без теста и без ожидания: уверенность для младшего грейда уже набрана той же "
    "оценкой. Это смена категории — обратно вверх только тестом, после срока ожидания.",
    responses=error_responses(
        errors.StepUnavailable,
        errors.NoLowerGrade,
        errors.AttemptInProgress,
        errors.VerificationPending,
    ),
)
def step_down(user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep) -> PathOut:
    return _path_out(paths.step_down(user.id), mechanics)


@router.post(
    "/topic-block",
    summary="Начать блок по теме",
    description="Короткий адаптивный тест по одной теме категории — ровно `topic_block_items` "
    "заданий. Ответы уточняют профиль навыков; категорию, грейд и сроки смены грейда блок не "
    "меняет. По одной теме — не чаще `topic_block_interval_days` от старта прошлого блока, "
    "брошенного тоже: раньше ошибка несёт `available_at`. Задания — через `/item`, как у теста.",
    responses=error_responses(
        errors.CategoryRequired,
        errors.TopicNotInCategory,
        errors.AttemptInProgress,
        errors.TopicBlockTooEarly,
        errors.StepUnavailable,
    ),
)
def start_topic_block(
    body: TopicBlockIn, user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    return _path_out(paths.start_topic_block(user.id, topic=body.topic), mechanics)


@router.post(
    "/verification",
    summary="Начать проверочный блок",
    description="Короткий блок на время из невиданных заданий тех же тем. Нужен, когда результат "
    "попытки ждёт его: совпал с основным тестом — категория присваивается или повышается с "
    "пометкой «уровень подтверждён», расхождение — категория прежняя, причина числами в "
    "`verification.last`. Без отложенного результата — добровольно, чтобы подтвердить уровень "
    "категории. Срок — `verification_time_limit_minutes` по часам сервера; повтор — не раньше "
    "`verification_retest_days` от старта прошлого блока. Задания — через `/item`.",
    responses=error_responses(
        errors.VerificationUnavailable,
        errors.VerificationTooEarly,
        errors.AttemptInProgress,
    ),
)
def start_verification(
    user: CurrentUser, paths: CandidatePathDep, mechanics: MechanicsDep
) -> PathOut:
    return _path_out(paths.start_verification(user.id), mechanics)


@router.get(
    "/item",
    summary="Текущее задание теста",
    description="Время ответа считается по часам сервера с первого показа задания; повторный "
    "запрос отдаёт то же задание. Эталон и параметры экземпляра не отдаются.",
    responses=error_responses(errors.NoTestInProgress, errors.ExpressPaused),
)
def get_item(user: CurrentUser, paths: CandidatePathDep) -> ItemOut:
    item = paths.current_item(user.id)
    return ItemOut(
        id=item.presentation_id,
        number=item.number,
        max_items=item.max_items,
        topic_block=item.topic_block,
        verification=item.verification,
        deadline=item.deadline,
        focus_consent=item.focus_consent,
        topic=CatalogRef.model_validate(item.topic),
        prompt=item.instance.prompt,
        code=item.instance.code,
        answer_format=item.instance.answer_format,
        options=[OptionOut(letter=o.letter, text=o.text) for o in item.instance.options],
    )


@router.post(
    "/item/answer",
    summary="Ответ на текущее задание",
    description="Ответ проверяет бэкенд; верен ли он, не сообщается. Тест адаптивный: попытка "
    "останавливается, когда уровень определён с нужной точностью или задания кончились, — "
    "тогда возвращается её итог. Ответ проверочного блока после срока не засчитывается: блок "
    "останавливается. Счётчики событий пишутся, только если на попытку дано согласие.",
    responses=error_responses(errors.NoTestInProgress, errors.ItemNotCurrent),
)
def answer_item(
    body: AnswerIn,
    user: CurrentUser,
    paths: CandidatePathDep,
    calibrations: AnswerCalibrationDep,
    mechanics: MechanicsDep,
) -> PathOut:
    answered = paths.answer(
        user.id,
        presentation_id=body.presentation_id,
        response=body.response,
        paste_events=body.paste_events,
        focus_losses=body.focus_losses,
    )
    # Ответы тестового кандидата режима жюри банк заданий не калибруют (mechanics.md, §18).
    if answered.answer is not None and not user.demo:
        try:
            calibrations.calibrate(answered.answer)
        except Exception:
            log.exception(
                "Калибровка после ответа %s не прошла, ответ сохранён", body.presentation_id
            )
    return _path_out(answered.view, mechanics)


def _path_out(view: PathView, mechanics: Mechanics) -> PathOut:
    return PathOut(
        stage=view.stage,
        survey=SurveyOut.model_validate(view.survey) if view.survey else None,
        attempt=(
            AttemptProgressOut(
                grade=view.progress.grade,
                answered=view.progress.answered,
                max_items=view.progress.max_items,
                express=view.progress.express,
            )
            if view.progress
            else None
        ),
        offer_grade=view.offer_grade,
        retest_after=view.retest_after,
        category=CategoryOut.model_validate(view.category) if view.category else None,
        result=_result_out(view.result) if view.result else None,
        profile=skill_profile_view(view.profile) if view.profile else None,
        grade_up=(
            GradeUpOut(grade=view.grade_up.grade, available_at=view.grade_up.available_at)
            if view.grade_up
            else None
        ),
        grade_down=view.grade_down,
        history=[_history_out(entry) for entry in view.history],
        topic_block=(
            TopicBlockOut(
                topic=CatalogRef.model_validate(view.topic_block.topic),
                answered=view.topic_block.answered,
                items=view.topic_block.items,
            )
            if view.topic_block
            else None
        ),
        verification=_verification_out(view.verification) if view.verification else None,
        express=(
            ExpressOut(
                limit=view.express.limit,
                answered=view.express.answered,
                paused=view.express.paused,
            )
            if view.express
            else None
        ),
    )


def _verification_out(view: VerificationView) -> VerificationOut:
    return VerificationOut(
        grade=view.grade,
        available_at=view.available_at,
        progress=(
            VerificationProgressOut(
                answered=view.progress.answered,
                items=view.progress.items,
                deadline=view.progress.deadline,
            )
            if view.progress
            else None
        ),
        last=(
            VerificationResultOut(
                confirmed=view.last.confirmed,
                expected=view.last.expected,
                correct=view.last.correct,
                items=view.last.items,
                at=view.last.at,
            )
            if view.last
            else None
        ),
    )


def _history_out(entry: HistoryEntry) -> HistoryEntryOut:
    return HistoryEntryOut(
        at=entry.at,
        event=entry.event,
        grade=entry.grade,
        purpose=entry.purpose,
        overall=level_view(entry.overall) if entry.overall else None,
        outcome=entry.outcome,
        outcome_grade=entry.outcome_grade,
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
