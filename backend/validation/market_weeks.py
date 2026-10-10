"""Рынок приглашений M6 на стенде специализации: копия стенда после определений с моделью
принятия, ожидания кандидатов в пуле и две стратегии на одной синтетике
(`validation.invitation_market`).

Копия берётся до двойников M3 и M5 — на рынке только кандидаты набора — и со своим сидом: замеры
прогона она не сдвигает. Стратегии идут на отдельных копиях одного состояния. Выдача — подборка
продукта по потребности (`Selections.build_draft`) от имени её компании, со сферой компании и
загрузкой кандидатов на начало недели: B берёт сохранённый порядок по S × P(принятия), A —
`in_order(…, match)`. Решение кандидата — правило синтетики, как у пар модели принятия (M7).
"""

import dataclasses
import random
import uuid
from collections.abc import Mapping, Sequence

from app.adapter.seed import DerivedSeeds
from app.domain.selection import (
    Expectations,
    SelectionBlock,
    SelectionOrder,
    in_order,
)
from app.usecase.interface import AcceptanceModel
from validation.acceptance import decision, features_of
from validation.invitation_market import (
    STRATEGIES,
    Opening,
    Ranked,
    Sent,
    budgets,
    simulate,
)
from validation.main import Stand, build_stand
from validation.market import Market
from validation.population import Employer, GeneratorParams, ObservedCandidate, SyntheticNeed
from validation.simulate import Scored
from validation.truth import CandidateTruth

# Выдача рынка — блоки со скором: точный и «близкие». Нижний блок без S не приглашается.
SCORED = (SelectionBlock.exact, SelectionBlock.nearby)
ORDERS = {"A": SelectionOrder.match, "B": SelectionOrder.mutual}


@dataclasses.dataclass(frozen=True)
class MarketInput:
    """Что рынку нужно сверх стенда: наблюдаемое и истина кандидатов, компании и потребности."""

    params: GeneratorParams
    needs: tuple[SyntheticNeed, ...]
    employers: tuple[Employer, ...]
    # Компания → сколько у неё потребностей во всём наборе: бюджет недели делится между ними.
    employer_needs: Mapping[uuid.UUID, int]
    observed: Mapping[uuid.UUID, ObservedCandidate]
    truths: Mapping[uuid.UUID, CandidateTruth]


def expectations(seen: ObservedCandidate) -> Expectations:
    return Expectations(
        salary_from=seen.expected_salary,
        work_formats=seen.work_formats,
        city=seen.city,
        relocation=seen.relocation,
        industries=frozenset(seen.industries),
    )


def market_stand(
    base: Market,
    seed: int,
    model: AcceptanceModel,
    given: MarketInput,
    users: Mapping[uuid.UUID, uuid.UUID],
) -> Stand:
    """Копия стенда `base` с моделью принятия, ожиданиями кандидатов в пуле и сферами компаний;
    `users` — кандидат набора → его учётка на стенде."""
    fork = base.fork(seed)
    stand = build_stand(
        fork.mechanics,
        store=fork.stand.store,
        clock=fork.stand.clock,
        seeds=DerivedSeeds(seed),
        selector=fork.selector,
        acceptance=model,
    )
    for truth, user in users.items():
        member = stand.pool.member(user)
        if member is not None and truth in given.observed:
            stand.pool.add(
                dataclasses.replace(member, expectations=expectations(given.observed[truth]))
            )
    for employer in given.employers:
        stand.needs.put_company_industry(employer.id, employer.industry)
    return stand


class _Strategy:
    """Выдача и решения одной стратегии на своей копии стенда."""

    def __init__(
        self,
        stand: Stand,
        order: SelectionOrder,
        given: MarketInput,
        users: Mapping[uuid.UUID, uuid.UUID],
    ) -> None:
        self._stand = stand
        self._selections = stand.selections()
        self._order = order
        self._given = given
        self._to_truth = {user: truth for truth, user in users.items()}
        self._forms = {n.id: n for n in given.needs}
        self._employers = {e.id: e for e in given.employers}
        # Грейд категории кандидата — из выдачи: по нему рыночная медиана признаков пары.
        self._grades: dict[uuid.UUID, str] = {}

    def rank(self, opening: Opening, loads: Mapping[uuid.UUID, int]) -> Sequence[Ranked]:
        for user, truth in self._to_truth.items():
            self._stand.pool.set_open_invitations(user, loads.get(truth, 0))
        page = self._selections.build_draft(
            opening.employer, self._forms[opening.need].form, limit=len(self._to_truth)
        )
        ranked = []
        for e in in_order(page.entries, self._order):
            if e.block not in SCORED or e.match_score is None:
                continue
            truth = self._to_truth[e.candidate_id]
            self._grades[truth] = e.grade.code
            ranked.append(Ranked(truth, e.match_score))
        return ranked

    def decide(self, opening: Opening, candidate: uuid.UUID, score: float, load: int) -> float:
        features = features_of(
            self._forms[opening.need],
            self._employers[opening.employer],
            self._given.observed[candidate],
            Scored(candidate, self._grades[candidate], score),
            load,
            self._stand.mechanics,
        )
        return decision(self._given.truths[candidate], features, self._given.params)


def run_market(
    base: Market, users: Mapping[uuid.UUID, uuid.UUID], given: MarketInput, model: AcceptanceModel
) -> dict[str, tuple[Sent, ...]]:
    """Две стратегии на копиях стенда `base` после определений; приглашения — с id кандидатов
    набора. Копии — с одним сидом: стратегии начинают с одного состояния."""
    mechanics = base.mechanics
    params = given.params
    openings = budgets(
        [(n.id, n.employer) for n in given.needs],
        given.employer_needs,
        mechanics.invitation_weekly_budget,
    )
    seed = random.Random(f"{params.seed}:market:{base.specialization}").getrandbits(32)
    found: dict[str, tuple[Sent, ...]] = {}
    for strategy in STRATEGIES:
        played = _Strategy(
            market_stand(base, seed, model, given, users), ORDERS[strategy], given, users
        )
        run = simulate(
            strategy,
            openings,
            played.rank,
            played.decide,
            weeks=params.market_weeks,
            ttl_days=mechanics.invitation_ttl_days,
            response_mean_days=params.market_response_mean_days,
            rng=random.Random(f"{params.seed}:market:{base.specialization}:{strategy}"),
        )
        found[strategy] = tuple(run.sent)
    return found
