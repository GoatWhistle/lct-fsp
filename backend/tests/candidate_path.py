"""Путь кандидата к категории через HTTP API — шаги для тестов, которым нужна категория."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.assessment.bank import Family, Instance, families_for_topics
from tests.conftest import Seeds

PATH = "/api/candidate/path"
ITEM = f"{PATH}/item"
WRONG = "ответа нет"

Json = dict[str, Any]


def take_survey(c: TestClient, specialization: str = "qa") -> Json:
    response = c.post(f"{PATH}/survey", json={"specialization": specialization})
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def start(c: TestClient, grade: str) -> Json:
    response = c.post(f"{PATH}/attempts", json={"grade": grade})
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


def presented(seeds: Seeds, item: Json) -> tuple[Family, int]:
    """Семейство и seed показанного задания — по seed, выданным тесту, а не из базы. Экземпляр
    берёт последний seed показа, поэтому поиск идёт от свежих seed; семейство — то, чей экземпляр
    совпал с заданием."""
    candidates = families_for_topics([item["topic"]["code"]])
    for seed in reversed(seeds.issued):
        found = [f for f in candidates if _shows(f.instance(seed), item)]
        if found:
            assert len(found) == 1, (item, [f.code for f in found])
            return found[0], seed
    raise AssertionError(f"задание не выведено ни из одного выданного seed: {item}")


def _shows(instance: Instance, item: Json) -> bool:
    return (instance.prompt, instance.code, list(instance.options)) == (
        item["prompt"],
        item["code"],
        item["options"],
    )


def answer_items(c: TestClient, seeds: Seeds, correct: Callable[[Family], bool]) -> Json:
    """Отвечает на задания до остановки попытки; `correct` решает, отвечать ли верно."""
    path: Json = c.get(PATH).json()
    while path["stage"] == "test":
        item = c.get(ITEM).json()
        assert "id" in item, (item, path)
        family, seed = presented(seeds, item)
        response = family.instance(seed).answer if correct(family) else WRONG
        answered = c.post(
            f"{ITEM}/answer", json={"presentation_id": item["id"], "response": response}
        )
        assert answered.status_code == 200, answered.text
        path = answered.json()
    return path


def everything(_: Family) -> bool:
    return True


def nothing(_: Family) -> bool:
    return False


def pass_test(c: TestClient, seeds: Seeds, grade: str = "middle") -> Json:
    """Кандидат проходит опрос на QA и тест на `grade`, отвечая верно на всё, — категория есть."""
    take_survey(c)
    start(c, grade)
    path = answer_items(c, seeds, everything)
    assert path["stage"] == "category", path
    return path
