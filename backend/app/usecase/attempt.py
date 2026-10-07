"""Сценарии пути кандидата к категории: опрос → грейд → тест → оценка → категория
(mechanics.md, §4, §6).

Опрос — направление: специализация справочника, «отрасль» в ТЗ. Сферы бизнеса в опрос не
входят — это необязательное предпочтение в профиле кандидата.

Правила пути — в `app.domain.attempt` и `app.domain.determination`; модель навыка, выбор
задания и калибровка — за портами, их реализации сценарий не видит. От калибровки путь берёт
только текущие параметры семейств; калибруют их по ответу — `app.usecase.calibration`.
Следующее задание выбирается адаптивно при показе. Априорное зависит только от тем
специализации и конфига, поэтому считается один раз на запрос; оценка по ответам — тоже.
"""

import logging
import random
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from app.config import Mechanics
from app.domain import bank
from app.domain.adaptive import Blueprint, Option, selection_prior, should_stop
from app.domain.attempt import (
    Answer,
    Answered,
    Attempt,
    AttemptOutcome,
    AttemptProgress,
    Item,
    PathState,
    PathView,
    Presentation,
    Stage,
    stage_of,
    test_result,
)
from app.domain.determination import Assign, Offer, decide
from app.domain.errors import (
    GradeNotOffered,
    ItemNotCurrent,
    NoTestInProgress,
    SpecializationWithoutTest,
    StepUnavailable,
    UnknownGrade,
    UnknownSpecialization,
)
from app.domain.skill import Normal, Observation, Prior, SkillEstimate
from app.usecase.interface import (
    AttemptRepository,
    Calibration,
    Clock,
    ItemSelector,
    SeedSource,
    SkillModel,
    UnitOfWork,
)
from app.usecase.skill_profile import refresh_skill_profile, specialization_prior

log = logging.getLogger(__name__)


def blueprint_of(prior: Prior, mechanics: Mechanics) -> Blueprint:
    """Бланк теста из априорного и конфига — общий для пути кандидата и стенда валидации."""
    return Blueprint(
        topics=prior.topics,
        weights=prior.weights,
        min_items=mechanics.test_min_items,
        max_items=mechanics.test_max_items,
        min_per_topic=mechanics.test_min_items_per_topic,
        max_topic_share=mechanics.test_max_topic_share,
        stop_sd=mechanics.test_stop_sd,
    )


def rest_levels(
    model: SkillModel,
    prior: Prior,
    observations: Sequence[Observation],
    indices: Iterable[int],
) -> list[Normal]:
    """Итоговая оценка темы для каждого ответа из `indices` — по всем остальным ответам.

    Сам ответ в оценку не входит: иначе верный ответ поднимает оценку, с которой его потом
    сравнивают, и переоценка завышает разделяющую силу.
    """
    return [
        model.estimate(prior, [o for j, o in enumerate(observations) if j != i]).topic(
            observations[i].topic
        )
        for i in indices
    ]


class CandidatePath:
    """Путь кандидата. Состояние выводится из записей репозитория попытки: прерванный тест
    продолжается с того же места после перезапуска бэкенда."""

    def __init__(
        self,
        uow: UnitOfWork,
        attempts: AttemptRepository,
        calibration: Calibration,
        selector: ItemSelector,
        skill_model: SkillModel,
        clock: Clock,
        seeds: SeedSource,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._attempts = attempts
        self._calibration = calibration
        self._selector = selector
        self._skill_model = skill_model
        self._clock = clock
        self._seeds = seeds
        self._mechanics = mechanics
        # Априорное специализации — от тем и конфига: на запрос считается один раз.
        self._priors: dict[str, Prior] = {}

    def path(self, user_id: uuid.UUID) -> PathView:
        """Шаг пути и итоги теста — без записи."""
        with self._uow:
            return self._view(self._attempts.state(user_id), self._clock.now(), user_id)

    def submit_survey(self, user_id: uuid.UUID, *, specialization: str) -> PathView:
        """Опрос доступен до начала теста, повторный заменяет прежний."""
        with self._uow:
            self._attempts.lock_candidate(user_id)
            now = self._clock.now()
            if stage_of(self._attempts.state(user_id), now) not in (Stage.survey, Stage.grade):
                raise StepUnavailable()
            topics = self._attempts.specialization_topics(specialization)
            if topics is None:
                raise UnknownSpecialization()
            if not bank.covers([t.code for t in topics]):
                raise SpecializationWithoutTest()
            self._attempts.add_survey(user_id, specialization, now)
            return self._view(self._attempts.state(user_id), now, user_id)

    def start_attempt(self, user_id: uuid.UUID, *, grade: str) -> PathView:
        """Тест на заявленный грейд или дотест каскада на предложенный; возвращает шаг пути на
        тот же момент."""
        with self._uow:
            self._attempts.lock_candidate(user_id)
            if grade not in self._mechanics.grade_thresholds:
                raise UnknownGrade()
            now = self._clock.now()
            state = self._attempts.state(user_id)
            stage = stage_of(state, now)
            if stage == Stage.grade and state.survey is not None:
                survey, continues = state.survey, None
            elif stage == Stage.offer and state.attempt is not None:
                if grade != state.attempt.outcome_grade_code:
                    raise GradeNotOffered()
                survey, continues = self._attempts.survey(state.attempt.survey_id), state.attempt
            else:
                raise StepUnavailable()

            attempt = self._attempts.add_attempt(user_id, survey, grade, continues, now)
            prior = self._prior(attempt.specialization_code)
            if not self._remaining(attempt, prior):
                # Дотест, в котором спрашивать нечего, оценку не меняет — его итог известен сразу.
                chain = self._attempts.chain(attempt)
                observations = _observations(chain)
                estimate = self._skill_model.estimate(prior, observations)
                self._finish(attempt, chain, prior, estimate, observations, now)
            return self._view(self._attempts.state(user_id), now, user_id)

    def current_item(self, user_id: uuid.UUID) -> Item:
        """Текущее задание попытки. Предъявление создаётся при первом показе — с него идут часы
        ответа; повторный запрос отдаёт то же задание и часы не сбрасывает.

        Экземпляр всегда новый, со свежим seed. Seed выбора и экземпляра — из порта: в проде по
        ним никто не угадает следующее семейство, в тестах они воспроизводимы.
        """
        with self._uow:
            self._attempts.lock_candidate(user_id)
            attempt = self._attempt_in_progress(user_id)
            presentation = attempt.pending()
            if presentation is None:
                presentation = self._present(attempt, self._clock.now())
            topics = self._attempts.specialization_topics(attempt.specialization_code) or ()
            topic = next((t for t in topics if t.code == presentation.topic_code), None)
            if topic is None:
                raise LookupError(
                    f"тема {presentation.topic_code} не в справочнике специализации "
                    f"{attempt.specialization_code}"
                )
            instance = bank.get_family(presentation.family_code).instance(presentation.seed)
            return Item(
                presentation.id,
                presentation.position + 1,
                topic,
                presentation.family_code,
                instance,
            )

    def answer(self, user_id: uuid.UUID, *, presentation_id: uuid.UUID, response: str) -> Answered:
        """Проверка ответа на бэкенде; верность на фронт не уходит. После ответа — проверка
        остановки: точность набрана или спрашивать больше нечего.

        Калибровку (§7) сценарий не трогает: её по возвращённому ответу запускает вызывающий,
        отдельным сценарием `app.usecase.calibration` после фиксации ответа.
        """
        now = self._clock.now()
        with self._uow:
            self._attempts.lock_candidate(user_id)
            attempt = self._attempt_in_progress(user_id)
            presentation = attempt.pending()
            if presentation is None or presentation.id != presentation_id:
                raise ItemNotCurrent()
            family = bank.get_family(presentation.family_code)
            correct = family.check(family.instance(presentation.seed), response)
            presentation.response = response
            presentation.correct = correct
            presentation.answered_at = now
            # Часы сервера при синхронизации отходят назад на секунды — время ответа не уходит
            # в минус.
            elapsed = (now - presentation.shown_at).total_seconds()
            presentation.response_time_ms = max(0, round(elapsed * 1000))
            self._attempts.save_answer(presentation)

            prior = self._prior(attempt.specialization_code)
            chain = self._attempts.chain(attempt)
            observations = _observations(chain)
            estimate = self._skill_model.estimate(prior, observations)
            stop = should_stop(self._blueprint(prior), attempt.counts(), estimate.overall())
            if stop or not self._remaining(attempt, prior):
                self._finish(attempt, chain, prior, estimate, observations, now)
            view = self._view(self._attempts.state(user_id), now, user_id)

        return Answered(
            view,
            Answer(
                specialization_code=attempt.specialization_code,
                family_code=presentation.family_code,
                level_before=Normal(
                    presentation.topic_theta_before, presentation.topic_theta_sd_before
                ),
                correct=correct,
                answered_at=now,
                stopped=attempt.finished_at is not None,
                families=tuple(p.family_code for p in attempt.presentations),
            ),
        )

    def _present(self, attempt: Attempt, now: datetime) -> Presentation:
        chain = self._attempts.chain(attempt)
        observations = _observations(chain)
        prior = self._prior(attempt.specialization_code)
        threshold = self._mechanics.grade_thresholds[attempt.grade_code]
        selection = self._skill_model.estimate(selection_prior(prior, threshold), observations)
        shown_here = attempt.shown()
        params = self._calibration.current(
            [f for f in _bank(prior) if f.code not in shown_here]
        )
        window, shown = self._attempts.exposure(
            attempt.specialization_code, attempt.id, self._mechanics.exposure_window_attempts
        )
        seen = self._attempts.seen(attempt.user_id, attempt.id)
        options = [
            Option(
                code,
                bank.get_family(code).topic,
                p.discrimination,
                p.difficulty,
                shown=shown.get(code, 0),
                seen_at=seen.get(code),
            )
            for code, p in params.items()
        ]
        rng = random.Random(self._seeds.seed())
        choice = self._selector.choose(
            self._blueprint(prior), attempt.counts(), selection, options, window, rng
        )
        if choice is None:
            # Ответ останавливает попытку, когда спрашивать нечего, — сюда не доходит.
            raise NoTestInProgress()
        option = next(o for o in options if o.code == choice.code)
        if choice.capped:
            # В пустом окне под потолком нет ничего — это обычный холодный старт; в непустом —
            # сигнал, что банк темы мал (§6).
            log.log(
                logging.WARNING if window else logging.INFO,
                "Тема %s: под потолком показов семейств нет, взято наименее показанное %s "
                "(%d попыток в окне)",
                option.topic,
                option.code,
                window,
            )
        seed = self._seeds.seed()
        instance = bank.get_family(option.code).instance(seed)
        before = self._skill_model.estimate(prior, observations).topic(option.topic)
        return self._attempts.add_presentation(
            attempt,
            family_code=option.code,
            topic_code=option.topic,
            seed=seed,
            params=instance.params,
            discrimination=option.discrimination,
            difficulty=option.difficulty,
            level_before=before,
            shown_at=now,
        )

    def _finish(
        self,
        attempt: Attempt,
        chain: list[Attempt],
        prior: Prior,
        estimate: SkillEstimate,
        observations: list[Observation],
        now: datetime,
    ) -> None:
        """Остановка попытки: оценка теста по всему определению, решение каскада (§4) и пересчёт
        профиля навыков по всем ответам (§11)."""
        overall = estimate.overall()
        # Дотест всегда есть что спросить, пока у тем есть семейства в выдаче: невиданные
        # кончатся — возьмутся давно виденные с новыми экземплярами.
        available = bool(self._calibration.current(_bank(prior)))

        decision = decide(
            overall,
            attempt.grade_code,
            thresholds=self._mechanics.grade_thresholds,
            confidence=self._mechanics.grade_confidence,
            has_items=lambda _: available,
        )
        attempt.finished_at = now
        attempt.overall = overall
        answered = [p for a in chain for p in a.presentations if p.answered_at is not None]
        mine = [i for i, p in enumerate(answered) if p.attempt_id == attempt.id]
        rest = rest_levels(self._skill_model, prior, observations, mine)
        for i, level in zip(mine, rest, strict=True):
            answered[i].topic_theta_rest, answered[i].topic_theta_rest_sd = level.mean, level.sd
        match decision:
            case Assign(grade):
                attempt.outcome, attempt.outcome_grade_code = AttemptOutcome.assigned, grade
            case Offer(grade):
                attempt.outcome, attempt.outcome_grade_code = AttemptOutcome.offered, grade
            case _:
                attempt.outcome = AttemptOutcome.no_category
                attempt.retest_after = now + timedelta(
                    days=self._mechanics.no_category_retest_days
                )
        self._attempts.finish_attempt(attempt)
        self._attempts.save_rest_levels([answered[i] for i in mine])
        if attempt.outcome == AttemptOutcome.assigned:
            self._attempts.add_category(attempt, now)
        levels = refresh_skill_profile(
            self._attempts,
            self._skill_model,
            self._mechanics,
            attempt.user_id,
            attempt.specialization_code,
            prior.topics,
        )
        self._attempts.save_profile(attempt.user_id, attempt.specialization_code, levels, now)

    def _view(self, state: PathState, now: datetime, user_id: uuid.UUID) -> PathView:
        stage = stage_of(state, now)
        attempt = state.attempt
        profile = None
        if attempt is not None:
            profile = self._attempts.profile(user_id, attempt.specialization_code)
        if stage in (Stage.survey, Stage.grade):
            attempt = None
        finished = attempt is not None and attempt.finished_at is not None
        result = None
        if attempt is not None and finished:
            result = test_result(
                attempt,
                thresholds=self._mechanics.grade_thresholds,
                grade_confidence=self._mechanics.grade_confidence,
                hint_confidence=self._mechanics.grade_up_hint_confidence,
            )
        return PathView(
            stage=stage,
            survey=state.survey,
            progress=(
                AttemptProgress(
                    attempt.grade_code,
                    sum(1 for p in attempt.presentations if p.answered_at is not None),
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
            category=state.category,
            result=result,
            profile=profile,
        )

    def _attempt_in_progress(self, user_id: uuid.UUID) -> Attempt:
        attempt = self._attempts.attempt_in_progress(user_id)
        if attempt is None:
            raise NoTestInProgress()
        return attempt

    def _remaining(self, attempt: Attempt, prior: Prior) -> bool:
        """Есть ли в выдаче семейства тем, ещё не показанные в этой попытке."""
        shown = attempt.shown()
        fresh = [f for f in _bank(prior) if f.code not in shown]
        return bool(self._calibration.current(fresh))

    def _prior(self, specialization_code: str) -> Prior:
        """Общее априорное оценки теста: заявленный грейд на неё не влияет (§4, §6)."""
        prior = self._priors.get(specialization_code)
        if prior is None:
            topics = self._attempts.specialization_topics(specialization_code) or ()
            prior = specialization_prior([t.code for t in topics], self._mechanics)
            self._priors[specialization_code] = prior
        return prior

    def _blueprint(self, prior: Prior) -> Blueprint:
        return blueprint_of(prior, self._mechanics)


def _bank(prior: Prior) -> list[bank.Family]:
    return bank.families_for_topics(prior.topics)


def _observations(chain: list[Attempt]) -> list[Observation]:
    """Оценка теста — по ответам всего определения с весом 1: дотест продолжает её."""
    return [
        p.answered().observation()
        for a in chain
        for p in a.presentations
        if p.answered_at is not None
    ]
