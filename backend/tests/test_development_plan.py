"""План развития на модели (mechanics.md, §15–§16): сверка ответа, состав промпта, кэш."""

import json
import uuid

from app.adapter.text_model import ModelRequest
from app.domain.catalog import CatalogRef
from app.domain.development_plan import fingerprint, prompt, read_plan
from app.domain.feedback import Action, ActionKind, Feedback, Hint, Scenario
from app.usecase.development_plan import DevelopmentPlans

HINTS = (
    Hint(
        CatalogRef("qa.api", "Тестирование API"),
        Action(ActionKind.topic_block, True),
        Scenario.raise_,
        0.08,
        3.0,
    ),
    Hint(
        CatalogRef("qa.databases", "Базы данных"),
        Action(ActionKind.regular_task, True),
        Scenario.narrow,
        0.05,
        2.0,
    ),
    Hint(None, Action(ActionKind.link_fsp, True)),
)


def steps(*topics: str) -> str:
    return json.dumps({"steps": [{"topic": t, "step": f"Шаг по {t}"} for t in topics]})


def test_plan_with_hint_topics_is_accepted() -> None:
    plan = read_plan(steps("qa.api", "qa.databases", "qa.api"), HINTS)
    assert plan is not None and [s.topic for s in plan.steps] == [
        "qa.api",
        "qa.databases",
        "qa.api",
    ]


def test_topic_outside_hints_rejects_the_whole_plan() -> None:
    assert read_plan(steps("qa.api", "qa.databases", "devops.iac"), HINTS) is None


def test_substituted_or_broken_answers_are_rejected() -> None:
    assert read_plan("не json", HINTS) is None
    assert read_plan(json.dumps({"steps": "x"}), HINTS) is None
    assert read_plan(steps("qa.api", "qa.databases"), HINTS) is None
    assert read_plan(steps(*["qa.api"] * 6), HINTS) is None
    empty = json.dumps({"steps": [{"topic": "qa.api", "step": " "}] * 3})
    assert read_plan(empty, HINTS) is None


def test_prompt_has_only_candidate_numbers() -> None:
    data = json.loads(prompt(HINTS))
    assert [r["topic"] for r in data] == ["qa.api", "qa.databases"]
    assert set(data[0]) == {"topic", "name", "action", "gain_percent"}
    text = prompt(HINTS).lower()
    for forbidden in ("employer", "работодател", "компани", "потребност", "salary"):
        assert forbidden not in text


def test_cache_key_changes_with_the_skill_profile() -> None:
    levels = {"qa.api": (0.1, 0.4)}
    same = fingerprint(HINTS, dict(levels))
    assert same == fingerprint(HINTS, dict(levels))
    assert same != fingerprint(HINTS, {"qa.api": (0.6, 0.4)})
    assert same != fingerprint(HINTS[:1], dict(levels))


class FakeFeedback:
    """Обратная связь с подменяемым профилем: только то, что читает сценарий плана."""

    def __init__(self) -> None:
        self.levels_now = {"qa.api": (0.1, 0.4)}

    def own(self, candidate_id: uuid.UUID) -> Feedback:
        return Feedback(period_days=30, enough=True, placement=None, hints=HINTS)

    def levels(self, candidate_id: uuid.UUID) -> dict[str, tuple[float, float]]:
        return self.levels_now


def make(answer: str, calls: list[ModelRequest]) -> tuple[FakeFeedback, DevelopmentPlans]:
    def complete(request: ModelRequest) -> str:
        calls.append(request)
        return answer

    feedback = FakeFeedback()
    return feedback, DevelopmentPlans(feedback, complete, timeout=2.0)  # type: ignore[arg-type]


def test_plan_is_cached_until_the_profile_changes() -> None:
    calls: list[ModelRequest] = []
    feedback, plans = make(steps("qa.api", "qa.databases", "qa.api"), calls)
    me = uuid.uuid4()

    first = plans.own(me)
    assert first is not None and plans.own(me) == first
    assert len(calls) == 1

    feedback.levels_now = {"qa.api": (0.7, 0.3)}
    plans.own(me)
    assert len(calls) == 2


def test_substituted_model_answer_gives_no_plan() -> None:
    calls: list[ModelRequest] = []
    _, plans = make(steps("qa.api", "qa.databases", "devops.iac"), calls)
    assert plans.own(uuid.uuid4()) is None


def test_without_a_model_there_is_no_plan() -> None:
    plans = DevelopmentPlans(FakeFeedback(), None, timeout=1.0)  # type: ignore[arg-type]
    assert plans.own(uuid.uuid4()) is None


def test_model_failure_gives_no_plan() -> None:
    def broken(_: ModelRequest) -> str:
        raise RuntimeError("упала")

    plans = DevelopmentPlans(FakeFeedback(), broken, timeout=1.0)  # type: ignore[arg-type]
    assert plans.own(uuid.uuid4()) is None
