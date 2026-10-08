"""Точка входа `main`: на уровне модуля только функции сборки, импорт без побочных эффектов."""

import ast
import os
import subprocess
import sys

from settings import BACKEND_DIR

# Импорт `main` в чистом процессе без переменных окружения, где чтение настроек, создание
# движка и любое сетевое соединение — ошибка.
IMPORT_WITHOUT_SIDE_EFFECTS = """
import socket
import pydantic_settings
import sqlalchemy
import sqlalchemy.engine

def forbidden(*args, **kwargs):
    raise AssertionError("импорт main прочитал настройки, создал движок или пошёл в сеть")

pydantic_settings.BaseSettings.__init__ = forbidden
sqlalchemy.create_engine = forbidden
sqlalchemy.engine.create_engine = forbidden
socket.socket.connect = forbidden
socket.create_connection = forbidden

import main

assert callable(main.create_app)
"""


def test_module_level_has_only_function_definitions() -> None:
    tree = ast.parse((BACKEND_DIR / "main.py").read_text(encoding="utf-8"))
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    allowed = (ast.Import, ast.ImportFrom, ast.FunctionDef)
    extra = [ast.unparse(node).splitlines()[0] for node in body if not isinstance(node, allowed)]
    assert extra == []


def test_import_reads_no_config_and_opens_no_database() -> None:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT")}
    env["PYTHONPATH"] = str(BACKEND_DIR)
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_WITHOUT_SIDE_EFFECTS],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
