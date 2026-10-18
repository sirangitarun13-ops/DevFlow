"""Phase 2 tests that do not require a live PostgreSQL server."""

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_application_imports_and_metadata() -> None:
    assert app.title == "DevFlow API"
    assert app.version == "0.1.0"


def test_root_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "DevFlow API"
    assert response.json()["status"] == "ok"


def test_versioned_root_endpoint() -> None:
    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert response.json()["name"] == "DevFlow API"
    assert response.json()["status"] == "ok"


def test_health_endpoint_does_not_require_database() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "database": "not_checked",
    }


def test_frontend_origin_is_allowed_for_browser_integration() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
