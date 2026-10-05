from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.identity.models import Role


@pytest.mark.parametrize(
    ("role", "own", "foreign"),
    [
        (Role.candidate, "/api/candidate/cabinet", "/api/employer/cabinet"),
        (Role.employer, "/api/employer/cabinet", "/api/candidate/cabinet"),
    ],
)
def test_each_role_reaches_only_its_own_api(
    signed_in: Callable[[Role], TestClient], role: Role, own: str, foreign: str
) -> None:
    client = signed_in(role)

    assert client.get(own).status_code == 200
    response = client.get(foreign)
    assert response.status_code == 403
    assert response.json()["code"] == "wrong_role"


@pytest.mark.parametrize("path", ["/api/candidate/cabinet", "/api/employer/cabinet"])
def test_role_api_requires_sign_in(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
