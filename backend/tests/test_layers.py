"""Направление зависимостей слоёв (docs/adr/0001-layers-and-ports.md).

`domain` не знает библиотек хранения, схем и HTTP и не тянет их через другие пакеты `app`;
`usecase` не знает реализаций портов и контроллеров; in-memory хранилища не знают SQLAlchemy и
ничего из `app`, кроме домена, портов и себя. Импорты читаются из исходников, а не из
`sys.modules`: так ловится и импорт внутри функции, и импорт под `TYPE_CHECKING`; относительный
импорт сводится к полному имени.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.config import BACKEND_DIR


@dataclass(frozen=True)
class Rule:
    banned: tuple[str, ...]
    allowed: tuple[str, ...] = ()


DOMAIN = Rule(
    banned=("sqlalchemy", "pydantic", "pydantic_settings", "fastapi", "app"),
    allowed=("app.domain",),
)
USECASE = Rule(banned=("app.adapter", "app.repository", "app.controller"))
MEMORY = Rule(
    banned=("sqlalchemy", "app"),
    allowed=("app.domain", "app.usecase", "app.repository.memory"),
)


def _within(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(f"{p}.") for p in prefixes)


def imported_modules(source: str, package: str) -> set[str]:
    """Модули, которые импортирует исходник из пакета `package`, — полными именами."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - node.level + 1]
                base = ".".join([*parts, node.module] if node.module else parts)
            else:
                base = node.module or ""
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


def violations(package: Path, rule: Rule) -> list[str]:
    """Запрещённые импорты в пакете — строками «файл: модуль». Имена модулей считаются от
    каталога, в котором лежит корневой пакет `app`."""
    root = next(p for p in package.parents if p.name == "app").parent
    found = []
    for path in sorted(package.rglob("*.py")):
        # Пакет файла: для `__init__.py` — сам каталог, для модуля — каталог, где он лежит.
        own = ".".join(path.relative_to(root).parent.parts)
        for module in sorted(imported_modules(path.read_text(encoding="utf-8"), own)):
            if _within(module, rule.banned) and not _within(module, rule.allowed):
                found.append(f"{path.relative_to(root)}: {module}")
    return found


@pytest.mark.parametrize(
    ("layer", "rule"),
    [("domain", DOMAIN), ("usecase", USECASE), ("repository/memory", MEMORY)],
)
def test_layer_imports_only_inward(layer: str, rule: Rule) -> None:
    package = BACKEND_DIR / "app" / layer
    assert (package / "__init__.py").is_file(), f"нет пакета app/{layer}"
    assert violations(package, rule) == []


def plant(tmp_path: Path, layer: str, source: str) -> Path:
    package = tmp_path / "app" / layer
    package.mkdir(parents=True)
    for directory in [package, *package.relative_to(tmp_path / "app").parents]:
        (tmp_path / "app" / directory / "__init__.py").write_text("")
    (package / "bad.py").write_text(source)
    return package


MEMORY_PEEKS_AT_SQL = "from ..unit_of_work import SqlUnitOfWork\n"


@pytest.mark.parametrize(
    ("layer", "rule", "source", "caught"),
    [
        ("domain", DOMAIN, "from sqlalchemy.orm import Mapped\n", "sqlalchemy.orm"),
        ("domain", DOMAIN, "def f() -> None:\n    import fastapi\n", "fastapi"),
        ("domain", DOMAIN, "from app.db import Base\n", "app.db"),
        ("domain", DOMAIN, "from ..assessment import models\n", "app.assessment"),
        # Домен получает момент и seed значениями — порты и их реализации ему не видны.
        ("domain", DOMAIN, "from app.usecase.interface import Clock\n", "app.usecase.interface"),
        ("domain", DOMAIN, "from app.adapter.clock import SystemClock\n", "app.adapter.clock"),
        ("domain", DOMAIN, "from ..adapter import seed\n", "app.adapter.seed"),
        ("usecase", USECASE, "from app.repository import users\n", "app.repository"),
        ("usecase", USECASE, "import app.controller.errors\n", "app.controller.errors"),
        ("usecase", USECASE, "from ..controller.errors import STATUS\n", "app.controller.errors"),
        ("repository/memory", MEMORY, "from sqlalchemy.orm import Session\n", "sqlalchemy.orm"),
        ("repository/memory", MEMORY, MEMORY_PEEKS_AT_SQL, "app.repository.unit_of_work"),
    ],
)
def test_planted_violation_is_caught(
    tmp_path: Path, layer: str, rule: Rule, source: str, caught: str
) -> None:
    package = plant(tmp_path, layer, source)

    assert any(v.endswith(f": {caught}") for v in violations(package, rule))


def test_domain_may_import_itself(tmp_path: Path) -> None:
    source = (
        "import pydantic_core_like\n"
        "from app.domain.errors import DomainError\n"
        "from . import catalog\n"
        "from .skill import Normal\n"
    )

    assert violations(plant(tmp_path, "domain", source), DOMAIN) == []


def test_usecase_lookalike_names_are_not_violations(tmp_path: Path) -> None:
    source = "from app.adapters_x import y\nfrom app.domain.errors import DomainError\n"

    assert violations(plant(tmp_path, "usecase", source), USECASE) == []


EXTERNAL = Rule(banned=("smtplib", "fpdf"))


def test_mail_and_pdf_libraries_live_only_in_adapters() -> None:
    """Почта и рендер PDF — за портами: SMTP и fpdf2 импортирует только `app.adapter`."""
    app_dir = BACKEND_DIR / "app"
    packages = [p for p in app_dir.iterdir() if (p / "__init__.py").is_file()]
    found = [v for p in sorted(packages) if p.name != "adapter" for v in violations(p, EXTERNAL)]
    for path in sorted(app_dir.glob("*.py")):
        modules = imported_modules(path.read_text(encoding="utf-8"), "app")
        found += [f"{path.name}: {m}" for m in sorted(modules) if _within(m, EXTERNAL.banned)]
    assert found == []
