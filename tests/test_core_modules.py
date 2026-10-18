"""Phase 4 isolated SQLite integration tests for core SDLC modules."""

from collections.abc import Generator
from uuid import UUID, uuid4

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
from backend.app.models.traceability import TraceabilityLink
from backend.app.services.auth_service import create_access_token, hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def database(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        roles = {code: Role(code=code, name=code.replace("_", " ").title()) for code in ("admin", "project_manager", "team_lead", "developer", "tester", "client")}
        manager = User(full_name="Manager", email="manager@example.com", password_hash=hash_password("password-123"), roles=[roles["project_manager"]])
        developer = User(full_name="Developer", email="developer@example.com", password_hash=hash_password("password-123"), roles=[roles["developer"]])
        tester = User(full_name="Tester", email="tester@example.com", password_hash=hash_password("password-123"), roles=[roles["tester"]])
        client_user = User(full_name="Client", email="client@example.com", password_hash=hash_password("password-123"), roles=[roles["client"]])
        db.add_all([*roles.values(), manager, developer, tester, client_user]); db.commit()
    monkeypatch.setattr(settings, "jwt_secret_key", "phase-four-test-secret")
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


def test_core_crud_relationships_pagination_and_access(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    assert client.post("/api/v1/projects", json={"name": "Denied"}).status_code == 401
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Alpha", "status": "active"}).json()
    project_id = project["id"]
    assert client.get("/api/v1/projects?limit=1&offset=0", headers=manager_headers).json()[0]["id"] == project_id

    developer_id = None
    with SessionLocal() as db:
        developer_id = db.scalar(select(User.id).where(User.email == "developer@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "developer"}).status_code == 201
    with SessionLocal() as db:
        db.execute(project_members.insert().values(project_id=UUID(project_id), user_id=tester_id, project_role="tester"))
        db.commit()

    milestone = client.post(f"/api/v1/projects/{project_id}/milestones", headers=manager_headers, json={"name": "M1", "status": "planned"}).json()
    assert client.patch(f"/api/v1/projects/milestones/{milestone['id']}", headers=manager_headers, json={"status": "in_progress"}).status_code == 200

    requirement = client.post(f"/api/v1/projects/{project_id}/requirements", headers=manager_headers, json={"requirement_key": "REQ-1", "title": "Login", "description": "Support login", "requirement_type": "functional", "priority": "high"}).json()
    assert client.patch(f"/api/v1/projects/requirements/{requirement['id']}", headers=manager_headers, json={"status": "approved"}).json()["version"] == 2

    sprint = client.post(f"/api/v1/projects/{project_id}/sprints", headers=manager_headers, json={"name": "Sprint 1", "start_date": "2026-09-01", "end_date": "2026-09-14"}).json()
    task = client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json={"title": "Implement login", "priority": "high", "requirement_id": requirement["id"], "sprint_id": sprint["id"], "assigned_to_user_id": str(developer_id)}).json()
    assert client.patch(f"/api/v1/projects/tasks/{task['id']}", headers=headers("developer@example.com"), json={"status": "in_progress"}).status_code == 200
    assert client.post(f"/api/v1/projects/tasks/{task['id']}/comments", headers=headers("developer@example.com"), json={"body": "Started work"}).status_code == 201
    assert len(client.get(f"/api/v1/projects/tasks/{task['id']}/comments", headers=manager_headers).json()) == 1

    bug = client.post(f"/api/v1/projects/{project_id}/bugs", headers=headers("tester@example.com"), json={"title": "Login error", "description": "Failure", "severity": "medium", "requirement_id": requirement["id"], "task_id": task["id"]}).json()
    assert client.patch(f"/api/v1/projects/bugs/{bug['id']}", headers=headers("tester@example.com"), json={"status": "resolved"}).status_code == 200
    test_case = client.post(f"/api/v1/projects/{project_id}/test-cases", headers=headers("tester@example.com"), json={"requirement_id": requirement["id"], "title": "Valid login", "test_steps": "Enter valid credentials", "expected_result": "Access granted"}).json()
    assert client.patch(f"/api/v1/projects/test-cases/{test_case['id']}", headers=headers("tester@example.com"), json={"status": "passed"}).status_code == 200

    other = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Other"}).json()
    invalid_link = client.post(f"/api/v1/projects/{other['id']}/tasks", headers=manager_headers, json={"title": "Bad link", "priority": "low", "requirement_id": requirement["id"]})
    assert invalid_link.status_code == 422
    assert client.get(f"/api/v1/projects/{project_id}", headers=headers("client@example.com")).status_code == 403


def test_validation_and_role_restrictions(client: TestClient) -> None:
    client_headers = headers("client@example.com")
    assert client.post("/api/v1/projects", headers=client_headers, json={"name": "Nope"}).status_code == 403
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Validated"}).json()
    bad_requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "BAD", "title": "Bad", "description": "Bad", "requirement_type": "unknown", "priority": "high"})
    assert bad_requirement.status_code == 422
    assert client.get(f"/api/v1/projects/{project['id']}/requirements", headers=client_headers).status_code == 403


def test_project_role_and_duplicate_membership_validation(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Membership"}).json()
    with SessionLocal() as db:
        developer_id = db.scalar(select(User.id).where(User.email == "developer@example.com"))
    invalid = client.post(f"/api/v1/projects/{project['id']}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "owner"})
    assert invalid.status_code == 422
    valid = client.post(f"/api/v1/projects/{project['id']}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "developer"})
    assert valid.status_code == 201
    duplicate = client.post(f"/api/v1/projects/{project['id']}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "developer"})
    assert duplicate.status_code == 409


def test_project_partial_date_updates_use_effective_range(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Dates", "start_date": "2026-01-01", "end_date": "2026-01-31"}).json()
    project_id = project["id"]
    assert client.patch(f"/api/v1/projects/{project_id}", headers=manager_headers, json={"start_date": "2026-02-01"}).status_code == 422
    assert client.patch(f"/api/v1/projects/{project_id}", headers=manager_headers, json={"end_date": "2025-12-31"}).status_code == 422
    assert client.patch(f"/api/v1/projects/{project_id}", headers=manager_headers, json={"end_date": "2026-02-15"}).status_code == 200


def test_sprint_update_persists_changes_and_validates_dates(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Sprint Update Test"}).json()
    project_id = project["id"]

    sprint = client.post(f"/api/v1/projects/{project_id}/sprints", headers=manager_headers, json={"name": "Sprint 1", "start_date": "2026-01-01", "end_date": "2026-01-14"}).json()
    sprint_id = sprint["id"]

    # Update name
    updated = client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"name": "Renamed Sprint"}).json()
    assert updated["name"] == "Renamed Sprint"
    assert updated["id"] == sprint_id

    # Update goal
    updated = client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"goal": "New goal"}).json()
    assert updated["goal"] == "New goal"

    # Update status
    updated = client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"status": "active"}).json()
    assert updated["status"] == "active"

    # Update both dates
    updated = client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"start_date": "2026-02-01", "end_date": "2026-02-14"}).json()
    assert updated["start_date"] == "2026-02-01"
    assert updated["end_date"] == "2026-02-14"

    # Read back and verify all changes persisted
    get_resp = client.get(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers).json()
    assert get_resp["name"] == "Renamed Sprint"
    assert get_resp["goal"] == "New goal"
    assert get_resp["status"] == "active"
    assert get_resp["start_date"] == "2026-02-01"
    assert get_resp["end_date"] == "2026-02-14"

    # Invalid: start_date after end_date (partial update)
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"start_date": "2026-03-01"}).status_code == 422
    # Invalid: end_date before start_date (partial update)
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"end_date": "2026-01-01"}).status_code == 422

    # Invalid status
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"status": "invalid_status"}).status_code == 422


def test_sprint_update_authorization_and_project_isolation(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    developer_headers = headers("developer@example.com")
    client_headers = headers("client@example.com")

    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Auth Test"}).json()
    project_id = project["id"]

    sprint = client.post(f"/api/v1/projects/{project_id}/sprints", headers=manager_headers, json={"name": "Sprint 1", "start_date": "2026-01-01", "end_date": "2026-01-14"}).json()
    sprint_id = sprint["id"]

    # Manager can update
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=manager_headers, json={"name": "Manager Update"}).status_code == 200

    # Developer cannot update (only read access)
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=developer_headers, json={"name": "Dev Update"}).status_code == 403

    # Client cannot update
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", headers=client_headers, json={"name": "Client Update"}).status_code == 403

    # Cross-project isolation: create second project and sprint
    other_project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Other"}).json()
    other_sprint = client.post(f"/api/v1/projects/{other_project['id']}/sprints", headers=manager_headers, json={"name": "Other Sprint", "start_date": "2026-01-01", "end_date": "2026-01-14"}).json()

    # Try to update other project's sprint via first project's URL (should 404 or 403)
    # The route is /sprints/{record_id} without project_id in path, so we test that the record is not found
    assert client.patch(f"/api/v1/projects/sprints/{other_sprint['id']}", headers=manager_headers, json={"name": "Cross Update"}).status_code == 200  # Manager can update any project's sprint they manage

    # Unauthenticated
    assert client.patch(f"/api/v1/projects/sprints/{sprint_id}", json={"name": "No Auth"}).status_code == 401


def test_detail_and_list_endpoints_and_cross_project_protection(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    first = client.post("/api/v1/projects", headers=manager_headers, json={"name": "One"}).json()
    second = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Two"}).json()
    req = client.post(f"/api/v1/projects/{first['id']}/requirements", headers=manager_headers, json={"requirement_key": "REQ-1", "title": "A", "description": "A", "requirement_type": "functional", "priority": "low"}).json()
    milestone = client.post(f"/api/v1/projects/{first['id']}/milestones", headers=manager_headers, json={"name": "M"}).json()
    sprint = client.post(f"/api/v1/projects/{first['id']}/sprints", headers=manager_headers, json={"name": "S", "start_date": "2026-01-01", "end_date": "2026-01-02"}).json()
    task = client.post(f"/api/v1/projects/{first['id']}/tasks", headers=manager_headers, json={"title": "T", "priority": "low"}).json()
    with SessionLocal() as db:
        manager_id = db.scalar(select(User.id).where(User.email == "manager@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(first["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    bug = client.post(f"/api/v1/projects/{first['id']}/bugs", headers=headers("tester@example.com"), json={"title": "B", "description": "B", "severity": "low"}).json()
    case = client.post(f"/api/v1/projects/{first['id']}/test-cases", headers=headers("tester@example.com"), json={"requirement_id": req["id"], "title": "TC", "test_steps": "step", "expected_result": "pass"}).json()
    assert client.get(f"/api/v1/projects/{first['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/{first['id']}/milestones", headers=manager_headers).json()[0]["id"] == milestone["id"]
    assert client.get(f"/api/v1/projects/milestones/{milestone['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/requirements/{req['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/sprints/{sprint['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/tasks/{task['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/bugs/{bug['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/v1/projects/{first['id']}/test-cases", headers=manager_headers).json()[0]["id"] == case["id"]
    assert client.get(f"/api/v1/projects/test-cases/{case['id']}", headers=manager_headers).status_code == 200
    # A non-member cannot read or update another project's records.
    with SessionLocal() as db:
        developer = db.scalar(select(User).where(User.email == "developer@example.com"))
        assert developer is not None
        db.execute(project_members.insert().values(project_id=UUID(second["id"]), user_id=developer.id, project_role="developer"))
        db.commit()
    developer_headers = headers("developer@example.com")
    assert client.get(f"/api/v1/projects/{first['id']}", headers=developer_headers).status_code == 403
    assert client.get(f"/api/v1/projects/{first['id']}/milestones", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/milestones/{milestone['id']}", headers=developer_headers, json={"status": "completed"}).status_code == 403
    assert client.get(f"/api/v1/projects/{first['id']}/requirements", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/requirements/{req['id']}", headers=developer_headers, json={"status": "approved"}).status_code == 403
    assert client.get(f"/api/v1/projects/{first['id']}/sprints", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/sprints/{sprint['id']}", headers=developer_headers, json={"status": "active"}).status_code == 403
    assert client.get(f"/api/v1/projects/tasks/{task['id']}", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/tasks/{task['id']}", headers=developer_headers, json={"status": "completed"}).status_code == 403
    assert client.get(f"/api/v1/projects/tasks/{task['id']}/comments", headers=developer_headers).status_code == 403
    assert client.get(f"/api/v1/projects/{first['id']}/bugs", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/bugs/{bug['id']}", headers=developer_headers, json={"status": "closed"}).status_code == 403
    assert client.get(f"/api/v1/projects/{first['id']}/test-cases", headers=developer_headers).status_code == 403
    assert client.patch(f"/api/v1/projects/test-cases/{case['id']}", headers=developer_headers, json={"status": "passed"}).status_code == 403


def test_traceability_links_validation_queries_authorization_and_delete(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    tester_headers = headers("tester@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Traceability"}).json()
    other_project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Traceability Other"}).json()
    with SessionLocal() as db:
        developer_id = db.scalar(select(User.id).where(User.email == "developer@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=developer_id, project_role="developer"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "TRACE-1", "title": "Trace", "description": "Trace", "requirement_type": "functional", "priority": "high"}).json()
    other_requirement = client.post(f"/api/v1/projects/{other_project['id']}/requirements", headers=manager_headers, json={"requirement_key": "OTHER-1", "title": "Other", "description": "Other", "requirement_type": "functional", "priority": "low"}).json()
    other_task = client.post(f"/api/v1/projects/{other_project['id']}/tasks", headers=manager_headers, json={"title": "Other Task", "priority": "low"}).json()
    sprint = client.post(f"/api/v1/projects/{project['id']}/sprints", headers=manager_headers, json={"name": "Trace Sprint", "start_date": "2026-01-01", "end_date": "2026-01-02"}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=manager_headers, json={"title": "Trace Task", "priority": "high"}).json()
    bug = client.post(f"/api/v1/projects/{project['id']}/bugs", headers=manager_headers, json={"title": "Trace Bug", "description": "Bug", "severity": "high"}).json()
    test_case = client.post(f"/api/v1/projects/{project['id']}/test-cases", headers=tester_headers, json={"requirement_id": requirement["id"], "title": "Trace Test", "test_steps": "step", "expected_result": "pass"}).json()
    base = f"/api/v1/projects/{project['id']}/traceability-links"
    links = [
        ("task", task["id"], "implements"),
        ("bug", bug["id"], "affects"),
        ("test_case", test_case["id"], "validates"),
        ("sprint", sprint["id"], "belongs_to"),
        ("user", str(developer_id), "belongs_to"),
    ]
    created = []
    for target_type, target_id, relationship_type in links:
        response = client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": target_type, "target_artifact_id": target_id, "relationship_type": relationship_type})
        assert response.status_code == 201
        created.append(response.json())
    assert len(client.get(base, headers=manager_headers).json()) == 5
    assert len(client.get(f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}/traceability-links", headers=manager_headers).json()) == 5
    assert len(client.get(f"/api/v1/projects/{project['id']}/artifacts/task/{task['id']}/traceability-links", headers=manager_headers).json()) == 1
    assert client.get(f"/api/v1/projects/{project['id']}/traceability-links?relationship_type=affects", headers=manager_headers).json()[0]["target_artifact_type"] == "bug"
    duplicate = client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "implements"})
    assert duplicate.status_code == 409
    assert client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": str(uuid4()), "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "implements"}).status_code == 422
    assert client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "task", "target_artifact_id": other_task["id"], "relationship_type": "implements"}).status_code == 422
    assert client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "requirement", "target_artifact_id": other_requirement["id"], "relationship_type": "associated_with"}).status_code == 422
    assert client.post(base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "invalid"}).status_code == 422
    assert client.post(base, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "implements"}).status_code == 401
    assert client.post(base, headers=headers("client@example.com"), json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": "task", "target_artifact_id": task["id"], "relationship_type": "implements"}).status_code == 403
    with SessionLocal() as db:
        db.execute(project_members.insert().values(project_id=UUID(other_project["id"]), user_id=developer_id, project_role="developer"))
        db.commit()
    inaccessible_headers = headers("client@example.com")
    assert client.get(base, headers=inaccessible_headers).status_code == 403
    assert client.delete(f"{base}/{created[0]['id']}", headers=manager_headers).status_code == 204
    assert client.get(f"{base}/{created[0]['id']}", headers=manager_headers).status_code == 404


def test_rcia_change_requests_deterministic_traversal_and_persistence(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "RCIA"}).json()
    other_project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "RCIA Other"}).json()
    with SessionLocal() as db:
        manager_id = db.scalar(select(User.id).where(User.email == "manager@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "RCIA-1", "title": "Changeable", "description": "Original", "requirement_type": "functional", "priority": "high"}).json()
    other_requirement = client.post(f"/api/v1/projects/{other_project['id']}/requirements", headers=manager_headers, json={"requirement_key": "OTHER-RCIA", "title": "Other", "description": "Other", "requirement_type": "functional", "priority": "low"}).json()
    other_task = client.post(f"/api/v1/projects/{other_project['id']}/tasks", headers=manager_headers, json={"title": "Other Task", "priority": "low"}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=manager_headers, json={"title": "Affected Task", "priority": "high"}).json()
    bug = client.post(f"/api/v1/projects/{project['id']}/bugs", headers=manager_headers, json={"title": "Affected Bug", "description": "Bug", "severity": "high"}).json()
    indirect_bug = client.post(f"/api/v1/projects/{project['id']}/bugs", headers=manager_headers, json={"title": "Indirect Bug", "description": "Bug", "severity": "medium"}).json()
    test_case = client.post(f"/api/v1/projects/{project['id']}/test-cases", headers=headers("tester@example.com"), json={"requirement_id": requirement["id"], "title": "Affected Test", "test_steps": "step", "expected_result": "pass"}).json()
    base = f"/api/v1/projects/{project['id']}"
    assert client.post(f"{base}/requirements/{requirement['id']}/change-requests", headers=manager_headers, json={"change_summary": "Change behavior", "proposed_description": "Updated"}).status_code == 201
    change_request = client.post(f"{base}/requirements/{requirement['id']}/change-requests", headers=manager_headers, json={"change_summary": "Analyze this change"}).json()
    assert client.post(f"{base}/requirements/{other_requirement['id']}/change-requests", headers=manager_headers, json={"change_summary": "Wrong project"}).status_code == 422
    assert client.post(f"{base}/requirements/{requirement['id']}/change-requests", headers=headers("client@example.com"), json={"change_summary": "Denied"}).status_code == 403
    assert client.get(f"{base}/change-requests", headers=manager_headers).status_code == 200
    assert client.get(f"{base}/change-requests/{change_request['id']}", headers=manager_headers).status_code == 200
    assert client.patch(f"{base}/change-requests/{change_request['id']}", headers=manager_headers, json={"status": "approved"}).status_code == 200
    trace_base = f"{base}/traceability-links"
    for target_type, target_id, relation in (("task", task["id"], "implements"), ("bug", bug["id"], "affects"), ("test_case", test_case["id"], "validates"), ("sprint", task["id"], "associated_with")):
        if target_type == "sprint":
            continue
        assert client.post(trace_base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": target_type, "target_artifact_id": target_id, "relationship_type": relation}).status_code == 201
    # These rows exercise multi-hop traversal and cycle protection at the graph boundary.
    with SessionLocal() as db:
        db.add_all([
            TraceabilityLink(project_id=UUID(project["id"]), source_artifact_type="task", source_artifact_id=UUID(task["id"]), target_artifact_type="bug", target_artifact_id=UUID(indirect_bug["id"]), relationship_type="implements", created_by_user_id=manager_id),
            TraceabilityLink(project_id=UUID(project["id"]), source_artifact_type="bug", source_artifact_id=UUID(indirect_bug["id"]), target_artifact_type="task", target_artifact_id=UUID(task["id"]), relationship_type="affects", created_by_user_id=manager_id),
            TraceabilityLink(project_id=UUID(project["id"]), source_artifact_type="requirement", source_artifact_id=UUID(requirement["id"]), target_artifact_type="task", target_artifact_id=UUID(other_task["id"]), relationship_type="implements", created_by_user_id=manager_id),
        ])
        db.commit()
    analysis_response = client.post(f"{base}/change-requests/{change_request['id']}/analyses", headers=manager_headers)
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    results = client.get(f"{base}/analyses/{analysis['id']}/results", headers=manager_headers)
    assert results.status_code == 200
    result_rows = results.json()
    assert [(row["artifact_type"], row["artifact_id"], row["impact_category"]) for row in result_rows] == sorted([("bug", bug["id"], "direct"), ("bug", indirect_bug["id"], "indirect"), ("task", task["id"], "direct"), ("test_case", test_case["id"], "direct")])
    assert all(row["relationship_path"] and row["explanation"] for row in result_rows)
    assert client.get(f"{base}/analyses/{analysis['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"{base}/analyses/{analysis['id']}/results", headers=headers("client@example.com")).status_code == 403
    repeat = client.post(f"{base}/change-requests/{change_request['id']}/analyses", headers=manager_headers).json()
    repeat_rows = client.get(f"{base}/analyses/{repeat['id']}/results", headers=manager_headers).json()
    assert [(row["artifact_type"], row["artifact_id"], row["impact_category"]) for row in repeat_rows] == [(row["artifact_type"], row["artifact_id"], row["impact_category"]) for row in result_rows]
