"""Обратная связь кандидату (mechanics.md, §15): место в подборках за период и что поднимет выше —
чистые функции.

Порог k — по числу разных компаний, чьи подборки включили кандидата: ниже порога ни агрегатов,
ни подсказок по потребностям нет, есть только общая подсказка. Подсказки считаются
контрфактически той же функцией скора, что и подборка (`match_score`): уровень одной темы
меняется по сценарию, остальное — как в профиле сейчас. Работодатели, потребности и чужие
профили наружу не выходят: на выходе — только числа и темы.
"""

import enum
import statistics
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.catalog import CatalogRef
from app.domain.match import Requirement, match_score
from app.domain.selection import NeedSnapshot, SelectionBlock
from app.domain.skill import Normal

# Рост уровня на полосу: полоса грейда шириной 1 по θ (§4, §15).
RAISE_STEP = 1.0


@dataclass(frozen=True)
class CandidateSelection:
    """Подборка, в выдаче которой есть кандидат, — то, что обратной связи можно о ней знать.

    `owner` и `selection_id` нужны только для порога k и для того, чтобы считать подборку без
    потребности отдельной, — наружу они не выходят.
    """

    selection_id: uuid.UUID
    # Работодатель-владелец подборки: у компании одна учётка.
    owner: uuid.UUID
    # None — подборка по черновику или потребность удалена.
    need_id: uuid.UUID | None
    need: NeedSnapshot
    # λ на момент построения.
    stack_cap: float
    created_at: datetime
    # Место кандидата в общей выдаче и его блок.
    position: int
    block: SelectionBlock
    # Сохранённые скоры соответствия остальных кандидатов того же блока — без их профилей.
    neighbors: tuple[float, ...]


@dataclass(frozen=True)
class Placement:
    """Агрегаты по подборкам за период: сколько, медианное место в общей выдаче, доля точного
    блока."""

    selections: int
    median_position: float
    exact_share: float


class Scenario(enum.StrEnum):
    # Сужение погрешности: блок по теме, μ не меняется.
    narrow = "narrow"
    # Рост уровня на полосу при той же погрешности.
    raise_ = "raise"


class ActionKind(enum.StrEnum):
    regular_task = "regular_task"
    topic_block = "topic_block"
    link_fsp = "link_fsp"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    # Действие можно выполнить сейчас: блока по теме пока нет.
    available: bool


@dataclass(frozen=True)
class Hint:
    """Подсказка: тема с действием. Без числа — общая подсказка ниже порога k и привязка ФСП ID
    (у неё нет и темы)."""

    topic: CatalogRef | None
    action: Action
    scenario: Scenario | None = None
    # Средний прирост скора соответствия по встреченным потребностям.
    gain: float | None = None
    # Средний выигрыш мест против сохранённых скоров соседей.
    places: float | None = None


@dataclass(frozen=True)
class Feedback:
    # Окно подборок, дней.
    period_days: int
    # Компаний не меньше k: есть агрегаты и подсказки по потребностям.
    enough: bool
    placement: Placement | None
    hints: tuple[Hint, ...]


@dataclass(frozen=True)
class FeedbackRules:
    """Параметры обратной связи из `config/mechanics.yaml`."""

    # k — `feedback_min_companies`.
    min_companies: int
    period_days: int
    hints_max: int
    min_gain: float
    # Уровень темы, которой нет в профиле, — как в подборке.
    missing_level: Normal


# Прогноз уровня темы после блока по ней; None — блоку нечем спросить тему.
Narrowed = Callable[[str], Normal | None]


def companies(selections: Collection[CandidateSelection]) -> int:
    return len({s.owner for s in selections})


def placement(selections: Sequence[CandidateSelection]) -> Placement | None:
    if not selections:
        return None
    exact = sum(s.block is SelectionBlock.exact for s in selections)
    return Placement(
        selections=len(selections),
        median_position=float(statistics.median(s.position for s in selections)),
        exact_share=exact / len(selections),
    )


def latest_per_need(selections: Sequence[CandidateSelection]) -> list[CandidateSelection]:
    """Каждая потребность — один раз, по последней подборке; подборка без потребности — сама по
    себе. Порядок — первого появления потребности."""
    latest: dict[uuid.UUID, CandidateSelection] = {}
    for s in selections:
        key = s.need_id or s.selection_id
        if key not in latest or s.created_at > latest[key].created_at:
            latest[key] = s
    return list(latest.values())


@dataclass(frozen=True)
class _Need:
    requirements: tuple[Requirement, ...]
    stack: tuple[str, ...]
    stack_cap: float
    neighbors: tuple[float, ...]


def topic_hints(
    selections: Sequence[CandidateSelection],
    *,
    specialization: str,
    topics: Sequence[CatalogRef],
    levels: Mapping[str, Normal],
    candidate_stack: Collection[str],
    narrowed: Narrowed,
    rules: FeedbackRules,
) -> list[tuple[CatalogRef, Scenario, float, float]]:
    """Темы с лучшим сценарием, средним приростом скора и выигрышем мест — по убыванию прироста,
    не больше `hints_max`, с приростом не меньше `min_gain`. Подборки — уже специализации
    `specialization`.

    Прирост сценария — разность скора на изменённом и текущем уровне, усреднённая по
    потребностям; темы нет в потребности — разность 0. Лучший из двух сценариев — тот, чей
    средний прирост больше; отрицательный не показывается.
    """
    assert all(s.need.specialization.code == specialization for s in selections)
    needs = [
        _Need(
            tuple(Requirement(t.topic.code, t.weight, t.requirement) for t in s.need.topics),
            tuple(t.code for t in s.need.stack),
            s.stack_cap,
            s.neighbors,
        )
        for s in latest_per_need(selections)
    ]
    if not needs:
        return []

    def level(topic: str) -> Normal:
        return levels.get(topic, rules.missing_level)

    def score(need: _Need, changed: Mapping[str, Normal]) -> float:
        current = {
            r.topic: changed[r.topic] if r.topic in changed else level(r.topic)
            for r in need.requirements
        }
        return match_score(
            need.requirements, current, need.stack, candidate_stack, stack_cap=need.stack_cap
        ).score

    base = [score(n, {}) for n in needs]
    # Тема без веса во всех потребностях скор не двигает: прогноз по ней не нужен.
    weighted = {r.topic for n in needs for r in n.requirements if r.weight > 0}
    found = []
    for ref in topics:
        if ref.code not in weighted:
            continue
        now = level(ref.code)
        scenarios = {Scenario.raise_: Normal(now.mean + RAISE_STEP, now.sd)}
        if (forecast := narrowed(ref.code)) is not None:
            scenarios[Scenario.narrow] = Normal(now.mean, forecast.sd)
        outcomes = []
        for scenario, changed in scenarios.items():
            gains, places = [], []
            for need, before in zip(needs, base, strict=True):
                if not any(r.topic == ref.code for r in need.requirements):
                    gains.append(0.0)
                    places.append(0)
                    continue
                after = score(need, {ref.code: changed})
                gains.append(after - before)
                places.append(_below(need.neighbors, after) - _below(need.neighbors, before))
            outcomes.append((sum(gains) / len(needs), sum(places) / len(needs), scenario))
        gain, moved, scenario = max(outcomes, key=lambda o: o[0])
        if gain > 0 and gain >= rules.min_gain:
            found.append((ref, scenario, gain, moved))
    found.sort(key=lambda f: (-f[2], f[0].code))
    return found[: rules.hints_max]


def _below(neighbors: Collection[float], score: float) -> int:
    """Соседей ниже скора — место кандидата среди них, считая снизу."""
    return sum(v < score for v in neighbors)


def widest_topic(topics: Sequence[CatalogRef], levels: Mapping[str, Normal]) -> CatalogRef | None:
    """Тема категории с наибольшей погрешностью; при равенстве — первая по справочнику."""
    known = [t for t in topics if t.code in levels]
    return max(known, key=lambda t: levels[t.code].sd, default=None)


def topic_action(topic: str, task_topics: Collection[str]) -> Action:
    """Регулярное задание по теме, если оно есть; иначе блок по теме — пока недоступен."""
    if topic in task_topics:
        return Action(ActionKind.regular_task, True)
    return Action(ActionKind.topic_block, False)


def feedback(
    selections: Sequence[CandidateSelection],
    *,
    specialization: str | None,
    topics: Sequence[CatalogRef],
    levels: Mapping[str, Normal],
    candidate_stack: Collection[str],
    narrowed: Narrowed,
    task_topics: Collection[str],
    fsp_linked: bool,
    rules: FeedbackRules,
) -> Feedback:
    """Обратная связь по подборкам окна. `specialization` — категории кандидата, None — категории
    нет: профиля и подсказок по темам тоже. `levels` — профиль навыков на «сейчас»,
    `task_topics` — темы доступных кандидату регулярных заданий.

    Порог k, агрегаты и подсказки — по одним и тем же подборкам: специализации категории. Иначе
    подсказки могли бы опереться на меньше чем k компаний, а подборки прежней специализации
    после смены категории смешались бы с текущими."""
    own = [s for s in selections if s.need.specialization.code == specialization]
    enough = specialization is not None and companies(own) >= rules.min_companies
    hints: list[Hint] = []
    if enough:
        assert specialization is not None
        hints += [
            Hint(ref, topic_action(ref.code, task_topics), scenario, gain, moved)
            for ref, scenario, gain, moved in topic_hints(
                own,
                specialization=specialization,
                topics=topics,
                levels=levels,
                candidate_stack=candidate_stack,
                narrowed=narrowed,
                rules=rules,
            )
        ]
    elif specialization is not None and (widest := widest_topic(topics, levels)) is not None:
        hints.append(Hint(widest, topic_action(widest.code, task_topics)))
    if not fsp_linked:
        # У достижений до привязки нет уровня, и отсутствие ФСП не штрафуется (§11): без числа.
        hints.append(Hint(None, Action(ActionKind.link_fsp, True)))
    return Feedback(
        period_days=rules.period_days,
        enough=enough,
        placement=placement(own) if enough else None,
        hints=tuple(hints),
    )
