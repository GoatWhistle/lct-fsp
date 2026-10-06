from fastapi.testclient import TestClient


def test_grades_go_from_intern_to_senior(client: TestClient) -> None:
    grades = client.get("/api/catalog/grades").json()

    assert [g["code"] for g in grades] == ["intern", "junior", "middle", "senior"]
    assert grades[0]["name"] == "Стажёр"


def test_mvp_specializations_have_topics(client: TestClient) -> None:
    specializations = client.get("/api/catalog/specializations").json()

    assert [s["code"] for s in specializations] == [
        "backend",
        "frontend",
        "data-ml",
        "qa",
        "devops",
    ]
    for s in specializations:
        assert s["topics"], f"у специализации {s['code']} нет тем"
    backend = specializations[0]
    assert {"code": "backend.databases", "name": "Базы данных и SQL"} in backend["topics"]


def test_technologies_point_to_topics_of_specializations(client: TestClient) -> None:
    topics = {
        t["code"] for s in client.get("/api/catalog/specializations").json() for t in s["topics"]
    }
    technologies = {t["code"]: t for t in client.get("/api/catalog/technologies").json()}

    assert set(technologies["postgresql"]["topics"]) >= {"backend.databases", "data-ml.sql"}
    for tech in technologies.values():
        assert tech["topics"], f"технология {tech['code']} не связана с темами"
        assert set(tech["topics"]) <= topics


def test_technologies_filtered_by_specialization(client: TestClient) -> None:
    technologies = client.get("/api/catalog/technologies", params={"specialization": "qa"}).json()
    by_code = {t["code"]: t for t in technologies}

    assert "selenium" in by_code
    assert "react" not in by_code
    assert by_code["postgresql"]["topics"] == ["qa.databases"]


def test_unknown_specialization_is_404(client: TestClient) -> None:
    response = client.get("/api/catalog/technologies", params={"specialization": "astrology"})

    assert response.status_code == 404
    assert response.json()["code"] == "specialization_not_found"


def test_industries_are_business_spheres(client: TestClient) -> None:
    industries = client.get("/api/catalog/industries").json()

    assert {"code": "fintech", "name": "Финтех и банки"} in industries
    assert len({i["code"] for i in industries}) == len(industries)


def test_specializations_tell_whether_test_is_ready(client: TestClient) -> None:
    specializations = client.get("/api/catalog/specializations").json()

    # Банк покрывает все специализации справочника — тест готов везде.
    assert all(s["has_test"] for s in specializations)
