"""Базовые линии стенда (docs/validation-plan.md, «Базовые линии»): BM25 на известном примере,
кэш B3 — попадание, промах и сменившийся запрос, двойники M3 и M5 и статистики M3, M20."""

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from app.adapter.text_model import ModelError, ModelRequest
from settings import Mechanics, Settings
from validation.baselines import (
    Bm25,
    Document,
    Embeddings,
    LlmRanker,
    MissingScore,
    ScoreCache,
    b3_request,
    record,
    resume_text,
)
from validation.main import catalog
from validation.metrics import quantile, spearman, weighted_kappa
from validation.population import D1, Generator
from validation.report import Places
from validation.truth import Persona
from validation.twins import TwinKind, twins

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
CATALOG = catalog()


def doc(text: str, key: str = "k") -> Document:
    return Document(key, text)


def test_bm25_scores_known_example() -> None:
    """N = 3, df(python) = 2: IDF = ln(1,5 / 2,5 + 1); средняя длина 7/3, k1 = 1,5, b = 0,75."""
    bm25 = Bm25(["python fastapi", "java spring", "python django python"])
    query = doc("Python")

    assert bm25.score(query, doc("python django python")) == pytest.approx(0.614958, abs=1e-6)
    assert bm25.score(query, doc("python fastapi")) == pytest.approx(0.502294, abs=1e-6)
    assert bm25.score(query, doc("java spring")) == 0.0


def test_bm25_rare_word_outweighs_common() -> None:
    bm25 = Bm25(["python fastapi", "python django", "python kafka", "go kafka"])

    assert bm25.score(doc("fastapi python"), doc("python fastapi")) > bm25.score(
        doc("fastapi python"), doc("python django")
    )


def test_embeddings_score_is_dot_of_prefixed_texts() -> None:
    seen: list[str] = []

    def encode(texts: list[str]) -> list[list[float]]:
        seen.extend(texts)
        return [[1.0, 0.0] if t.startswith("query: ") else [0.6, 0.8] for t in texts]

    b2 = Embeddings(encode)  # type: ignore[arg-type]

    assert b2.score(doc("вакансия"), doc("резюме")) == pytest.approx(0.6)
    assert sorted(seen) == ["passage: резюме", "query: вакансия"]
    b2.score(doc("вакансия"), doc("резюме"))
    assert len(seen) == 2


class Model:
    model = "claude-sonnet-5-5"

    def __init__(self, score: int = 7) -> None:
        self.score = score
        self.asked: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> str:
        self.asked.append(request)
        return json.dumps({"score": self.score})


NEED, RESUME = doc("Middle бэкенд", "need-1"), doc("Python, 5 лет", "cand-1")


def test_b3_cache_hit_answers_without_model_after_reload(tmp_path: Path) -> None:
    path = tmp_path / "b3.d1.json"
    first = LlmRanker(ScoreCache(path, 1), Model(7))
    first.score(NEED, RESUME)
    first.cache.save()
    replay = LlmRanker(ScoreCache(path, 1))

    assert replay.score(NEED, RESUME) == 7.0
    assert replay.cache.model == "claude-sonnet-5-5"
    assert replay.cache.first is not None


def test_b3_cache_miss_is_an_error_not_a_skip(tmp_path: Path) -> None:
    ranker = LlmRanker(ScoreCache(tmp_path / "b3.d1.json", 1))

    with pytest.raises(MissingScore, match="нет ответа"):
        ranker.score(NEED, RESUME)


def test_b3_changed_request_is_a_miss(tmp_path: Path) -> None:
    path = tmp_path / "b3.d1.json"
    live = LlmRanker(ScoreCache(path, 1), Model(7))
    live.score(NEED, RESUME)
    live.cache.save()

    with pytest.raises(MissingScore, match="запрос изменился"):
        LlmRanker(ScoreCache(path, 1)).score(NEED, doc("Python, 6 лет", RESUME.key))


def test_b3_cache_belongs_to_one_seed(tmp_path: Path) -> None:
    path = tmp_path / "b3.d1.json"
    ranker = LlmRanker(ScoreCache(path, 1), Model())
    ranker.score(NEED, RESUME)
    ranker.cache.save()

    with pytest.raises(ValueError, match="сида"):
        ScoreCache(path, 2)


def test_b3_record_asks_only_missing_and_keeps_failures_out(tmp_path: Path) -> None:
    class Flaky(Model):
        def __call__(self, request: ModelRequest) -> str:
            answer = super().__call__(request)
            if "сбой" in request.user:
                raise ModelError("нет ответа")
            return answer

    live = Flaky()
    ranker = LlmRanker(ScoreCache(tmp_path / "b3.d1.json", 1), live)
    ranker.score(NEED, RESUME)
    pairs = [(NEED, RESUME), (NEED, doc("Go", "cand-2")), (NEED, doc("сбой", "cand-3"))]

    added, failed = record(ranker, pairs, workers=2)

    assert (added, failed) == (1, 1)
    assert len(live.asked) == 3
    assert set(LlmRanker(ScoreCache(tmp_path / "b3.d1.json", 1)).cache.answers) == {
        "need-1:cand-1",
        "need-1:cand-2",
    }


def test_b3_rejects_score_outside_scale(tmp_path: Path) -> None:
    ranker = LlmRanker(ScoreCache(tmp_path / "b3.d1.json", 1), Model(11))

    with pytest.raises(ModelError):
        ranker.score(NEED, RESUME)


def test_b3_request_keeps_texts_as_data() -> None:
    request = b3_request(NEED, RESUME)

    assert NEED.text not in request.system
    assert NEED.text in request.user and RESUME.text in request.user


@pytest.fixture(scope="module")
def dataset():  # type: ignore[no-untyped-def]
    params = replace(D1, candidates_per_specialization=20)
    return Generator(params, MECHANICS, CATALOG).generate()


def test_inflated_twin_copies_need_stack_and_title_only(dataset) -> None:  # type: ignore[no-untyped-def]
    truth = {t.id: t for t in dataset.truths}
    seen = {o.id: o for o in dataset.observed}
    needs = {n.id: n for n in dataset.needs}
    inflated = [tw for tw in twins(dataset, CATALOG) if tw.kind == TwinKind.inflated]

    assert inflated
    for tw in inflated:
        source, form = seen[tw.source], needs[tw.need].form
        assert truth[tw.source].persona == Persona.honest
        assert set(form.stack) <= set(tw.observed.stack)
        assert set(source.stack) <= set(tw.observed.stack)
        assert form.title in tw.observed.about
        assert tw.observed.person == source.person
        assert tw.observed.answers == source.answers


def test_protected_twin_flips_gender_age_and_university_only(dataset) -> None:  # type: ignore[no-untyped-def]
    seen = {o.id: o for o in dataset.observed}
    protected = [tw for tw in twins(dataset, CATALOG) if tw.kind == TwinKind.protected]

    assert len(protected) == len(CATALOG.specializations) * 20
    for tw in protected:
        a, b = seen[tw.source].person, tw.observed.person
        assert (a.gender != b.gender, a.older != b.older, a.leading != b.leading) == (
            True,
            True,
            True,
        )
        assert a.name.split()[1].rstrip("а") == b.name.split()[1].rstrip("а")
        assert replace(tw.observed, person=a, id=tw.source) == seen[tw.source]
        assert resume_text(tw.observed) != resume_text(seen[tw.source])


def test_twins_are_the_same_for_the_same_seed(dataset) -> None:  # type: ignore[no-untyped-def]
    assert twins(dataset, CATALOG) == twins(dataset, CATALOG)


def test_personal_data_does_not_shift_rest_of_observed(dataset) -> None:  # type: ignore[no-untyped-def]
    """Личные данные — свой поток: имя, возраст и вуз не зависят от истины, а ответы, стек и
    стаж — те же, что без них."""
    ages = {o.person.older for o in dataset.observed}
    assert ages == {True, False}
    assert all(o.person.age >= 21 + o.experience_years for o in dataset.observed)


def test_percentile_place_excludes_replaced_candidate() -> None:
    places = Places([1.0, 2.0, 3.0, 4.0, 5.0])

    assert places.of(3.0, 3.0) == 50.0
    assert places.of(5.5, 3.0) == 100.0
    assert places.of(5.0, 5.0) == 100.0
    # Вровень с другим кандидатом — половина ничьей.
    assert places.of(5.0, 1.0) == 87.5
    # Вне выдачи — вровень ниже всех: двойник вне выдачи стоит там же, где кандидат.
    outside = Places([-math.inf, -math.inf, 1.0])
    assert outside.of(-math.inf, -math.inf) == 25.0


def test_statistics_on_known_values() -> None:
    assert quantile([1, 2, 3, 4], 0.9) == pytest.approx(3.7)
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert weighted_kappa([(0, 0), (1, 1), (2, 2), (3, 3)], 4) == pytest.approx(1.0)
    # Сдвиг на один шаг у всех пар — согласие ниже полного, но выше нуля.
    shifted = weighted_kappa([(0, 1), (1, 2), (2, 3), (3, 3)], 4)
    assert 0 < shifted < 1


@pytest.mark.parametrize("raw", ["не json", "[]", '{"оценка": 5}', '{"score": true}'])
def test_b3_answer_off_schema_is_a_model_failure(tmp_path: Path, raw: str) -> None:
    class Broken(Model):
        def __call__(self, request: ModelRequest) -> str:
            return raw

    ranker = LlmRanker(ScoreCache(tmp_path / "b3.d1.json", 1), Broken())

    assert record(ranker, [(NEED, RESUME)], workers=1) == (0, 1)
    assert (tmp_path / "b3.d1.json").exists()
