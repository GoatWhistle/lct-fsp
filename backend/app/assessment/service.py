"""Путь кандидата к категории: опрос → грейд → тест → оценка → категория (mechanics.md, §4, §6).

Опрос — направление: специализация справочника, «отрасль» в ТЗ. Сферы бизнеса в опрос не
входят — это необязательное предпочтение в профиле кандидата.

Состояние пути выводится из записей: последний опрос, последняя попытка, категория. Состояние
попытки — список предъявлений, оценка — чистая функция от него, поэтому прерванный тест
продолжается с того же места после перезапуска бэкенда. Следующее задание выбирается
адаптивно при показе.
"""

import enum
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment import bank, families
from app.assessment.adaptive import Blueprint, choose, selection_prior, should_stop
from app.assessment.calibration import rest_levels
from app.assessment.determination import Assign, Offer, decide
from app.assessment.models import (
    AttemptOutcome,
    CandidateCategory,
    Presentation,
    Specialization,
    Survey,
    TestAttempt,
    Topic,
)
from app.config import Mechanics
from app.errors import AppError
from app.identity.models import User
from app.skills.irt import Observation, Prior, estimate
from app.skills.models import SkillProfile
from app.skills.service import presentation_observation, refresh_profile, specialization_prior

log = logging.getLogger(__name__)
# Случайный выбор из top-k: по нему никто не должен угадать следующее семейство.
_rng = secrets.SystemRandom()


class UnknownIndustry(AppError):
    status_code = 422
    code = "unknown_industry"
    message = "Такой сферы бизнеса нет в справочнике"


class UnknownSpecialization(AppError):
    status_code = 422
    code = "unknown_specialization"
    message = "Такой специализации нет в справочнике"


class SpecializationWithoutTest(AppError):
    status_code = 422
    code = "specialization_without_test"
    message = "Тест по этой специализации ещё готовится — выберите другую"


class UnknownGrade(AppError):
    status_code = 422
    code = "unknown_grade"
    message = "Такого грейда нет в справочнике"


class StepUnavailable(AppError):
    status_code = 409
    code = "path_step_unavailable"
    message = "Этот шаг сейчас недоступен — обновите страницу"


class GradeNotOffered(AppError):
    status_code = 409
    code = "grade_not_offered"
    message = "Продолжить можно только на предложенном грейде"


class NoTestInProgress(AppError):
    status_code = 409
    code = "no_test_in_progress"
    message = "Сейчас нет начатого теста"


class ItemNotCurrent(AppError):
    status_code = 409
    code = "item_not_current"
    message = "Это задание уже не текущее — обновите страницу"


class Stage(enum.StrEnum):
    survey = "survey"
    grade = "grade"
    test = "test"
    offer = "offer"
    category = "category"
    no_category = "no_category"


@dataclass(frozen=True)
class PathView:
    stage: Stage
    survey: Survey | None
    # Начатая попытка на шаге test, последняя законченная — на шагах offer, category, no_category.
    attempt: TestAttempt | None
    category: CandidateCategory | None
    profile: SkillProfile | None


@dataclass(frozen=True)
class Item:
    presentation: Presentation
    instance: bank.Instance
    topic: Topic


def path(db: Session, user_id: uuid.UUID, now: datetime) -> PathView:
    category = db.get(CandidateCategory, user_id)
    survey = db.scalar(
        select(Survey).where(Survey.user_id == user_id).order_by(Survey.number.desc()).limit(1)
    )
    attempt = db.scalar(
        select(TestAttempt)
        .where(TestAttempt.user_id == user_id)
        .order_by(TestAttempt.number.desc())
        .limit(1)
    )

    if category is not None:
        stage = Stage.category
    elif attempt is not None and attempt.finished_at is None:
        stage = Stage.test
    elif attempt is not None and attempt.outcome == AttemptOutcome.offered:
        stage = Stage.offer
    elif (
        attempt is not None
        and attempt.outcome == AttemptOutcome.no_category
        and attempt.retest_after is not None
        and now < attempt.retest_after
    ):
        stage = Stage.no_category
    elif survey is None:
        stage = Stage.survey
    else:
        stage = Stage.grade

    profile = None
    if attempt is not None:
        profile = db.scalar(
            select(SkillProfile).where(
                SkillProfile.user_id == user_id,
                SkillProfile.specialization_code == attempt.specialization_code,
            )
        )
    if stage in (Stage.survey, Stage.grade):
        attempt = None
    return PathView(stage, survey, attempt, category, profile)


def submit_survey(db: Session, user: User, *, specialization: str, now: datetime) -> None:
    _lock(db, user)
    if path(db, user.id, now).stage not in (Stage.survey, Stage.grade):
        raise StepUnavailable()
    if db.get(Specialization, specialization) is None:
        raise UnknownSpecialization()
    if not bank.covers(_topics(db, specialization)):
        raise SpecializationWithoutTest()
    db.add(
        Survey(
            user_id=user.id,
            number=_next_number(db, Survey, user.id),
            specialization_code=specialization,
            created_at=now,
        )
    )
    db.commit()


def start_attempt(
    db: Session, user: User, mechanics: Mechanics, *, grade: str, now: datetime
) -> None:
    """Тест на заявленный грейд или дотест каскада на предложенный."""
    _lock(db, user)
    if grade not in mechanics.grade_thresholds:
        raise UnknownGrade()
    view = path(db, user.id, now)
    if view.stage == Stage.grade and view.survey is not None:
        survey, continues = view.survey, None
    elif view.stage == Stage.offer and view.attempt is not None:
        if grade != view.attempt.outcome_grade_code:
            raise GradeNotOffered()
        survey, continues = db.get_one(Survey, view.attempt.survey_id), view.attempt
    else:
        raise StepUnavailable()

    attempt = TestAttempt(
        user_id=user.id,
        number=_next_number(db, TestAttempt, user.id),
        survey_id=survey.id,
        specialization_code=survey.specialization_code,
        grade_code=grade,
        continues_attempt_id=continues.id if continues else None,
        started_at=now,
    )
    db.add(attempt)
    db.flush()
    if not _remaining(db, attempt, mechanics):
        _finish(db, attempt, mechanics, now)
    db.commit()


def current_item(db: Session, user: User, mechanics: Mechanics, *, now: datetime) -> Item:
    """Текущее задание попытки. Предъявление создаётся при первом показе — с него идут часы
    ответа; повторный запрос отдаёт то же задание и часы не сбрасывает.

    Следующее семейство выбирает адаптивный тест (§6) по оценке с априорным средним в пороге
    грейда попытки; экземпляр всегда новый, со свежим seed.
    """
    _lock(db, user)
    attempt = _attempt_in_progress(db, user.id)
    presentation = _pending(attempt)
    if presentation is None:
        presentation = _present(db, attempt, mechanics, now)
        db.commit()
    family = bank.get_family(presentation.family_code)
    topic = db.get_one(Topic, presentation.topic_code)
    return Item(presentation, family.instance(presentation.seed), topic)


def answer(
    db: Session,
    user: User,
    mechanics: Mechanics,
    *,
    presentation_id: uuid.UUID,
    response: str,
    now: datetime,
) -> None:
    """Проверка ответа на бэкенде; верность на фронт не уходит. После ответа — шаг Эло по
    семейству и проверка остановки: точность набрана или спрашивать больше нечего. После
    остановки — пересчёт связки шкалы и пакетная переоценка семейств, набравших ответы (§7)."""
    _lock(db, user)
    attempt = _attempt_in_progress(db, user.id)
    presentation = _pending(attempt)
    if presentation is None or presentation.id != presentation_id:
        raise ItemNotCurrent()
    family = bank.get_family(presentation.family_code)
    presentation.response = response
    presentation.correct = family.check(family.instance(presentation.seed), response)
    presentation.answered_at = now
    # Часы сервера при синхронизации отходят назад на секунды — время ответа не уходит в минус.
    elapsed = (now - presentation.shown_at).total_seconds()
    presentation.response_time_ms = max(0, round(elapsed * 1000))
    families.learn(db, presentation, mechanics)

    prior = _prior(db, attempt, mechanics)
    overall = estimate(prior, _observations(db, attempt)).overall()
    blueprint = Blueprint.from_prior(prior, mechanics)
    stop = should_stop(blueprint, _counts(attempt), overall)
    if stop or not _remaining(db, attempt, mechanics):
        _finish(db, attempt, mechanics, now)
    db.commit()
    if attempt.finished_at is not None:
        specialization = attempt.specialization_code
        families.relink(db, specialization, mechanics, now)
        families.refit_due(
            db, [p.family_code for p in attempt.presentations], specialization, mechanics, now
        )


def _present(
    db: Session, attempt: TestAttempt, mechanics: Mechanics, now: datetime
) -> Presentation:
    prior = _prior(db, attempt, mechanics)
    observations = _observations(db, attempt)
    threshold = mechanics.grade_thresholds[attempt.grade_code]
    selection = estimate(selection_prior(prior, threshold), observations)
    options, exposure = families.options(db, attempt, _bank(prior), mechanics)
    blueprint = Blueprint.from_prior(prior, mechanics)
    choice = choose(blueprint, _counts(attempt), selection, options, exposure, _rng)
    if choice is None:
        # Ответ останавливает попытку, когда спрашивать нечего, — сюда не доходит.
        raise NoTestInProgress()
    option = next(o for o in options if o.code == choice.code)
    if choice.capped:
        # В пустом окне под потолком нет ничего — это обычный холодный старт; в непустом —
        # сигнал, что банк темы мал (§6).
        log.log(
            logging.WARNING if exposure.attempts else logging.INFO,
            "Тема %s: под потолком показов семейств нет, взято наименее показанное %s "
            "(%d попыток в окне)",
            option.topic,
            option.code,
            exposure.attempts,
        )
    seed = secrets.randbits(63)
    instance = bank.get_family(option.code).instance(seed)
    before = estimate(prior, observations).topic(option.topic)
    presentation = Presentation(
        attempt_id=attempt.id,
        position=len(attempt.presentations),
        family_code=option.code,
        topic_code=option.topic,
        seed=seed,
        params=instance.params,
        discrimination=option.discrimination,
        difficulty=option.difficulty,
        topic_theta_before=before.mean,
        topic_theta_sd_before=before.sd,
        shown_at=now,
    )
    attempt.presentations.append(presentation)
    return presentation


def _finish(db: Session, attempt: TestAttempt, mechanics: Mechanics, now: datetime) -> None:
    """Остановка попытки: оценка теста по всему определению и решение каскада (§4)."""
    prior = _prior(db, attempt, mechanics)
    answered = _answered(db, attempt)
    observations = [presentation_observation(p) for p in answered]
    overall = estimate(prior, observations).overall()
    # Дотест всегда есть что спросить, пока у тем есть семейства в выдаче: невиданные кончатся —
    # возьмутся давно виденные с новыми экземплярами.
    available = bool(families.current(db, _bank(prior), mechanics))

    decision = decide(
        overall,
        attempt.grade_code,
        thresholds=mechanics.grade_thresholds,
        confidence=mechanics.grade_confidence,
        has_items=lambda _: available,
    )
    attempt.finished_at = now
    attempt.overall_theta, attempt.overall_theta_sd = overall.mean, overall.sd
    mine = [i for i, p in enumerate(answered) if p.attempt_id == attempt.id]
    for i, level in zip(mine, rest_levels(prior, observations, mine), strict=True):
        answered[i].topic_theta_rest, answered[i].topic_theta_rest_sd = level.mean, level.sd
    match decision:
        case Assign(grade):
            attempt.outcome, attempt.outcome_grade_code = AttemptOutcome.assigned, grade
            db.add(
                CandidateCategory(
                    user_id=attempt.user_id,
                    specialization_code=attempt.specialization_code,
                    grade_code=grade,
                    attempt_id=attempt.id,
                    assigned_at=now,
                )
            )
        case Offer(grade):
            attempt.outcome, attempt.outcome_grade_code = AttemptOutcome.offered, grade
        case _:
            attempt.outcome = AttemptOutcome.no_category
            attempt.retest_after = now + timedelta(days=mechanics.no_category_retest_days)
    db.flush()
    refresh_profile(db, attempt.user_id, attempt.specialization_code, prior.topics, mechanics)


def _prior(db: Session, attempt: TestAttempt, mechanics: Mechanics) -> Prior:
    """Общее априорное оценки теста: заявленный грейд на неё не влияет (§4, §6)."""
    return specialization_prior(_topics(db, attempt.specialization_code), mechanics)


def _answered(db: Session, attempt: TestAttempt) -> list[Presentation]:
    """Отвеченные предъявления всего определения категории — по порядку."""
    return [p for a in _chain(db, attempt) for p in a.presentations if p.answered_at is not None]


def _observations(db: Session, attempt: TestAttempt) -> list[Observation]:
    """Оценка теста — по ответам всего определения с весом 1: дотест продолжает её."""
    return [presentation_observation(p) for p in _answered(db, attempt)]


def _chain(db: Session, attempt: TestAttempt) -> list[TestAttempt]:
    """Попытки определения категории от первой до `attempt`."""
    chain = [attempt]
    while chain[0].continues_attempt_id is not None:
        chain.insert(0, db.get_one(TestAttempt, chain[0].continues_attempt_id))
    return chain


def _counts(attempt: TestAttempt) -> dict[str, int]:
    """Заданий по темам в текущей попытке: минимумы покрытия и потолок доли — у каждой свои."""
    counts: dict[str, int] = {}
    for p in attempt.presentations:
        counts[p.topic_code] = counts.get(p.topic_code, 0) + 1
    return counts


def _bank(prior: Prior) -> list[bank.Family]:
    return bank.families_for_topics(prior.topics)


def _remaining(db: Session, attempt: TestAttempt, mechanics: Mechanics) -> bool:
    """Есть ли в выдаче семейства тем, ещё не показанные в этой попытке."""
    shown = {p.family_code for p in attempt.presentations}
    prior = _prior(db, attempt, mechanics)
    fresh = [f for f in _bank(prior) if f.code not in shown]
    return bool(families.current(db, fresh, mechanics))


def _topics(db: Session, specialization: str) -> list[str]:
    return list(
        db.scalars(
            select(Topic.code)
            .where(Topic.specialization_code == specialization)
            .order_by(Topic.position)
        )
    )


def _attempt_in_progress(db: Session, user_id: uuid.UUID) -> TestAttempt:
    attempt = db.scalar(
        select(TestAttempt).where(TestAttempt.user_id == user_id, TestAttempt.finished_at.is_(None))
    )
    if attempt is None:
        raise NoTestInProgress()
    return attempt


def _pending(attempt: TestAttempt) -> Presentation | None:
    last = attempt.presentations[-1] if attempt.presentations else None
    return last if last is not None and last.answered_at is None else None


def _next_number(db: Session, model: type[Survey] | type[TestAttempt], user_id: uuid.UUID) -> int:
    """Следующий номер записи кандидата; гонку исключает блокировка `_lock`."""
    last = db.scalar(select(func.max(model.number)).where(model.user_id == user_id))
    return (last or 0) + 1


def _lock(db: Session, user: User) -> None:
    """Шаги пути одного кандидата идут по очереди: двойной клик не создаст две попытки."""
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
