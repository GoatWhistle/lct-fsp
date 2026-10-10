"""Рыночная симуляция приглашений на стенде (docs/validation-plan.md, M6; mechanics.md, §13–§14).

Восемь недель рынка одной специализации. Каждую неделю работодатель перестраивает подборку по
своей потребности и шлёт приглашения сверху выдачи в пределах бюджета недели: стратегия A берёт
порядок «только соответствие» — по S, стратегия B — сохранённый порядок по S × P(принятия). Обе
берут порядок из той же подборки, что продукт (`Selections`, `in_order`), а не из своей копии
формулы. Одно открытое приглашение компании кандидату: пока прошлое не закрыто, второе той же
компании не уходит; кандидату, который уже принял приглашение компании, она больше не пишет.

Кандидат отвечает через случайную задержку — экспонента со средним `market_response_mean_days`
дней; не ответил за `invitation_ttl_days` — приглашение истекло. Решение — правило синтетики
(`AcceptanceRule`) по скрытой склонности и признакам пары, загрузка — открытые приглашения
кандидата в момент ответа, включая это. Модель принятия решения не видит: она только упорядочивает
выдачу стратегии B.

Здесь — только ход времени и правила рынка; подборку и решение подставляет вызывающий, поэтому
модуль проверяется без стенда.
"""

import math
import random
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

STRATEGIES = ("A", "B")
DAYS_IN_WEEK = 7.0


class Answer(StrEnum):
    accepted = "accepted"
    declined = "declined"
    expired = "expired"


@dataclass(frozen=True)
class Opening:
    """Потребность на рынке: чья она и сколько приглашений в неделю на неё уходит."""

    need: uuid.UUID
    employer: uuid.UUID
    budget: int


@dataclass(frozen=True)
class Ranked:
    """Строка выдачи на момент отправки: кандидат и его S."""

    candidate: uuid.UUID
    match_score: float


@dataclass
class Sent:
    """Отправленное приглашение и его судьба."""

    week: int
    need: uuid.UUID
    employer: uuid.UUID
    candidate: uuid.UUID
    match_score: float
    sent_at: float
    # Когда кандидат ответит; None — не ответит до срока, приглашение истечёт.
    answer_at: float | None
    answer: Answer | None = None

    def closes_at(self, ttl: float) -> float:
        return self.answer_at if self.answer_at is not None else self.sent_at + ttl

    def open_at(self, moment: float, ttl: float) -> bool:
        return self.sent_at <= moment < self.closes_at(ttl)


# Выдача потребности на начало недели: загрузка кандидатов → порядок стратегии.
Rank = Callable[[Opening, Mapping[uuid.UUID, int]], Sequence[Ranked]]
# P(кандидат примет) по правилу синтетики: потребность, кандидат, S, загрузка.
Decide = Callable[[Opening, uuid.UUID, float, int], float]


@dataclass
class MarketRun:
    strategy: str
    sent: list[Sent] = field(default_factory=list)


def budgets(
    needs: Sequence[tuple[uuid.UUID, uuid.UUID]],
    total_needs: Mapping[uuid.UUID, int],
    weekly: int,
) -> list[Opening]:
    """Бюджет недели компании делится поровну между всеми её потребностями набора; здесь —
    потребности одной специализации `needs` (потребность, компания). Округление вниз: если
    потребностей больше бюджета,
    квота каждой равна нулю, бюджет компании не превышается."""
    return [Opening(need, employer, weekly // total_needs[employer]) for need, employer in needs]


def simulate(
    strategy: str,
    openings: Sequence[Opening],
    rank: Rank,
    decide: Decide,
    *,
    weeks: int,
    ttl_days: float,
    response_mean_days: float,
    rng: random.Random,
) -> MarketRun:
    """Восемь недель рынка одной стратегии. Неделя: ответы кандидатов до её начала — по времени,
    затем отправка по каждой потребности сверху выдачи; после последней недели — оставшиеся
    ответы."""
    run = MarketRun(strategy)
    accepted: set[tuple[uuid.UUID, uuid.UUID]] = set()
    pending: list[Sent] = []
    for week in range(weeks):
        start = week * DAYS_IN_WEEK
        pending = _answer_until(run.sent, pending, start, ttl_days, decide, openings, rng, accepted)
        loads = _loads(run.sent, start, ttl_days)
        busy = {(s.employer, s.candidate) for s in run.sent if s.open_at(start, ttl_days)}
        for opening in openings:
            left = opening.budget
            for row in rank(opening, loads):
                if left == 0:
                    break
                key = (opening.employer, row.candidate)
                if key in busy or key in accepted:
                    continue
                delay = rng.expovariate(1 / response_mean_days)
                sent = Sent(
                    week,
                    opening.need,
                    opening.employer,
                    row.candidate,
                    row.match_score,
                    start,
                    start + delay if delay < ttl_days else None,
                )
                run.sent.append(sent)
                pending.append(sent)
                busy.add(key)
                left -= 1
    _answer_until(run.sent, pending, math.inf, ttl_days, decide, openings, rng, accepted)
    return run


def _loads(sent: Sequence[Sent], moment: float, ttl: float) -> dict[uuid.UUID, int]:
    loads: dict[uuid.UUID, int] = {}
    for s in sent:
        if s.open_at(moment, ttl):
            loads[s.candidate] = loads.get(s.candidate, 0) + 1
    return loads


def _answer_until(
    sent: Sequence[Sent],
    pending: list[Sent],
    until: float,
    ttl: float,
    decide: Decide,
    openings: Sequence[Opening],
    rng: random.Random,
    accepted: set[tuple[uuid.UUID, uuid.UUID]],
) -> list[Sent]:
    """Ответы и истечения раньше `until` — по времени; ничьи — по порядку отправки. Загрузка —
    открытые приглашения кандидата в момент ответа, включая это."""
    by_need = {o.need: o for o in openings}
    due = sorted(
        (s for s in pending if s.closes_at(ttl) < until),
        key=lambda s: (s.closes_at(ttl), sent.index(s)),
    )
    for s in due:
        if s.answer_at is None:
            s.answer = Answer.expired
            continue
        load = sum(
            1
            for other in sent
            if other.candidate == s.candidate and (other is s or other.open_at(s.answer_at, ttl))
        )
        p = decide(by_need[s.need], s.candidate, s.match_score, load)
        if rng.random() < p:
            s.answer = Answer.accepted
            accepted.add((s.employer, s.candidate))
        else:
            s.answer = Answer.declined
    done = {id(s) for s in due}
    return [s for s in pending if id(s) not in done]


@dataclass(frozen=True)
class MarketMetrics:
    """M6: доля принятых от отправленных, Джини числа приглашений на кандидата и средний M*
    принятых пар."""

    sent: int
    accepted: int
    gini: float
    true_match: float | None

    @property
    def accepted_share(self) -> float:
        return self.accepted / self.sent if self.sent else 0.0


def gini(values: Sequence[float]) -> float:
    """Коэффициент Джини: 0 — всем поровну, к 1 — всё у одного."""
    n = len(values)
    total = sum(values)
    if n == 0 or total == 0:
        return 0.0
    ordered = sorted(values)
    weighted = sum((i + 1) * v for i, v in enumerate(ordered))
    return (2 * weighted) / (n * total) - (n + 1) / n


def metrics(
    sent: Sequence[Sent],
    candidates: Sequence[uuid.UUID],
    true_match: Callable[[uuid.UUID, uuid.UUID], float],
) -> MarketMetrics:
    """Метрики по приглашениям `sent` на кандидатов пула `candidates` — Джини считается по всем,
    включая тех, кого не позвали ни разу."""
    counts = dict.fromkeys(candidates, 0)
    for s in sent:
        counts[s.candidate] = counts.get(s.candidate, 0) + 1
    accepted = [s for s in sent if s.answer == Answer.accepted]
    return MarketMetrics(
        sent=len(sent),
        accepted=len(accepted),
        gini=gini(list(counts.values())),
        true_match=(
            sum(true_match(s.need, s.candidate) for s in accepted) / len(accepted)
            if accepted
            else None
        ),
    )
