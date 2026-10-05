"""OpenAPI — договор с фронтом: у каждой операции описаны смысл, запрос и ошибки."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def spec(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    result: dict[str, Any] = response.json()
    return result


def operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method.upper(), path, op)
        for path, item in spec["paths"].items()
        for method, op in item.items()
    ]


def test_every_operation_has_summary_and_success_response(spec: dict[str, Any]) -> None:
    for method, path, op in operations(spec):
        assert op.get("summary"), f"{method} {path}: нет summary"
        assert any(code.startswith("2") for code in op["responses"]), f"{method} {path}"


def test_role_apis_document_401_and_403(spec: dict[str, Any]) -> None:
    for method, path, op in operations(spec):
        if path.startswith(("/api/candidate/", "/api/employer/")):
            assert {"401", "403"} <= op["responses"].keys(), f"{method} {path}"


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("POST", "/api/auth/register", {"email_taken"}),
        ("POST", "/api/auth/verify-email", {"token_invalid", "token_expired"}),
        ("POST", "/api/auth/login", {"invalid_credentials", "email_not_verified"}),
        ("GET", "/api/auth/me", {"not_authenticated"}),
        ("GET", "/api/catalog/technologies", {"specialization_not_found"}),
    ],
)
def test_error_codes_are_documented(
    spec: dict[str, Any], method: str, path: str, codes: set[str]
) -> None:
    op = spec["paths"][path][method.lower()]
    documented = " ".join(
        r.get("description", "") for status, r in op["responses"].items() if status[0] in "45"
    )
    for code in codes:
        assert f"`{code}`" in documented, f"{method} {path}: не описана ошибка {code}"
