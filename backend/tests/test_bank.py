"""Банк семейств: экземпляр воспроизводим по seed, эталон проверяется кодом, верный ответ одного
экземпляра не подходит к другому, банк покрывает справочник (mechanics.md, §5)."""

import json
import random
from collections import Counter
from decimal import Decimal, InvalidOperation

import pytest

from app.adapter.catalog_file import load_catalog
from app.adapter.code_runner import InProcessCodeRunner
from app.domain.bank import (
    BANK,
    RETIRED,
    AnswerFormat,
    Family,
    Kind,
    covers,
    families_for_topics,
    get_family,
)
from app.domain.bank.family import same_answer, values
from settings import CATALOG_FILE, Mechanics, Settings

SEEDS = range(200)
RUNNER = InProcessCodeRunner()
# Совпадения ответов считаются на большей выборке: доля около 4 % на 200 экземплярах шумит.
COLLISION_SEEDS = range(500)
TOPICS = {s.code: [t.code for t in s.topics] for s in load_catalog(CATALOG_FILE).specializations}
MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)


@pytest.mark.parametrize("family", BANK, ids=lambda f: f.code)
def test_instance_is_reproducible_and_checks_its_own_answer(family: Family) -> None:
    for seed in SEEDS:
        instance = family.instance(seed, RUNNER)

        assert family.instance(seed, RUNNER) == instance
        assert instance.prompt and instance.answer
        assert family.check(instance, f"  {instance.answer.upper()} ")
        assert not family.check(instance, instance.answer + "1")
        # Параметры экземпляра пишутся в предъявление — должны сериализоваться.
        json.dumps(instance.params)


@pytest.mark.parametrize("family", BANK, ids=lambda f: f.code)
def test_family_has_different_instances(family: Family) -> None:
    prompts = {(family.instance(s, RUNNER).prompt, family.instance(s, RUNNER).code) for s in SEEDS}

    assert len(prompts) >= 20


def answer_key(answer: str) -> tuple[str, ...]:
    """Ключ эталона: два эталона с одним ключом засчитываются друг за друга (`same_answer`)."""
    parts = values(answer)
    if len(parts) == 1:
        parts = ["".join(answer.split())]
    return tuple(_value_key(p) for p in parts)


def _value_key(value: str) -> str:
    try:
        return str(Decimal(value.lower().replace(",", ".")).normalize())
    except InvalidOperation:
        return value.lower()


@pytest.mark.parametrize("family", BANK, ids=lambda f: f.code)
def test_correct_answer_of_one_instance_rarely_fits_another(family: Family) -> None:
    instances = [family.instance(s, RUNNER) for s in COLLISION_SEEDS]
    counts = Counter(answer_key(i.answer) for i in instances)
    n = len(instances)

    # Доля пар экземпляров, где верный ответ одного засчитывается на другом.
    collision = sum(k * (k - 1) for k in counts.values()) / (n * (n - 1))

    assert collision <= MECHANICS.family_answer_collision_max
    # Ключ совпадает с проверкой ответа: пары с одним ключом засчитываются, с разными — нет.
    rng = random.Random(family.code)
    for _ in range(200):
        one, other = rng.sample(instances, 2)
        same_key = answer_key(one.answer) == answer_key(other.answer)
        assert family.check(other, one.answer) is same_key


def test_family_codes_are_unique_and_namespaced_by_topic() -> None:
    codes = [f.code for f in (*BANK, *RETIRED)]

    assert len(set(codes)) == len(codes)
    for family in (*BANK, *RETIRED):
        assert family.code.startswith(f"{family.topic}.")


def test_every_family_has_kind() -> None:
    for family in (*BANK, *RETIRED):
        assert isinstance(family.kind, Kind), family.code


def test_bank_has_choice_and_ordering_samples() -> None:
    formats = {f.instance(0, RUNNER).answer_format: f.kind for f in BANK}

    assert formats[AnswerFormat.CHOICE] == Kind.SCENARIO_CHOICE
    assert formats[AnswerFormat.ORDERING] == Kind.ORDERING


@pytest.mark.parametrize(
    "family",
    [f for f in BANK if f.instance(0, RUNNER).answer_format != AnswerFormat.VALUE],
    ids=lambda f: f.code,
)
def test_letter_answer_names_options(family: Family) -> None:
    """Выбор — буква одного варианта, перестановка — буквы всех вариантов по разу. Буквы
    вариантов разные и идут по алфавиту, тексты перемешаны."""
    first_positions = set()
    for seed in SEEDS:
        instance = family.instance(seed, RUNNER)
        letters = [o.letter for o in instance.options]

        assert letters == sorted(set(letters))
        assert len({o.text for o in instance.options}) == len(letters) >= 3
        if instance.answer_format == AnswerFormat.CHOICE:
            assert instance.answer in letters
        else:
            assert sorted(instance.answer) == letters
        first_positions.add(letters.index(instance.answer[0]))
        assert family.check(instance, " - ".join(instance.answer.lower()))

    # Верный вариант стоит на разных местах.
    assert len(first_positions) > 1


def test_family_grades_are_catalog_grades() -> None:
    assert {f.grade for f in BANK} == {g.code for g in load_catalog(CATALOG_FILE).grades}


def test_bank_covers_every_specialization() -> None:
    assert all(covers(topics) for topics in TOPICS.values())
    assert {f.topic for f in BANK} == {t for topics in TOPICS.values() for t in topics}


@pytest.mark.parametrize("topic", [t for topics in TOPICS.values() for t in topics])
def test_topic_has_enough_families_for_every_grade_and_anchors(topic: str) -> None:
    families = families_for_topics([topic])
    grades = Counter(f.grade for f in families)

    assert len(families) >= MECHANICS.bank_min_families_per_topic
    for grade in MECHANICS.grade_thresholds:
        assert grades[grade] >= MECHANICS.bank_min_families_per_grade, grade
    assert sum(f.anchor for f in families) == MECHANICS.anchor_families_per_topic


def test_retired_family_is_restored_by_code_but_not_offered() -> None:
    retired = RETIRED[0]

    assert get_family(retired.code) is retired
    assert retired not in families_for_topics([retired.topic])


@pytest.mark.parametrize(
    ("response", "answer", "same"),
    [
        ("7", "7", True),
        (" 7,0 ", "7", True),
        ("7,5", "7.5", True),
        ("abcd", "ABCD", True),
        ("A B C D", "ABCD", True),
        ("8", "7", False),
        ("", "0", False),
        # Ответ из нескольких значений сравнивается поштучно.
        ("12, 3", "12 3", True),
        ("12;3", "12 3", True),
        ("1 23", "12 3", False),
        ("3 12", "12 3", False),
        ("12 3 4", "12 3", False),
        ("12.0 3", "12 3", True),
        # «|» между списками — само значение, пробелы вокруг не важны.
        ("8|9", "8 | 9", True),
        ("app-2 cache-1|нет", "app-2 cache-1 | нет", True),
        ("8 9", "8 | 9", False),
        ("8 | 9", "8 9 |", False),
    ],
)
def test_same_answer(response: str, answer: str, same: bool) -> None:
    assert same_answer(response, answer) is same


@pytest.mark.parametrize(
    ("response", "answer", "same"),
    [
        ("k", "K", True),
        ("bdac", "BDAC", True),
        (" B, D; A-C ", "BDAC", True),
        ("B > D > A > C", "BDAC", True),
        ("В Д А С", "BDAC", False),
        # Кириллические двойники латинских букв читаются латиницей.
        ("ВАС", "BAC", True),
        ("BDCA", "BDAC", False),
        ("BDA", "BDAC", False),
        ("K1", "K", False),
        ("", "K", False),
    ],
)
def test_same_answer_in_letters(response: str, answer: str, same: bool) -> None:
    assert same_answer(response, answer, letters=True) is same


def test_terraform_expressions_with_all_sizes_one() -> None:
    """Все размеры сервисов 1 — порог 2, под него не попадает ни один сервис. Раньше такой seed
    ронял генератор: случайный порог брался из пустого диапазона."""
    family = get_family("devops.iac.tf-expressions")

    instance = family.instance(2085, RUNNER)

    assert set(instance.params["sizes"].values()) == {1}
    assert instance.answer.split()[:2] == ["0", "0"]
