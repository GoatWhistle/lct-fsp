"""Скрытая истина синтетического кандидата, модель ответа и эталонная релевантность
(docs/validation-plan.md, «Данные» и «Эталонная релевантность»).

Истина живёт только на стенде: модуль оценки и подбора её не видят, а наблюдаемое — ответы,
время, самоописание, достижения ФСП — порождается из неё и никогда не наоборот. Эталонная
релевантность принимает истину кандидата и потребность — вход работодателя; наблюдаемых
признаков в её сигнатуре нет.

Модель ответа — не модель оценки (правило 5 плана): угадывание по виду задания, промах, свои
истинные параметры семейства и личная скорость ответа.
"""

import enum
import json
import math
import random
import uuid
import zlib
from dataclasses import dataclass, field

from app.domain.bank import AnswerFormat, Instance
from app.domain.calibration import Parameters
from app.domain.selection import NeedSnapshot
from app.domain.skill import sigmoid
from app.domain.work import WorkFormat


class Persona(enum.StrEnum):
    """Персонаж кандидата D1: доли — в плане валидации."""

    honest = "honest"
    # Дописывает в самоописание стек и слова вакансий своей специализации.
    resume_inflator = "resume_inflator"
    # Знает часть банка: слитый экземпляр решает всегда, свежий экземпляр слитого семейства —
    # с прибавкой ρ.
    bank_leak = "bank_leak"
    # Решает с помощью LLM: вероятность падает с трудностью, время аномально короткое.
    llm_helper = "llm_helper"


@dataclass(frozen=True)
class ResponseModel:
    """Числа модели ответа; имена — строки раздела «Синтетический рынок» в parameters.md."""

    # s — промах.
    slip: float = 0.02
    # g вычисляемого ответа.
    value_guess: float = 0.0
    # g выбора из k вариантов — `choice_guess_factor / k`; перестановки k шагов — `/ k!`.
    choice_guess_factor: float = 1.0
    # Время: ln T = ln `rt_median_seconds` + скорость кандидата + `rt_difficulty_slope` · b* + шум.
    rt_median_seconds: float = 60.0
    rt_difficulty_slope: float = 0.25
    rt_noise_sd: float = 0.4
    # LLM-помощник (M16 а): P = σ(`llm_slope` · (`llm_center` − b*)), время около
    # `llm_median_seconds` независимо от трудности.
    llm_slope: float = 1.5
    llm_center: float = 1.0
    llm_median_seconds: float = 25.0
    llm_time_sd: float = 0.2
    # Читер (M14): на свежем экземпляре слитого семейства p' = p + ρ(1 − p).
    leak_rho: float = 0.5


@dataclass(frozen=True)
class CandidateTruth:
    """Скрытая истина кандидата. Уровни — θ*_t = θ*_s + δ*_t по темам его специализации."""

    id: uuid.UUID
    specialization: str
    persona: Persona
    # θ*_s — общая часть уровня.
    common: float
    level: dict[str, float]
    # Истинный грейд — полоса θ̄*; None — ниже порога младшего грейда.
    grade: str | None
    claimed: str
    # Ожидаемая зарплата «от», ₽ в месяц до НДФЛ.
    expected_salary: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool
    # Склонность принимать приглашения, 0–1: вход модели принятия, а не признак.
    acceptance: float
    # Личная скорость — сдвиг ln T: больше нуля — медленнее.
    speed: float
    # Слитые семейства читера.
    leaked: frozenset[str] = field(default=frozenset())
    # ФСП ID в реестре; None — без истории ФСП.
    fsp_sub: str | None = None


@dataclass(frozen=True)
class Response:
    correct: bool
    seconds: float


class Corruption(enum.StrEnum):
    """Испорченное семейство M21 — только в скрытой истине: признаки банка его не выдают."""

    # Ошибка эталона: у половины экземпляров эталон неверен, верный ответ засчитывается неверным.
    key = "key"
    # Ответ не зависит от уровня: P(верно) = 0,5.
    flat = "flat"


def corrupt(
    response: Response, corruption: Corruption, instance: Instance | None, rng: random.Random
) -> Response:
    """Ответ на испорченное семейство. Неверный эталон — свойство экземпляра: какая половина
    экземпляров испорчена, решает экземпляр целиком — текст, код, параметры и эталон. Одного текста
    мало: у многих семейств он общий, а различаются параметры и код, и тогда испорчены были бы все
    экземпляры или ни один. Без экземпляра — фиксированный бланк базовой линии — жребий на каждый
    ответ: та же доля испорченных ответов, но не привязанная к экземпляру; M21 идёт только через
    попытки, где экземпляр есть."""
    match corruption:
        case Corruption.flat:
            return Response(rng.random() < 0.5, response.seconds)
        case Corruption.key:
            broken = (
                zlib.crc32(_identity(instance).encode()) % 2 == 0
                if instance is not None
                else rng.random() < 0.5
            )
            return Response(response.correct and not broken, response.seconds)


def _identity(instance: Instance) -> str:
    return json.dumps(
        [instance.prompt, instance.code, instance.answer, instance.params],
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )


def guessing(instance: Instance, model: ResponseModel) -> float:
    """g по виду ответа: вычисляемый — `value_guess`, выбор — из k вариантов, перестановка —
    из k! порядков."""
    k = len(instance.options)
    match instance.answer_format:
        case AnswerFormat.CHOICE if k:
            return min(1.0, model.choice_guess_factor / k)
        case AnswerFormat.ORDERING if k:
            return min(1.0, model.choice_guess_factor / math.factorial(k))
        case _:
            return model.value_guess


def respond(
    truth: CandidateTruth,
    family: str,
    topic: str,
    params: Parameters,
    guess: float,
    model: ResponseModel,
    rng: random.Random,
    *,
    leaked_instance: bool = False,
) -> Response:
    """Ответ кандидата на экземпляр семейства `family` с истинными параметрами `params`.
    `leaked_instance` — тот самый экземпляр, что слит (общий бланк S1): читер решает его всегда."""
    b = params.difficulty
    if truth.persona == Persona.llm_helper:
        p = sigmoid(model.llm_slope * (model.llm_center - b))
        seconds = model.llm_median_seconds * math.exp(rng.gauss(0, model.llm_time_sd))
        return Response(rng.random() < p, seconds)
    p = guess + (1 - guess - model.slip) * sigmoid(params.discrimination * (truth.level[topic] - b))
    if truth.persona == Persona.bank_leak and family in truth.leaked:
        p = 1.0 if leaked_instance else p + model.leak_rho * (1 - p)
    seconds = model.rt_median_seconds * math.exp(
        truth.speed + model.rt_difficulty_slope * b + rng.gauss(0, model.rt_noise_sd)
    )
    return Response(rng.random() < p, seconds)


# Градация эталона: rel = 3, 2, 1 при M* не ниже порога.
RELEVANCE_EDGES = (0.9, 0.7, 0.5)
# Сумма весов тем — дроби: 0,9 не должно стать 0,8999999.
_EPSILON = 1e-9


@dataclass(frozen=True)
class Relevance:
    # M* — доля выполненных требований по истине.
    share: float
    # rel — 3/2/1/0; релевантный — rel ≥ 2.
    grade: int


def relevance(truth: CandidateTruth, need: NeedSnapshot) -> Relevance:
    """M* = Σ v_t · 1[θ*_t ≥ req_t]; другая истинная специализация — M* = 0."""
    if truth.specialization != need.specialization.code:
        return Relevance(0.0, 0)
    share = sum(t.weight for t in need.topics if truth.level[t.topic.code] >= t.requirement)
    grade = next((3 - i for i, edge in enumerate(RELEVANCE_EDGES) if share >= edge - _EPSILON), 0)
    return Relevance(share, grade)
