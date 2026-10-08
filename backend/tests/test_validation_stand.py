"""Стенд валидации — те же сценарии, что HTTP, на своей сборке (docs/adr/0001-layers-and-ports.md).

Прод стенд не импортирует; подборка строится на синтетических кандидатах, прошедших тест через
сценарии; прогон с одним seed воспроизводим и в пуле процессов.
"""

import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from app.config import BACKEND_DIR, Mechanics, Settings
from app.domain.selection import Need
from app.domain.work import SalaryRange, WorkFormat
from tests.test_layers import Rule, imported_modules, violations
from validation.commands import Honesty, Stability, honesty, stability
from validation.market import market

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
STAND = Rule(banned=("validation",))


def test_production_does_not_import_stand() -> None:
    """`main`, `composition` и `app` не импортируют пакет стенда: базовые линии и локальная LLM
    стенда в прод не попадают."""
    app_dir = BACKEND_DIR / "app"
    packages = [p for p in app_dir.iterdir() if (p / "__init__.py").is_file()]
    found = [v for p in sorted(packages) for v in violations(p, STAND)]
    modules = [
        *((path, "app") for path in sorted(app_dir.glob("*.py"))),
        (BACKEND_DIR / "main.py", ""),
        (BACKEND_DIR / "composition.py", ""),
    ]
    for path, package in modules:
        imported = imported_modules(path.read_text(encoding="utf-8"), package)
        found += [f"{path.name}: {m}" for m in sorted(imported) if m.split(".")[0] == "validation"]
    assert found == []


def test_planted_stand_import_is_caught(tmp_path: Path) -> None:
    package = tmp_path / "app" / "usecase"
    package.mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "bad.py").write_text("def f() -> None:\n    from validation.market import SEED\n")

    assert "app/usecase/bad.py: validation.market" in violations(package, STAND)


def test_selection_builds_on_synthetic_candidates() -> None:
    """Кандидаты проходят тест через сценарии стенда, с категорией идут в пул; сценарий подборки
    стенда строит по ним выдачу."""
    m = market("qa", MECHANICS)
    users = [m.determine(m.candidate()).user for _ in range(20)]
    enlisted = [u for u in users if m.enlist(u)]
    stand = m.stand
    employer = uuid.UUID(int=10**6)
    qa = stand.catalog.specializations["qa"]
    need = Need(
        id=uuid.UUID(int=10**6 + 1),
        title="QA-инженер",
        specialization=qa,
        grade=stand.catalog.grades["middle"],
        stack=(stand.catalog.technologies["pytest"],),
        edited_importance={},
        work_format=WorkFormat.remote,
        city=None,
        salary=SalaryRange(150_000, 250_000),
        updated_at=stand.clock.now(),
    )
    stand.needs.put(employer, need)

    page = stand.selections().build(employer, need.id, limit=len(enlisted))

    assert enlisted
    assert {e.candidate_id for e in page.entries} <= set(enlisted)
    assert page.entries


def _job(seed: int) -> tuple[Honesty, Stability]:
    """Короткий прогон D1 с калибровкой, затем замеры на замороженном банке."""
    m = market("frontend", MECHANICS, seed)
    for _ in range(30):
        m.attempt(m.candidate())
    m.calibrate = False
    return honesty(m, 10), stability(m, 5)


def test_same_seed_gives_same_numbers_across_processes() -> None:
    with ProcessPoolExecutor(2) as pool:
        first, second = pool.map(_job, [7, 7])

    # Каппа без разброса категорий — nan, а nan не равен себе: сравниваются записи чисел.
    assert repr(first) == repr(second)
    assert repr(_job(8)) != repr(first)
