"""Защищённые признаки (mechanics.md, §17): пол, возраст и вуз не входят ни в одну модель. У
каждой модели — оценки уровня, скора соответствия и модели принятия — рядом с ней объявлен список
признаков; тест сверяет его с тем, что модель на деле получает, и с защищёнными.
"""

import dataclasses
import inspect

import pytest

from app.domain.match import MATCH_FEATURES, match_score
from app.domain.selection import ACCEPTANCE_FEATURES, AcceptanceFeatures
from app.domain.skill import SKILL_MODEL_FEATURES, Observation

PROTECTED = {
    "gender",
    "sex",
    "age",
    "birth_date",
    "birth_year",
    "date_of_birth",
    "university",
    "education",
    "school",
    "photo",
    "nationality",
    "marital_status",
}

MODELS = {
    "оценка уровня": SKILL_MODEL_FEATURES,
    "скор соответствия": MATCH_FEATURES,
    "модель принятия": ACCEPTANCE_FEATURES,
}


@pytest.mark.parametrize("features", MODELS.values(), ids=MODELS.keys())
def test_model_features_have_no_protected(features: tuple[str, ...]) -> None:
    assert features
    assert not set(features) & PROTECTED


def test_acceptance_features_are_declared() -> None:
    # Новое поле признаков без объявления — красный тест.
    assert tuple(f.name for f in dataclasses.fields(AcceptanceFeatures)) == ACCEPTANCE_FEATURES


def test_skill_model_features_are_declared() -> None:
    assert tuple(f.name for f in dataclasses.fields(Observation)) == SKILL_MODEL_FEATURES


def test_match_features_are_declared() -> None:
    # Признаки скора — входы функции; λ — параметр механики, не признак кандидата.
    inputs = tuple(
        name
        for name, p in inspect.signature(match_score).parameters.items()
        if p.kind is not inspect.Parameter.KEYWORD_ONLY
    )
    assert inputs == MATCH_FEATURES
