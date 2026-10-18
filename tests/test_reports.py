"""Isolated PDF report endpoint tests."""

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
from backend.app.models.core import project_members
from backend.app.models.rcia import ImpactAnalysisResult
from backend.app.services.auth_service import create_access_token, hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def database(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        manager_role = Role(code="project_manager", name="Project Manager")
        client_role = Role(code="client", name="Client")
        manager = User(full_name="Manager", email="reports-manager@example.com", password_hash=hash_password("password-123"), roles=[manager_role])
        client = User(full_name="Client", email="reports-client@example.com", password_hash=hash_password("password-123"), roles=[client_role])
        db.add_all([manager_role, client_role, manager, client]); db.commit()
    monkeypatch.setattr(settings, "jwt_secret_key", "reports-test-secret")
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
        user = db.scalar(select(User).where(User.email == email)); assert user is not None
        return {"Authorization": f"Bearer {create_access_token(user)}"}


def setup_project(client: TestClient) -> tuple[str, str, str]:
    auth = headers("reports-manager@example.com")
    project = client.post("/api/v1/projects", headers=auth, json={"name": "Reports", "description": "Reporting project", "status": "active"}).json()
    requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=auth, json={"requirement_key": "REQ-1", "title": "Export data", "description": "Export project data", "requirement_type": "functional", "priority": "high"}).json()
    change = client.post(f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}/change-requests", headers=auth, json={"change_summary": "Change export format", "proposed_description": "Use CSV"}).json()
    return project["id"], requirement["id"], change["id"]


def test_project_and_sdlc_reports_return_meaningful_pdf(client: TestClient) -> None:
    project_id, _, _ = setup_project(client); auth = headers("reports-manager@example.com")
    summary = client.get(f"/api/v1/projects/{project_id}/reports/project-summary", headers=auth)
    sdlc = client.get(f"/api/v1/projects/{project_id}/reports/sdlc-status", headers=auth)
    for response in (summary, sdlc):
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF-")
        assert len(response.content) > 1500


def test_change_impact_report_without_analysis_is_explicit(client: TestClient) -> None:
    project_id, _, change_id = setup_project(client); auth = headers("reports-manager@example.com")
    response = client.get(f"/api/v1/projects/{project_id}/reports/change-impact/{change_id}", headers=auth)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 1500


def test_change_impact_report_uses_existing_analysis_and_is_project_scoped(client: TestClient) -> None:
    project_id, requirement_id, change_id = setup_project(client); auth = headers("reports-manager@example.com")
    task = client.post(f"/api/v1/projects/{project_id}/tasks", headers=auth, json={"title": "Implement export", "priority": "high"}).json()
    link = client.post(f"/api/v1/projects/{project_id}/traceability-links", headers=auth, json={"source_artifact_type": "requirement", "source_artifact_id": requirement_id, "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "implements"})
    assert link.status_code == 201
    analysis = client.post(f"/api/v1/projects/{project_id}/change-requests/{change_id}/analyses", headers=auth)
    assert analysis.status_code == 201
    second_task = client.post(f"/api/v1/projects/{project_id}/tasks", headers=auth, json={"title": "Review export", "priority": "low"}).json()
    with SessionLocal() as db:
        db.add(ImpactAnalysisResult(impact_analysis_id=UUID(analysis.json()["id"]), artifact_type="task", artifact_id=UUID(second_task["id"]), impact_category="indirect", relationship_path=[{"relationship_type": "implements"}, {"relationship_type": "affects"}]))
        db.commit()
    report = client.get(f"/api/v1/projects/{project_id}/reports/change-impact/{change_id}", headers=auth)
    assert report.status_code == 200
    assert len(report.content) > 1500
    other = client.post("/api/v1/projects", headers=auth, json={"name": "Other"}).json()
    assert client.get(f"/api/v1/projects/{other['id']}/reports/change-impact/{change_id}", headers=auth).status_code in {404, 422}


def test_reports_require_project_access(client: TestClient) -> None:
    project_id, _, _ = setup_project(client)
    auth = headers("reports-manager@example.com")
    other = client.post("/api/v1/projects", headers=auth, json={"name": "Private"}).json()
    with SessionLocal() as db:
        member = db.scalar(select(User).where(User.email == "reports-client@example.com")); assert member is not None
        db.execute(project_members.insert().values(project_id=UUID(project_id), user_id=member.id, project_role="client")); db.commit()
    client_headers = headers("reports-client@example.com")
    assert client.get(f"/api/v1/projects/{project_id}/reports/project-summary", headers=client_headers).status_code == 200
    assert client.get(f"/api/v1/projects/{other['id']}/reports/project-summary", headers=client_headers).status_code == 403
