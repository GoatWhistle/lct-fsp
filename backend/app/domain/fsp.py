"""ФСП: вход через ФСП ID, достижения из реестра и их место в профиле навыков (mechanics.md, §11).

Результат ФСП — очное соревнование под надзором, высший уровень доверия. В профиль он входит
односторонним наблюдением — «решённое задание» сложности по типу результата: победитель,
призёр, финалист. Участие в отборе — факт в профиле, не наблюдение. Мероприятия и дисциплины не
ранжируются, ФСП не меняет ни грейд, ни категорию.

Темы достижения — по справочнику дисциплин: личный зачёт или роль не указана — темы дисциплины;
командный зачёт с ролью — темы роли (специализации) внутри тем дисциплины, при пустом пересечении —
темы роли. Дисциплина без тем — только факт.
"""

import enum
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from app.domain.catalog import CatalogRef, FspDiscipline, Topic
from app.domain.skill import Observation, SignalSource


class FspResult(enum.StrEnum):
    """Тип результата — поле реестра `fsp_result`."""

    winner = "winner"
    prize = "prize"
    finalist = "finalist"
    # Участник отбора без выхода в финал — факт в профиле, не наблюдение.
    participant = "participant"


@dataclass(frozen=True)
class FspAchievement:
    """Достижение, как его отдаёт реестр: `discipline` — код дисциплины справочника, `team_role`
    — код специализации роли в команде, `None` — личный зачёт или роль не указана; `place` —
    место, если реестр его знает."""

    event: str
    date: date
    discipline: str
    place: int | None
    result: FspResult
    team_role: str | None


@dataclass(frozen=True)
class FspSnapshot:
    """Последние полученные из реестра достижения и момент получения. Профиль и подборка читают
    только снимок: недоступный реестр их не ломает."""

    achievements: tuple[FspAchievement, ...]
    fetched_at: datetime


@dataclass(frozen=True)
class ConfirmedAchievement:
    """Достижение для показа: названия дисциплины и роли — из справочника, неизвестный код
    показывается как есть."""

    event: str
    date: date
    discipline: CatalogRef
    place: int | None
    result: FspResult
    team_role: CatalogRef | None


@dataclass(frozen=True)
class FspHistory:
    """Привязанный ФСП ID: снимок достижений для показа. `fetched_at` — `None`, если реестр
    ни разу не ответил."""

    achievements: tuple[ConfirmedAchievement, ...]
    fetched_at: datetime | None


@dataclass(frozen=True)
class AnonymizedAchievement:
    """Достижение в обезличенной карточке: тип результата, дисциплина и год. Мероприятие, место и
    команда по ним узнают человека — их работодатель видит только после раскрытия."""

    result: FspResult
    discipline: CatalogRef
    year: int


def anonymized(achievement: ConfirmedAchievement) -> AnonymizedAchievement:
    return AnonymizedAchievement(achievement.result, achievement.discipline, achievement.date.year)


@dataclass(frozen=True)
class FspEvidence:
    """Всё, из чего достижения становятся наблюдениями: снимок, справочник дисциплин и темы
    специализаций, которые встречаются ролями в команде."""

    achievements: tuple[FspAchievement, ...]
    disciplines: Mapping[str, FspDiscipline]
    role_topics: Mapping[str, Collection[str]]


def achievement_topics(achievement: FspAchievement, evidence: FspEvidence) -> tuple[str, ...]:
    """Темы, о которых говорит достижение. Неизвестная дисциплина или дисциплина без тем — ни
    одной; неизвестная роль — как роль не указана."""
    discipline = evidence.disciplines.get(achievement.discipline)
    if discipline is None or not discipline.topics:
        return ()
    role_topics = evidence.role_topics
    role = role_topics.get(achievement.team_role, ()) if achievement.team_role else ()
    if not role:
        return discipline.topics
    both = tuple(t for t in discipline.topics if t in role)
    return both or tuple(role)


@dataclass(frozen=True)
class TimedObservation:
    """Наблюдение с моментом сигнала: наблюдения всех уровней идут в модель по времени."""

    at: datetime
    observation: Observation


def signal_moment(day: date) -> datetime:
    """Момент сигнала достижения — начало дня мероприятия в UTC."""
    return datetime.combine(day, time(), UTC)


def fsp_observations(
    evidence: FspEvidence,
    profile_topics: Collection[str],
    *,
    difficulty: Mapping[str, float],
    discrimination: float,
    weight: float,
) -> list[TimedObservation]:
    """Каждый результат с выходом в финал — отдельное наблюдение «решено» по каждой своей теме
    профиля: сложность — по типу результата (`fsp_result_difficulty`), разделяющая сила
    `fsp_result_discrimination`, вес `trust_weight_fsp`. Участник отбора — не наблюдение."""
    found = []
    for achievement in evidence.achievements:
        b = difficulty.get(achievement.result.value)
        if b is None:
            continue
        for topic in achievement_topics(achievement, evidence):
            if topic in profile_topics:
                observation = Observation(
                    topic, True, discrimination, b, weight=weight, source=SignalSource.fsp
                )
                found.append(TimedObservation(signal_moment(achievement.date), observation))
    return found


@dataclass(frozen=True)
class Divergence:
    """Тест ниже уровня результата ФСП по теме больше чем на `fsp_divergence_theta`: пометка и
    рекомендация проверочного блока, без штрафа. Видит только кандидат."""

    topic: CatalogRef
    discipline: CatalogRef
    event: str
    result: FspResult
    # Сложность результата — уровень, который он подтверждает, θ.
    result_level: float
    # Уровень по теме по оценке теста, θ.
    test_level: float


def divergences(
    evidence: FspEvidence,
    topics: Sequence[Topic],
    test_levels: Mapping[str, float],
    *,
    difficulty: Mapping[str, float],
    threshold: float,
) -> list[Divergence]:
    """Расхождения по темам с оценкой теста — по одному на тему, с самым сильным результатом.
    Тест выше результата расхождением не считается: результат ФСП — нижняя граница."""
    named = {t.code: t for t in topics}
    strongest: dict[str, Divergence] = {}
    for achievement in evidence.achievements:
        b = difficulty.get(achievement.result.value)
        if b is None:
            continue
        for code in achievement_topics(achievement, evidence):
            level = test_levels.get(code)
            if level is None or code not in named or b - level <= threshold:
                continue
            if code in strongest and strongest[code].result_level >= b:
                continue
            # Темы есть только у дисциплины из справочника.
            discipline = evidence.disciplines[achievement.discipline]
            strongest[code] = Divergence(
                topic=CatalogRef(code, named[code].name),
                discipline=CatalogRef(discipline.code, discipline.name),
                event=achievement.event,
                result=achievement.result,
                result_level=b,
                test_level=level,
            )
    return [strongest[t.code] for t in topics if t.code in strongest]


class FspIntent(enum.StrEnum):
    """Зачем кандидат ушёл в ФСП ID: войти или привязать ID к своей учётке."""

    login = "login"
    link = "link"


@dataclass(frozen=True)
class FspAuthorization:
    """Начатый вход через ФСП ID (authorization code + PKCE): `state` сверяется в callback,
    `code_verifier` подтверждает обмен кода, `nonce` — ID-токен выдан этому входу. Живёт в
    короткоживущей httpOnly-cookie браузера. `user_id` — кто начал привязку: ID привязывается
    только к нему, даже если в браузере за это время вошёл другой."""

    state: str
    code_verifier: str
    nonce: str
    intent: FspIntent
    user_id: uuid.UUID | None = None


@dataclass(frozen=True)
class FspIdentity:
    """Кто вошёл в ФСП ID: `sub` — ФСП ID, email и его подтверждение — из claims IdP."""

    sub: str
    email: str | None
    email_verified: bool
