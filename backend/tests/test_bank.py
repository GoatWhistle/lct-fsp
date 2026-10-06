"""Банк семейств: экземпляр воспроизводим по seed, эталон проверяется кодом (mechanics.md, §5)."""

import json

import pytest

from app.assessment.bank import BANK, Family, covers, same_answer
from app.assessment.catalog import load_catalog

SEEDS = range(200)
TOPICS = {s.code: [t.code for t in s.topics] for s in load_catalog().specializations}


@pytest.mark.parametrize("family", BANK, ids=lambda f: f.code)
def test_instance_is_reproducible_and_checks_its_own_answer(family: Family) -> None:
    for seed in SEEDS:
        instance = family.instance(seed)

        assert family.instance(seed) == instance
        assert instance.prompt and instance.answer
        assert family.check(instance, f"  {instance.answer.upper()} ")
        assert not family.check(instance, instance.answer + "1")
        # Параметры экземпляра пишутся в предъявление — должны сериализоваться.
        json.dumps(instance.params)


@pytest.mark.parametrize("family", BANK, ids=lambda f: f.code)
def test_family_has_different_instances(family: Family) -> None:
    prompts = {(family.instance(s).prompt, family.instance(s).code) for s in SEEDS}

    assert len(prompts) >= 20


def test_family_codes_are_unique_and_namespaced_by_topic() -> None:
    codes = [f.code for f in BANK]

    assert len(set(codes)) == len(codes)
    for family in BANK:
        assert family.code.startswith(f"{family.topic}.")


def test_bank_covers_backend_and_qa_only() -> None:
    assert {s for s, topics in TOPICS.items() if covers(topics)} == {"backend", "qa"}
    assert {f.topic for f in BANK} <= {t for topics in TOPICS.values() for t in topics}


@pytest.mark.parametrize(
    ("response", "answer", "same"),
    [
        ("7", "7", True),
        (" 7,0 ", "7", True),
        ("7.5", "7,5", True),
        ("abcd", "ABCD", True),
        ("A B C D", "ABCD", True),
        ("8", "7", False),
        ("", "0", False),
    ],
)
def test_same_answer(response: str, answer: str, same: bool) -> None:
    assert same_answer(response, answer) is same
