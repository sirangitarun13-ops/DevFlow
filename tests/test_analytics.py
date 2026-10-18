"""Isolated tests for project analytics aggregation and authorization."""

from collections.abc import Generator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.auth import Role, User
from backend.app.services.auth_service import create_access_token, hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def database(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        manager_role = Role(code="project_manager", name="Project Manager")
        client_role = Role(code="client", name="Client")
        manager = User(full_name="Manager", email="analytics-manager@example.com", password_hash=hash_password("password-123"), roles=[manager_role])
        client = User(full_name="Client", email="analytics-client@example.com", password_hash=hash_password("password-123"), roles=[client_role])
        db.add_all([manager_role, client_role, manager, client])
        db.commit()
    monkeypatch.setattr(settings, "jwt_secret_key", "analytics-test-secret")
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override() -> Generator[Session, None, None]:
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def headers(email: str) -> dict[str, str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_summary_aggregates_statuses_progress_and_rcia(client: TestClient) -> None:
    manager_headers = headers("analytics-manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Metrics", "status": "active"}).json()
    project_id = project["id"]
    requirement = client.post(
        f"/api/v1/projects/{project_id}/requirements",
        headers=manager_headers,
        json={"requirement_key": "REQ-1", "title": "One", "description": "One", "requirement_type": "functional", "priority": "high", "status": "completed"},
    ).json()
    client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json={"title": "Done", "priority": "low", "status": "completed", "requirement_id": requirement["id"]})
    client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json={"title": "Todo", "priority": "medium", "status": "todo"})
    summary = client.get(f"/api/v1/projects/{project_id}/analytics/summary", headers=manager_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["project"]["progress_percent"] == 50.0
    assert body["requirements"]["by_status"] == {"completed": 1}
    assert body["tasks"]["by_status"] == {"completed": 1, "todo": 1}
    assert body["tasks"]["total"] == 2
    assert body["impact_analysis"]["total_analyses"] == 0


def test_empty_project_has_zero_progress_without_division_error(client: TestClient) -> None:
    manager_headers = headers("analytics-manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Empty"}).json()
    body = client.get(f"/api/v1/projects/{project['id']}/analytics/summary", headers=manager_headers).json()
    assert body["project"]["progress_percent"] == 0.0
    assert body["tasks"] == {"total": 0, "by_status": {}}
    assert body["bugs"] == {"total": 0, "by_status": {}}
    assert body["test_cases"] == {"total": 0, "by_status": {}}


def test_analytics_requires_project_access_and_is_deterministic(client: TestClient) -> None:
    manager_headers = headers("analytics-manager@example.com")
    client_headers = headers("analytics-client@example.com")
    first = client.post("/api/v1/projects", headers=manager_headers, json={"name": "First"}).json()
    second = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Second"}).json()
    assert client.get(f"/api/v1/projects/{first['id']}/analytics/summary", headers=client_headers).status_code == 403
    first_body = client.get(f"/api/v1/projects/{first['id']}/analytics/summary", headers=manager_headers).json()
    second_body = client.get(f"/api/v1/projects/{first['id']}/analytics/summary", headers=manager_headers).json()
    assert {key: value for key, value in first_body.items() if key != "generated_at"} == {key: value for key, value in second_body.items() if key != "generated_at"}
    assert first_body["project"]["id"] == first["id"]
    assert first["id"] != second["id"]
