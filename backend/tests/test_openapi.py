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
        (
            "POST",
            "/api/candidate/path/survey",
            {"path_step_unavailable", "unknown_specialization", "specialization_without_test"},
        ),
        (
            "POST",
            "/api/candidate/path/attempts",
            {"path_step_unavailable", "grade_not_offered", "unknown_grade"},
        ),
        ("GET", "/api/candidate/path/item", {"no_test_in_progress"}),
        ("POST", "/api/candidate/path/item/answer", {"no_test_in_progress", "item_not_current"}),
        (
            "PUT",
            "/api/candidate/profile",
            {"unknown_technology", "unknown_industry", "city_required"},
        ),
        ("GET", "/api/candidate/profile/pdf", {"profile_not_found"}),
        ("PUT", "/api/employer/company", {"unknown_industry"}),
        (
            "POST",
            "/api/employer/needs",
            {
                "unknown_specialization",
                "unknown_grade",
                "unknown_technology",
                "topic_not_in_specialization",
                "invalid_salary_range",
                "city_required",
            },
        ),
        ("PUT", "/api/employer/needs/{need_id}", {"need_not_found", "invalid_salary_range"}),
        ("DELETE", "/api/employer/needs/{need_id}", {"need_not_found"}),
        ("GET", "/api/employer/candidates/{candidate_id}", {"candidate_not_found"}),
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


def _schemas_from(spec: dict[str, Any], roots: list[Any]) -> dict[str, dict[str, Any]]:
    """Компоненты схем, достижимые по `$ref` из `roots`."""
    components = spec["components"]["schemas"]
    found: dict[str, dict[str, Any]] = {}
    stack = list(roots)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if ref := node.get("$ref"):
                name = ref.rsplit("/", 1)[-1]
                if name not in found:
                    found[name] = components[name]
                    stack.append(components[name])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _salary_fields(schema: dict[str, Any]) -> list[str]:
    return [name for name in schema.get("properties", {}) if name in ("salary_from", "salary_to")]


def test_every_response_with_money_says_gross_or_net(spec: dict[str, Any]) -> None:
    """Организаторы: гросс или нетто — непринципиально, лишь бы подписано. Каждый ответ с
    суммой несёт `salary_basis`."""
    responses = [
        response.get("content", {})
        for _, _, op in operations(spec)
        for status, response in op["responses"].items()
        if status.startswith("2")
    ]
    with_money = {
        name: schema
        for name, schema in _schemas_from(spec, responses).items()
        if _salary_fields(schema)
    }

    assert with_money, "в ответах API не нашлось ни одной суммы"
    for name, schema in with_money.items():
        assert "salary_basis" in schema.get("required", []), name


def test_every_request_with_money_says_gross_or_net(spec: dict[str, Any]) -> None:
    bodies = [op["requestBody"]["content"] for _, _, op in operations(spec) if "requestBody" in op]
    with_money = {
        name: schema
        for name, schema in _schemas_from(spec, bodies).items()
        if _salary_fields(schema)
    }

    assert with_money, "в запросах API не нашлось ни одной суммы"
    for name, schema in with_money.items():
        for field in _salary_fields(schema):
            description = schema["properties"][field].get("description", "")
            assert "до вычета НДФЛ" in description, f"{name}.{field}"
