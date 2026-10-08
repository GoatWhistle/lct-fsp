"""Синтетический рынок специализации: кандидаты с известной истиной проходят тест на стенде через
те же сценарии, что HTTP, — начать попытку, задание, ответ, калибровка после ответа.

Истина — уровни кандидатов и параметры семейств — живёт только здесь. В сценарии и хранилище
попадают только ответы, как в сервисе: верный — эталон экземпляра, неверный — заведомо не он.
Окна показов и связки, «видел раньше», остановка и каскад — прод-код; стенд ничего из этого не
повторяет, а только читает записанное.

Истина отличается от модели оценки, как в наборе D1 плана валидации: уровни шире априорного
оценщика, b* = b₀ + N(0; 0,5²), ln a* = ln a₀ + N(0; 0,3²) — калибровке есть что исправлять.
"""

import math
import random
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.config import Mechanics
from app.domain.adaptive import Blueprint, Choice, Option
from app.domain.attempt import AttemptOutcome, Stage
from app.domain.bank import Family, families_for_topics
from app.domain.calibration import CalibratedFamily, Parameters
from app.domain.determination import grades_by_threshold
from app.domain.selection import PoolCandidate
from app.domain.skill import Normal, Observation, SkillEstimate, sigmoid
from app.repository.memory.calibration import MemoryCalibrationRepository
from app.repository.memory.unit_of_work import MemoryStore
from app.usecase.interface import ItemSelector
from app.usecase.skill_profile import specialization_prior
from composition import elo_calibration, item_selector
from validation.main import Stand, build_stand
from validation.metrics import pearson, rmse

# Сиды наборов плана валидации: D1 — основной, D3 — настроечный.
SEED = 20261005
TUNING_SEED = 7
# Прогретый банк: ответов на семейство в среднем.
WARM_RESPONSES = 500
# Неверный ответ синтетического кандидата: ни один эталон банка с ним не совпадает.
WRONG = "ответа нет"


def expert(grade: str, mechanics: Mechanics) -> Parameters:
    """Стартовые параметры семейства по грейду эксперта — у калибровки прода."""
    return elo_calibration(MemoryCalibrationRepository(MemoryStore()), mechanics).expert(grade)


@dataclass(frozen=True)
class Candidate:
    level: dict[str, float]
    claimed: str


@dataclass(frozen=True)
class Run:
    """Попытка теста, как её записал сценарий."""

    shown: tuple[str, ...]
    # Оценка общего уровня на остановке.
    overall: Normal
    # Исход и присвоенный или предложенный для дотеста грейд; у базовой линии исхода нет.
    outcome: AttemptOutcome | None = None
    outcome_grade: str | None = None
    # Семейства, взятые сверх потолка показов: под потолком в теме ничего не осталось.
    capped: tuple[str, ...] = ()
    # Ответы попытки по порядку.
    answers: tuple[Observation, ...] = ()


@dataclass(frozen=True)
class Determination:
    """Итог первичного определения: грейд None — без категории; оценка общего уровня — на конец
    определения."""

    user: uuid.UUID
    grade: str | None
    overall: Normal


class RecordingSelector:
    """Выбор задания стенда: выбирает реализация прода, стенд записывает выбор — так видно, что
    взято сверх потолка показов."""

    def __init__(self, inner: ItemSelector) -> None:
        self.inner = inner
        self.choices: list[Choice] = []

    def choose(
        self,
        blueprint: Blueprint,
        counts: Mapping[str, int],
        estimate: SkillEstimate,
        options: Sequence[Option],
        attempts_in_window: int,
        rng: random.Random,
    ) -> Choice | None:
        choice = self.inner.choose(blueprint, counts, estimate, options, attempts_in_window, rng)
        if choice is not None:
            self.choices.append(choice)
        return choice


class Market:
    """Банк одной специализации на своём стенде и поток кандидатов с известной истиной.

    Калибровку после ответа стенд вызывает, как контроллер; `calibrate = False` замораживает
    банк — сценарий калибровки больше не вызывается.
    """

    def __init__(self, specialization: str, mechanics: Mechanics, seed: int = SEED) -> None:
        self.specialization = specialization
        self.mechanics = mechanics
        self.rng = random.Random(seed)
        self.selector = RecordingSelector(item_selector(mechanics))
        self.stand = build_stand(mechanics, seed=seed, selector=self.selector)
        topics = [t.code for t in self.stand.catalog.specializations[specialization].topics]
        self.prior = specialization_prior(topics, mechanics)
        self.expert = elo_calibration(self.stand.calibration, mechanics).expert
        self.families = families_for_topics(topics)
        self._topics = {f.code: f.topic for f in self.families}
        self.truth: dict[str, Parameters] = {}
        for f in self.families:
            start = self.expert(f.grade)
            # Параметры якоря известны — на этом знании и держится шкала.
            self.truth[f.code] = (
                start
                if f.anchor
                else Parameters(
                    start.discrimination * math.exp(self.rng.gauss(0, 0.3)),
                    start.difficulty + self.rng.gauss(0, 0.5),
                )
            )
        self.calibrate = True
        self._users = 0

    def candidate(self) -> Candidate:
        """Уровни шире априорного оценщика; заявка — истинный грейд, на один выше или ниже."""
        common = self.rng.gauss(0, 1.2)
        level = {t: common + self.rng.gauss(0, 0.7) for t in self.prior.topics}
        grades = grades_by_threshold(self.mechanics.grade_thresholds)
        thresholds = self.mechanics.grade_thresholds
        overall = self._overall(level)
        true = max((i for i, g in enumerate(grades) if overall >= thresholds[g]), default=0)
        shift = self.rng.choices([0, 1, -1], weights=[0.6, 0.25, 0.15])[0]
        return Candidate(level, grades[min(max(true + shift, 0), len(grades) - 1)])

    def overall(self, candidate: Candidate) -> float:
        """Истинный общий уровень θ̄* — с весами тем, как в оценке."""
        return self._overall(candidate.level)

    def respond(self, candidate: Candidate, family_code: str) -> bool:
        truth = self.truth[family_code]
        level = candidate.level[self._topics[family_code]]
        p = sigmoid(truth.discrimination * (level - truth.difficulty))
        return self.rng.random() < p

    def attempt(self, candidate: Candidate, *, stand: Stand | None = None) -> Run:
        """Тест на заявленный грейд — одна попытка до остановки, без дотестов каскада.
        `stand` — вариант стенда с другим бланком на том же банке."""
        return self._take(stand or self.stand, self._enrol(), candidate, candidate.claimed)

    def determine(self, candidate: Candidate) -> Determination:
        """Первичное определение категории (§4) новым кандидатом: тест на заявленный грейд и
        каскад дотестов вниз."""
        user = self._enrol()
        grade = candidate.claimed
        while True:
            run = self._take(self.stand, user, candidate, grade)
            match run.outcome:
                case AttemptOutcome.assigned:
                    return Determination(user, run.outcome_grade, run.overall)
                case AttemptOutcome.offered:
                    assert run.outcome_grade is not None
                    grade = run.outcome_grade
                case _:
                    return Determination(user, None, run.overall)

    def enlist(self, user: uuid.UUID) -> bool:
        """Кандидат с категорией — в пул подборки стенда: категория и профиль навыков её
        специализации, как их записал путь кандидата. Самоописания и ожиданий у синтетики нет.
        Без категории в пул не попадает — False."""
        stand = self.stand
        with stand.uow:
            category = stand.attempts.state(user).category
            profile = stand.attempts.profile(user, self.specialization)
            if category is None or profile is None:
                return False
            stand.pool.add(
                PoolCandidate(
                    candidate_id=user,
                    specialization=self.specialization,
                    grade=stand.catalog.grades[category.grade.code],
                    levels={
                        t.topic.code: Normal(t.level.theta, t.level.theta_sd)
                        for t in profile.topics
                    },
                    stack=frozenset(),
                    last_signal_at=profile.last_signal_at,
                    expectations=None,
                )
            )
        return True

    def fixed(self, candidate: Candidate, length: int, *, target: float | None = None) -> Run:
        """Базовая линия — фиксированный бланк с тем же покрытием тем: по кругу тем, в теме —
        семейства с экспертной сложностью ближе к `target` первыми. С `target` бланк общий для
        всех (схема S2 плана валидации); без него — по середине заявленного грейда. Ответы
        оцениваются моделью навыка стенда на текущих параметрах банка."""
        if target is None:
            target = self.mechanics.expert_difficulty_by_grade[candidate.claimed]
        queues = {
            t: sorted(
                (f for f in self.families if f.topic == t),
                key=lambda f: (abs(self.expert(f.grade).difficulty - target), f.code),
            )
            for t in self.prior.topics
        }
        order: list[Family] = []
        while any(queues.values()) and len(order) < length:
            for t in self.prior.topics:
                if queues[t] and len(order) < length:
                    order.append(queues[t].pop(0))
        params = self.parameters()
        answers = tuple(
            Observation(
                f.topic,
                self.respond(candidate, f.code),
                params[f.code].discrimination,
                params[f.code].difficulty,
            )
            for f in order
        )
        overall = self.stand.skill_model.estimate(self.prior, answers).overall()
        return Run(tuple(f.code for f in order), overall, answers=answers)

    def sd_after(self, run: Run, items: int) -> float:
        """Погрешность общего уровня после первых `items` ответов попытки."""
        return self.stand.skill_model.estimate(self.prior, run.answers[:items]).overall().sd

    def items_to(self, run: Run, sd: float) -> int | None:
        """Сколько ответов понадобилось, чтобы погрешность общего уровня стала не выше `sd`;
        None — не стала. С каждым ответом погрешность не растёт — поиск делением пополам."""
        if not run.answers or self.sd_after(run, len(run.answers)) > sd:
            return None
        low, high = 1, len(run.answers)
        while low < high:
            middle = (low + high) // 2
            if self.sd_after(run, middle) <= sd:
                high = middle
            else:
                low = middle + 1
        return low

    def calibrated(self) -> dict[str, CalibratedFamily]:
        """Состояние калибровки семейств, у которых оно есть, — из репозитория стенда."""
        with self.stand.uow:
            return self.stand.calibration.parameters([f.code for f in self.families])

    def parameters(self) -> dict[str, Parameters]:
        """Текущие параметры всех семейств банка, и выведенных из выдачи тоже."""
        rows = self.calibrated()
        return {
            f.code: rows[f.code].parameters if f.code in rows else self.expert(f.grade)
            for f in self.families
        }

    def load(self, parameters: Mapping[str, Parameters]) -> None:
        """Кладёт параметры семейств в репозиторий калибровки — банк, прогретый заранее или
        известный точно."""
        with self.stand.uow:
            for code, p in parameters.items():
                row = self.stand.calibration.locked(code, p)
                row.discrimination, row.difficulty = p.discrimination, p.difficulty
                self.stand.calibration.save(row)

    def _enrol(self) -> uuid.UUID:
        """Новый кандидат с опросом по специализации рынка — прямо в репозиторий, без
        регистрации и сценария опроса."""
        self._users += 1
        user = uuid.UUID(int=self._users)
        with self.stand.uow:
            self.stand.attempts.add_survey(user, self.specialization, self.stand.clock.now())
        return user

    def _take(self, stand: Stand, user: uuid.UUID, candidate: Candidate, grade: str) -> Run:
        """Попытка на `grade` через сценарии, как их вызывает контроллер: шаг часов, начало,
        задания и ответы до остановки, после каждого ответа — калибровка."""
        stand.clock.advance(stand.step)
        paths = stand.candidate_path()
        calibrations = stand.answer_calibration()
        self.selector.choices.clear()
        view = paths.start_attempt(user, grade=grade)
        while view.stage == Stage.test:
            item = paths.current_item(user)
            correct = self.respond(candidate, item.family_code)
            response = item.instance.answer if correct else WRONG
            answered = paths.answer(user, presentation_id=item.presentation_id, response=response)
            assert answered.answer.correct == correct, item.family_code
            if self.calibrate:
                calibrations.calibrate(answered.answer)
            view = answered.view
        with stand.uow:
            attempt = stand.attempts.state(user).attempt
        assert attempt is not None and attempt.overall is not None
        assert attempt.outcome is not None
        return Run(
            shown=tuple(p.family_code for p in attempt.presentations),
            overall=attempt.overall,
            outcome=attempt.outcome,
            outcome_grade=attempt.outcome_grade_code,
            capped=tuple(c.code for c in self.selector.choices if c.capped),
            answers=tuple(
                p.answered().observation() for p in attempt.presentations if p.correct is not None
            ),
        )

    def _overall(self, level: dict[str, float]) -> float:
        return sum(w * level[t] for t, w in zip(self.prior.topics, self.prior.weights, strict=True))


def market(specialization: str, mechanics: Mechanics, seed: int = SEED) -> Market:
    return Market(specialization, mechanics, seed)


def calibration_quality(m: Market) -> tuple[float, float, float]:
    """r(b̂, b*), RMSE(b̂, b*) и RMSE экспертных b₀ по неякорным семействам."""
    params = m.parameters()
    regular = [f for f in m.families if not f.anchor]
    truth = [m.truth[f.code].difficulty for f in regular]
    start = [m.expert(f.grade).difficulty for f in regular]
    current = [params[f.code].difficulty for f in regular]
    return pearson(current, truth), rmse(current, truth), rmse(start, truth)


def mean_responses(m: Market) -> float:
    """Ответов на неякорное семейство в среднем — по счётчику калибровки."""
    rows = m.calibrated()
    regular = [f for f in m.families if not f.anchor]
    return sum(rows[f.code].responses if f.code in rows else 0 for f in regular) / len(regular)


def warm(m: Market, responses: int = WARM_RESPONSES) -> Market:
    """Калибровка на потоке кандидатов до `responses` ответов на семейство в среднем; дальше
    параметры заморожены."""
    while mean_responses(m) < responses:
        m.attempt(m.candidate())
    m.calibrate = False
    return m


def true_grade(m: Market, candidate: Candidate) -> str | None:
    """Истинный грейд — полоса θ̄*; None — ниже порога младшего грейда."""
    thresholds = m.mechanics.grade_thresholds
    level = m.overall(candidate)
    passed = [g for g in grades_by_threshold(thresholds) if level >= thresholds[g]]
    return passed[-1] if passed else None
