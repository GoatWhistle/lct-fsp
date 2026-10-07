"""Экземпляры банка не меняются: тот же seed даёт тот же экземпляр и ту же проверку ответа
(mechanics.md, §5). На seed из предъявлений стоят проверка ответа и калибровка, поэтому снимок
`data/bank_snapshot.json` пополняется только новым семейством — другой генератор старого
семейства тест ловит.

Пересобрать снимок после нового семейства: `uv run python -m tests.test_bank_snapshot`.
"""

import hashlib
import json
from pathlib import Path

import pytest

from app.assessment.bank import BANK, RETIRED, Family

SNAPSHOT = Path(__file__).parent / "data" / "bank_snapshot.json"
SEEDS = range(50)
FAMILIES = (*BANK, *RETIRED)


def fingerprint(family: Family) -> str:
    """Отпечаток семейства: метаданные, экземпляры по seed и проверка эталона и чужого ответа."""
    digest = hashlib.sha256()
    meta = [family.code, family.topic, family.grade, family.anchor]
    digest.update(json.dumps(meta, ensure_ascii=False).encode())
    for seed in SEEDS:
        instance = family.instance(seed)
        checks = [family.check(instance, instance.answer), family.check(instance, "0")]
        record = [
            instance.prompt,
            instance.answer,
            instance.params,
            instance.code,
            list(instance.options),
            checks,
        ]
        digest.update(json.dumps(record, ensure_ascii=False, sort_keys=True).encode())
    return digest.hexdigest()


def expected() -> dict[str, str]:
    snapshot: dict[str, str] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return snapshot


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.code)
def test_seed_gives_same_instance_as_in_snapshot(family: Family) -> None:
    assert fingerprint(family) == expected().get(family.code)


def test_snapshot_lists_exactly_the_bank() -> None:
    assert set(expected()) == {f.code for f in FAMILIES}


if __name__ == "__main__":
    snapshot = {f.code: fingerprint(f) for f in FAMILIES}
    text = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
    SNAPSHOT.write_text(text + "\n", encoding="utf-8")
