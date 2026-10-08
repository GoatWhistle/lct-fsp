"""Сценарии пути кандидата к категории: опрос → грейд → тест → оценка → категория, затем
смена грейда — попытка вверх и переход вниз — и блок по теме (mechanics.md, §4, §6).

Блок по теме — попытка с той же парой «задание / ответ», что у теста, но вне пути: ровно
`topic_block_items` заданий по семействам одной темы, ответы идут в профиль навыков, категория,
грейд и часы смены грейда не меняются. У кандидата одна незавершённая попытка — теста или блока.

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
from dataclasses import replace
from datetime import datetime, timedelta

from app.domain import bank
from app.domain.adaptive import Blueprint, Option, selection_prior, should_stop
from app.domain.attempt import (
    Answer,
    Answered,
    Attempt,
    AttemptOutcome,
    AttemptProgress,
    AttemptPurpose,
    CategoryChange,
    GradeUp,
    HistoryEntry,
    Item,
    PathState,
    PathView,
    Presentation,
    Stage,
    TopicBlockProgress,
    grade_up_available_at,
    path_history,
    stage_of,
    test_result,
    topic_blocks_held,
)
from app.domain.bank.runner import CodeRunner
from app.domain.catalog import CatalogRef
from app.domain.determination import (
    Assign,
    Decision,
    NoCategory,
    NotPassed,
    Offer,
    decide,
    decide_up,
    grade_above,
    grade_below,
)
from app.domain.errors import (
    AttemptInProgress,
    CategoryRequired,
    GradeChangeTooEarly,
    GradeNotNext,
    GradeNotOffered,
    ItemNotCurrent,
    NoLowerGrade,
    NoTestInProgress,
    SpecializationWithoutTest,
    StepUnavailable,
    TopicBlockTooEarly,
    TopicNotInCategory,
    UnknownGrade,
    UnknownSpecialization,
)
from app.domain.skill import Normal, Observation, Prior, SkillEstimate
from app.usecase.interface import (
    AttemptRepository,
    Calibration,
    Clock,
    FspEvidenceReader,
    ItemSelector,
    RegularTaskReader,
    SeedSource,
    SkillModel,
    UnitOfWork,
)
from app.usecase.skill_profile import (
    ProfileFreshness,
    fsp_evidence,
    refresh_skill_profile,
    specialization_prior,
)
from settings import Mechanics

log = logging.getLogger(__name__)


def blueprint_of(prior: Prior, mechanics: Mechanics) -> Blueprint:
    """Бланк теста из априорного и конфига."""
    return Blueprint(
        topics=prior.topics,
        weights=prior.weights,
        min_items=mechanics.test_min_items,
        max_items=mechanics.test_max_items,
        min_per_topic=mechanics.test_min_items_per_topic,
        max_topic_share=mechanics.test_max_topic_share,
        stop_sd=mechanics.test_stop_sd,
    )


def topic_block_blueprint(topic: str, mechanics: Mechanics) -> Blueprint:
    """Бланк блока по теме: одна тема, ровно `topic_block_items` заданий, без остановки по
    погрешности и без ограничений покрытия теста."""
    items = mechanics.topic_block_items
    return Blueprint(
        topics=(topic,),
        weights=(1.0,),
        min_items=items,
        max_items=items,
        min_per_topic=0,
        max_topic_share=1.0,
        stop_sd=0.0,
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
        tasks: RegularTaskReader,
        fsp: FspEvidenceReader,
        calibration: Calibration,
        selector: ItemSelector,
        skill_model: SkillModel,
        clock: Clock,
        seeds: SeedSource,
        runner: CodeRunner,
        mechanics: Mechanics,
    ) -> None:
        self._uow = uow
        self._attempts = attempts
        self._tasks = tasks
        self._fsp = fsp
        self._calibration = calibration
        self._selector = selector
        self._skill_model = skill_model
        self._clock = clock
        self._seeds = seeds
        self._runner = runner
        self._mechanics = mechanics
        self._freshness = ProfileFreshness(skill_model, mechanics)
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
        """Тест на заявленный грейд, дотест каскада на предложенный или, при категории, попытка
        на грейд выше; возвращает шаг пути на тот же момент.

        Попытка вверх — с чистого листа: дотестом она не продолжает ничью оценку. Раньше срока
        по правилу ожидания (§4) она не начинается — ошибка несёт дату, когда можно.
        """
        with self._uow:
            self._attempts.lock_candidate(user_id)
            if grade not in self._mechanics.grade_thresholds:
                raise UnknownGrade()
            now = self._clock.now()
            state = self._attempts.state(user_id)
            stage = stage_of(state, now)
            purpose = AttemptPurpose.determination
            if stage == Stage.grade and state.survey is not None:
                survey, continues = state.survey, None
            elif stage == Stage.offer and state.attempt is not None:
                if grade != state.attempt.outcome_grade_code:
                    raise GradeNotOffered()
                survey, continues = self._attempts.survey(state.attempt.survey_id), state.attempt
            elif stage == Stage.category and state.category is not None:
                if self._attempts.attempt_in_progress(user_id) is not None:
                    raise AttemptInProgress()
                up = self._grade_up(
                    state.category.grade.code,
                    self._path_attempts(user_id),
                    self._attempts.category_changes(user_id),
                    now,
                )
                if up is None or grade != up.grade:
                    raise GradeNotNext()
                if up.available_at is not None:
                    raise GradeChangeTooEarly(up.available_at)
                # Опрос после присвоения не меняется: последний — тот, по которому категория.
                assert state.survey is not None
                survey, continues = state.survey, None
                purpose = AttemptPurpose.grade_up
            else:
                raise StepUnavailable()

            attempt = self._attempts.add_attempt(user_id, survey, grade, continues, now, purpose)
            prior = self._prior(attempt.specialization_code)
            if not self._remaining(attempt, prior):
                # Дотест, в котором спрашивать нечего, оценку не меняет — его итог известен сразу.
                chain = self._attempts.chain(attempt)
                observations = _observations(chain)
                estimate = self._skill_model.estimate(prior, observations)
                self._finish(attempt, chain, prior, estimate, observations, now)
            return self._view(self._attempts.state(user_id), now, user_id)

    def start_topic_block(self, user_id: uuid.UUID, *, topic: str) -> PathView:
        """Блок по теме категории (§6). Не чаще `topic_block_interval_days` на тему: интервал
        считается от старта последнего блока по теме, брошенного тоже, — раньше срока ошибка несёт
        дату, когда можно. Пока идёт тест или другой блок, блок не начинается."""
        with self._uow:
            self._attempts.lock_candidate(user_id)
            now = self._clock.now()
            state = self._attempts.state(user_id)
            category = state.category
            if category is None:
                raise CategoryRequired()
            specialization = category.specialization.code
            topics = self._attempts.specialization_topics(specialization) or ()
            if topic not in {t.code for t in topics}:
                raise TopicNotInCategory()
            if self._attempts.attempt_in_progress(user_id) is not None:
                raise AttemptInProgress()
            held = topic_blocks_held(
                self._attempts.attempts(user_id),
                [topic],
                now,
                timedelta(days=self._mechanics.topic_block_interval_days),
            )
            if topic in held:
                raise TopicBlockTooEarly(held[topic])
            if not self._calibration.current(bank.families_for_topics([topic])):
                # Все семейства темы сняты с выдачи — спросить блоку нечем.
                raise StepUnavailable()
            # Опрос после присвоения не меняется: последний — тот, по которому категория.
            assert state.survey is not None
            self._attempts.add_attempt(
                user_id,
                state.survey,
                category.grade.code,
                None,
                now,
                AttemptPurpose.topic_block,
                topic_code=topic,
            )
            return self._view(self._attempts.state(user_id), now, user_id)

    def step_down(self, user_id: uuid.UUID) -> PathView:
        """Переход на грейд ниже — без теста и без ожидания (§4): правило уверенности для
        младшего грейда уже выполнено той же оценкой. Заданий не показывает, банк не тратит."""
        with self._uow:
            self._attempts.lock_candidate(user_id)
            now = self._clock.now()
            state = self._attempts.state(user_id)
            if stage_of(state, now) != Stage.category or state.category is None:
                raise StepUnavailable()
            lower = grade_below(state.category.grade.code, self._mechanics.grade_thresholds)
            if lower is None:
                raise NoLowerGrade()
            self._attempts.lower_category(user_id, lower, now)
            return self._view(self._attempts.state(user_id), now, user_id)

    def current_item(self, user_id: uuid.UUID) -> Item:
        """Текущее задание попытки. Предъявление создаётся при первом показе — с него идут часы
        ответа; повторный запрос отдаёт то же задание и часы не сбрасывает.

        Экземпляр всегда новый, со свежим seed. Seed выбора и экземпляра — из порта: в проде по
        ним никто не угадает следующее семейство, в тестах они воспроизводимы.

        Блок, у темы которого после прошлого ответа не осталось семейств в выдаче, — калибровка
        вывела их, — останавливается здесь же: иначе он висел бы незавершённой попыткой.
        """
        with self._uow:
            self._attempts.lock_candidate(user_id)
            attempt = self._attempt_in_progress(user_id)
            presentation = attempt.pending()
            prior = self._prior(attempt.specialization_code)
            stuck = (
                presentation is None
                and attempt.purpose == AttemptPurpose.topic_block
                and not self._remaining(attempt, prior)
            )
            if stuck:
                self._finish_block(attempt, prior, self._clock.now())
            else:
                if presentation is None:
                    presentation = self._present(attempt, self._clock.now())
                return self._item(attempt, presentation)
        # Остановка блока зафиксирована — заданий больше нет.
        raise NoTestInProgress()

    def _item(self, attempt: Attempt, presentation: Presentation) -> Item:
        topics = self._attempts.specialization_topics(attempt.specialization_code) or ()
        topic = next((t for t in topics if t.code == presentation.topic_code), None)
        if topic is None:
            raise LookupError(
                f"тема {presentation.topic_code} не в справочнике специализации "
                f"{attempt.specialization_code}"
            )
        instance = bank.get_family(presentation.family_code).instance(
            presentation.seed, self._runner
        )
        block = attempt.purpose == AttemptPurpose.topic_block
        return Item(
            presentation.id,
            presentation.position + 1,
            topic,
            presentation.family_code,
            instance,
            max_items=(
                self._mechanics.topic_block_items if block else self._mechanics.test_max_items
            ),
            topic_block=block,
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
            correct = family.check(family.instance(presentation.seed, self._runner), response)
            presentation.response = response
            presentation.correct = correct
            presentation.answered_at = now
            # Часы сервера при синхронизации отходят назад на секунды — время ответа не уходит
            # в минус.
            elapsed = (now - presentation.shown_at).total_seconds()
            presentation.response_time_ms = max(0, round(elapsed * 1000))
            self._attempts.save_answer(presentation)

            prior = self._prior(attempt.specialization_code)
            if attempt.purpose == AttemptPurpose.topic_block:
                if len(attempt.presentations) >= self._mechanics.topic_block_items or (
                    not self._remaining(attempt, prior)
                ):
                    self._finish_block(attempt, prior, now)
            else:
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
        """Следующее задание. Тест выбирает по оценке определения с априорным в пороге
        заявленного грейда; блок по теме — по оценке теста из всех ответов кандидата по
        специализации, только среди семейств своей темы."""
        prior = self._prior(attempt.specialization_code)
        if attempt.purpose == AttemptPurpose.topic_block:
            observations = self._test_observations(attempt)
            selection = self._skill_model.estimate(prior, observations)
            blueprint = self._block_blueprint(attempt)
        else:
            observations = _observations(self._attempts.chain(attempt))
            threshold = self._mechanics.grade_thresholds[attempt.grade_code]
            selection = self._skill_model.estimate(selection_prior(prior, threshold), observations)
            blueprint = self._blueprint(prior)
        shown_here = attempt.shown()
        params = self._calibration.current(
            [f for f in self._families(attempt, prior) if f.code not in shown_here]
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
        choice = self._selector.choose(blueprint, attempt.counts(), selection, options, window, rng)
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
        instance = bank.get_family(option.code).instance(seed, self._runner)
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
        """Остановка попытки: оценка теста по всему определению, решение (§4) и пересчёт
        профиля навыков по всем ответам и достижениям ФСП (§11). Определение решает каскадом
        вниз; попытка вверх — только правилом уверенности на свой грейд, провал категорию не
        меняет."""
        overall = estimate.overall()
        thresholds = self._mechanics.grade_thresholds
        confidence = self._mechanics.grade_confidence
        decision: Decision | NotPassed
        if attempt.purpose == AttemptPurpose.grade_up:
            decision = decide_up(
                overall, attempt.grade_code, thresholds=thresholds, confidence=confidence
            )
        else:
            # Дотест всегда есть что спросить, пока у тем есть семейства в выдаче: невиданные
            # кончатся — возьмутся давно виденные с новыми экземплярами.
            available = bool(self._calibration.current(_bank(prior)))
            decision = decide(
                overall,
                attempt.grade_code,
                thresholds=thresholds,
                confidence=confidence,
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
            case NotPassed():
                attempt.outcome = AttemptOutcome.not_passed
            case NoCategory():
                attempt.outcome = AttemptOutcome.no_category
                attempt.retest_after = now + timedelta(days=self._mechanics.no_category_retest_days)
        self._attempts.finish_attempt(attempt)
        self._attempts.save_rest_levels([answered[i] for i in mine])
        if attempt.outcome == AttemptOutcome.assigned:
            if attempt.purpose == AttemptPurpose.grade_up:
                self._attempts.raise_category(attempt, now)
            else:
                self._attempts.add_category(attempt, now)
        self._refresh_profile(attempt, prior, now)

    def _finish_block(self, attempt: Attempt, prior: Prior, now: datetime) -> None:
        """Остановка блока по теме: оценка теста по всем ответам кандидата, итоговые оценки
        темы без каждого ответа блока — для переоценки семейств (§7) — и пересчёт профиля тем же
        путём, что после теста. Исхода нет: категория, грейд и журнал смен не меняются."""
        observations = self._test_observations(attempt)
        attempt.finished_at = now
        attempt.overall = self._skill_model.estimate(prior, observations).overall()
        answered = [p for p in attempt.presentations if p.answered_at is not None]
        # Ответы блока — последние: незавершённая попытка у кандидата одна, и номер у неё старший.
        mine = range(len(observations) - len(answered), len(observations))
        tail = [(observations[i].topic, observations[i].at) for i in mine]
        assert tail == [(p.topic_code, p.answered_at) for p in answered], (
            "ответы блока не последние"
        )
        rest = rest_levels(self._skill_model, prior, observations, mine)
        for p, level in zip(answered, rest, strict=True):
            p.topic_theta_rest, p.topic_theta_rest_sd = level.mean, level.sd
        self._attempts.finish_attempt(attempt)
        self._attempts.save_rest_levels(answered)
        self._refresh_profile(attempt, prior, now)

    def _refresh_profile(self, attempt: Attempt, prior: Prior, now: datetime) -> None:
        """Профиль навыков по всем ответам и достижениям ФСП (§11) — после теста и блока."""
        levels = refresh_skill_profile(
            self._attempts,
            self._tasks,
            self._skill_model,
            self._mechanics,
            attempt.user_id,
            attempt.specialization_code,
            prior.topics,
            fsp_evidence(self._attempts, self._fsp, attempt.user_id),
        )
        self._attempts.save_profile(attempt.user_id, attempt.specialization_code, levels, now)

    def _view(self, state: PathState, now: datetime, user_id: uuid.UUID) -> PathView:
        stage = stage_of(state, now)
        attempt = state.attempt
        profile = None
        if attempt is not None:
            profile = self._attempts.profile(user_id, attempt.specialization_code)
        if profile is not None:
            profile = self._freshness.view(profile, now)
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
        grade_up, grade_down = None, None
        history: tuple[HistoryEntry, ...] = ()
        if stage == Stage.category and state.category is not None:
            grade = state.category.grade.code
            attempts = self._path_attempts(user_id)
            changes = self._attempts.category_changes(user_id)
            grade_up = self._grade_up(grade, attempts, changes, now)
            grade_down = grade_below(grade, self._mechanics.grade_thresholds)
            # Подсказка «грейд выше» — только пока она про доступную сейчас попытку вверх: после
            # перехода вниз или при сроке ожидания она устарела.
            if result is not None and (
                grade_up is None
                or grade_up.available_at is not None
                or result.grade_up_hint != grade_up.grade
            ):
                result = replace(result, grade_up_hint=None)
            history = path_history(
                attempts,
                changes,
                thresholds=self._mechanics.grade_thresholds,
                confidence=self._mechanics.grade_confidence,
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
            grade_up=grade_up,
            grade_down=grade_down,
            history=history,
            # Блок идёт только при категории — на других шагах его не ищем.
            topic_block=self._block_progress(user_id) if stage == Stage.category else None,
        )

    def _block_progress(self, user_id: uuid.UUID) -> TopicBlockProgress | None:
        block = self._attempts.attempt_in_progress(user_id)
        if block is None or block.purpose != AttemptPurpose.topic_block:
            return None
        assert block.topic_code is not None
        topics = self._attempts.specialization_topics(block.specialization_code) or ()
        name = next((t.name for t in topics if t.code == block.topic_code), block.topic_code)
        return TopicBlockProgress(
            CatalogRef(block.topic_code, name),
            sum(1 for p in block.presentations if p.answered_at is not None),
            self._mechanics.topic_block_items,
        )

    def _path_attempts(self, user_id: uuid.UUID) -> list[Attempt]:
        """Попытки пути — без блоков по теме: истории и правилу ожидания они не принадлежат."""
        return [a for a in self._attempts.attempts(user_id) if a.on_path]

    def _grade_up(
        self,
        grade: str,
        attempts: Sequence[Attempt],
        changes: Sequence[CategoryChange],
        now: datetime,
    ) -> GradeUp | None:
        """Попытка вверх с грейда `grade` на момент `now`: срок по правилу ожидания, если он ещё
        не наступил; None — грейд старший."""
        target = grade_above(grade, self._mechanics.grade_thresholds)
        if target is None:
            return None
        available_at = grade_up_available_at(
            target,
            attempts,
            changes,
            thresholds=self._mechanics.grade_thresholds,
            change_interval=timedelta(days=self._mechanics.grade_change_interval_days),
            retry_interval=timedelta(days=self._mechanics.grade_retry_interval_days),
        )
        if available_at is not None and available_at <= now:
            available_at = None
        return GradeUp(target, available_at)

    def _attempt_in_progress(self, user_id: uuid.UUID) -> Attempt:
        attempt = self._attempts.attempt_in_progress(user_id)
        if attempt is None:
            raise NoTestInProgress()
        return attempt

    def _remaining(self, attempt: Attempt, prior: Prior) -> bool:
        """Есть ли в выдаче семейства тем попытки, ещё не показанные в ней."""
        shown = attempt.shown()
        fresh = [f for f in self._families(attempt, prior) if f.code not in shown]
        return bool(self._calibration.current(fresh))

    def _families(self, attempt: Attempt, prior: Prior) -> list[bank.Family]:
        """Семейства, из которых попытка берёт задания: у блока — только своей темы."""
        if attempt.topic_code is not None:
            return bank.families_for_topics([attempt.topic_code])
        return _bank(prior)

    def _test_observations(self, attempt: Attempt) -> list[Observation]:
        """Оценка теста для блока по теме: все ответы кандидата по специализации с весом 1 — тестов
        и блоков, по порядку ответа."""
        return [
            p.observation()
            for p in self._attempts.answered(attempt.user_id, attempt.specialization_code)
        ]

    def _block_blueprint(self, attempt: Attempt) -> Blueprint:
        assert attempt.topic_code is not None
        return topic_block_blueprint(attempt.topic_code, self._mechanics)

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
