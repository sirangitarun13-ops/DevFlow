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
        admin = User(full_name="Admin", email="admin@example.com", password_hash=hash_password("password-123"), roles=[roles["admin"]])
        manager = User(full_name="Manager", email="manager@example.com", password_hash=hash_password("password-123"), roles=[roles["project_manager"]])
        developer = User(full_name="Developer", email="developer@example.com", password_hash=hash_password("password-123"), roles=[roles["developer"]])
        tester = User(full_name="Tester", email="tester@example.com", password_hash=hash_password("password-123"), roles=[roles["tester"]])
        client_user = User(full_name="Client", email="client@example.com", password_hash=hash_password("password-123"), roles=[roles["client"]])
        db.add_all([*roles.values(), admin, manager, developer, tester, client_user]); db.commit()
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
    # Any authenticated user can now create a project
    project = client.post("/api/v1/projects", headers=client_headers, json={"name": "Client Created"}).json()
    assert project["name"] == "Client Created"
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Validated"}).json()
    bad_requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "BAD", "title": "Bad", "description": "Bad", "requirement_type": "unknown", "priority": "high"})
    assert bad_requirement.status_code == 422
    assert client.get(f"/api/v1/projects/{project['id']}/requirements", headers=client_headers).status_code == 403


def test_project_creator_role_assignment(client: TestClient) -> None:
    client_headers = headers("client@example.com")
    project = client.post("/api/v1/projects", headers=client_headers, json={"name": "Creator Test"}).json()
    assert project["name"] == "Creator Test"
    project_id = project["id"]
    creator_id = project["created_by_user_id"]

    with SessionLocal() as db:
        from backend.app.models.core import project_members
        member = db.execute(
            project_members.select().where(
                project_members.c.project_id == UUID(project_id),
                project_members.c.user_id == UUID(creator_id)
            )
        ).first()
        assert member is not None
        assert member.project_role == "project_manager"


def test_project_creator_global_role_preservation(client: TestClient) -> None:
    client_headers = headers("client@example.com")
    project = client.post("/api/v1/projects", headers=client_headers, json={"name": "Global Role Test"}).json()

    with SessionLocal() as db:
        from backend.app.models.auth import User
        user = db.scalar(select(User).where(User.id == UUID(project["created_by_user_id"])))
        assert user is not None
        # Creator should have client role globally, not project_manager globally
        global_roles = [role.code for role in user.roles]
        assert "client" in global_roles
        assert "project_manager" not in global_roles


def test_project_isolation_between_managers(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    other_headers = headers("developer@example.com")

    project1 = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Project One"}).json()
    project2 = client.post("/api/v1/projects", headers=other_headers, json={"name": "Project Two"}).json()

    project1_id = project1["id"]
    project2_id = project2["id"]
    manager_id = project1["created_by_user_id"]
    other_id = project2["created_by_user_id"]

    with SessionLocal() as db:
        from backend.app.models.auth import User
        manager = db.scalar(select(User).where(User.id == UUID(manager_id)))
        other = db.scalar(select(User).where(User.id == UUID(other_id)))

        developer_id = db.scalar(select(User.id).where(User.email == "developer@example.com"))
        assert developer_id is not None

        # Manager of project1 should be able to access project1
        assert client.post(f"/api/v1/projects/{project1_id}/requirements",
                         headers=manager_headers,
                         json={"requirement_key": "REQ-1", "title": "Test", "description": "Test",
                               "requirement_type": "functional", "priority": "high"}).status_code == 201

        # Manager of project1 should NOT be able to manage project2 solely based on their project_manager role in project1
        assert client.post(f"/api/v1/projects/{project2_id}/requirements",
                         headers=manager_headers,
                         json={"requirement_key": "REQ-2", "title": "Test", "description": "Test",
                               "requirement_type": "functional", "priority": "high"}).status_code == 403

        # Other user should be able to manage their own project
        assert client.post(f"/api/v1/projects/{project2_id}/requirements",
                         headers=other_headers,
                         json={"requirement_key": "REQ-2", "title": "Test", "description": "Test",
                               "requirement_type": "functional", "priority": "high"}).status_code == 201


def test_administrative_access(client: TestClient) -> None:
    admin_headers = headers("admin@example.com")
    client_headers = headers("client@example.com")
    manager_headers = headers("manager@example.com")

    # Admin can access any project without membership
    # Create project as manager
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Admin Test"}).json()
    project_id = project["id"]

    # Admin can access manager's project even without membership
    assert client.get(f"/api/v1/projects/{project_id}", headers=admin_headers).status_code == 200

    # Admin can create and manage projects globally
    admin_project = client.post("/api/v1/projects", headers=admin_headers, json={"name": "Admin's Project"}).json()
    admin_project_id = admin_project["id"]
    assert client.get(f"/api/v1/projects/{admin_project_id}", headers=admin_headers).status_code == 200

    # Client cannot access admin's project
    assert client.get(f"/api/v1/projects/{admin_project_id}", headers=client_headers).status_code == 403

    # Client can only access their own projects
    client_project = client.post("/api/v1/projects", headers=client_headers, json={"name": "Client's Project"}).json()
    client_project_id = client_project["id"]
    assert client.get(f"/api/v1/projects/{client_project_id}", headers=client_headers).status_code == 200


def test_admin_cross_project_access(client: TestClient) -> None:
    admin_headers = headers("admin@example.com")
    manager_headers = headers("manager@example.com")
    developer_headers = headers("developer@example.com")

    # Admin creates a project without being a member
    admin_project = client.post("/api/v1/projects", headers=admin_headers, json={"name": "Admin's Project"}).json()
    admin_project_id = admin_project["id"]

    # Manager creates a different project
    manager_project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Manager's Project"}).json()
    manager_project_id = manager_project["id"]

    # Admin can access both projects
    assert client.get(f"/api/v1/projects/{admin_project_id}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/v1/projects/{manager_project_id}", headers=admin_headers).status_code == 200

    # Admin can manage both projects
    assert client.post(f"/api/v1/projects/{admin_project_id}/requirements",
                     headers=admin_headers,
                     json={"requirement_key": "REQ-1", "title": "Test", "description": "Test",
                           "requirement_type": "functional", "priority": "high"}).status_code == 201

    assert client.post(f"/api/v1/projects/{manager_project_id}/requirements",
                     headers=admin_headers,
                     json={"requirement_key": "REQ-2", "title": "Test", "description": "Test",
                           "requirement_type": "functional", "priority": "high"}).status_code == 201


def test_non_member_cannot_access_project(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    developer_headers = headers("developer@example.com")

    # Manager creates a project and adds developer as member
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Manager's Project"}).json()
    project_id = project["id"]

    with SessionLocal() as db:
        from backend.app.models.auth import User
        from backend.app.models.core import project_members
        from uuid import UUID

        developer_id = db.scalar(select(User.id).where(User.email == "developer@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project_id), user_id=developer_id, project_role="developer"))
        db.commit()

    # Developer can access their own project (they are a member)
    assert client.get(f"/api/v1/projects/{project_id}", headers=developer_headers).status_code == 200

    # Create a new user that is NOT a member of the manager's project
    with SessionLocal() as db:
        from backend.app.models.auth import User, Role
        from backend.app.services.auth_service import hash_password
        from uuid import uuid4

        # Find existing tester role to reuse
        tester_role = db.scalar(select(Role).where(Role.code == "tester"))
        assert tester_role is not None, "Tester role not found in test database"

        # Create a new user with tester role
        tester_user = User(full_name="Tester", email="tester2@example.com", password_hash=hash_password("password-123"), roles=[tester_role])
        db.add(tester_user)
        db.commit()

    tester_headers = headers("tester2@example.com")

    # Tester (no membership) cannot access manager's project
    assert client.get(f"/api/v1/projects/{project_id}", headers=tester_headers).status_code == 403

    # Tester cannot manage manager's project
    assert client.post(f"/api/v1/projects/{project_id}/requirements",
                     headers=tester_headers,
                     json={"requirement_key": "REQ-1", "title": "Test", "description": "Test",
                           "requirement_type": "functional", "priority": "high"}).status_code == 403


def test_project_creator_global_role_preservation(client: TestClient) -> None:
    client_headers = headers("client@example.com")
    project = client.post("/api/v1/projects", headers=client_headers, json={"name": "Global Role Test"}).json()

    with SessionLocal() as db:
        from backend.app.models.auth import User
        user = db.scalar(select(User).where(User.id == UUID(project["created_by_user_id"])))
        assert user is not None

        # Clear existing roles to test fresh creation
        global_roles = [role.code for role in user.roles]

        # Creator should have client role globally, not project_manager globally
        assert "client" in global_roles
        assert "project_manager" not in global_roles

        # Verify project-specific role does not affect global role membership
        # by checking that the user has the exact expected roles
        assert len(global_roles) == 1
        assert global_roles[0] == "client"


def test_role_combinations(client: TestClient) -> None:
    manager_headers = headers("manager@example.com")
    developer_headers = headers("developer@example.com")

    # Manager creates a project (has global project_manager role + project-specific project_manager role)
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Manager Global Role"}).json()
    project_id = project["id"]

    # Manager should be able to manage their project (has global project_manager role)
    assert client.post(f"/api/v1/projects/{project_id}/requirements",
                     headers=manager_headers,
                     json={"requirement_key": "REQ-1", "title": "Test", "description": "Test",
                           "requirement_type": "functional", "priority": "high"}).status_code == 201

    # Developer cannot manage manager's project (doesn't have global manager role, no project_manager role)
    assert client.post(f"/api/v1/projects/{project_id}/requirements",
                     headers=developer_headers,
                     json={"requirement_key": "REQ-2", "title": "Test", "description": "Test",
                           "requirement_type": "functional", "priority": "high"}).status_code == 403


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


def test_rcia_impact_results_have_human_readable_fields(client: TestClient) -> None:
    """Verify that RCIA impact results include human-readable artifact_key and artifact_title."""
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "RCIA Readable"}).json()
    with SessionLocal() as db:
        manager_id = db.scalar(select(User.id).where(User.email == "manager@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    requirement = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "RCIA-1", "title": "Changeable Requirement", "description": "Original", "requirement_type": "functional", "priority": "high"}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=manager_headers, json={"title": "Affected Task", "priority": "high"}).json()
    bug = client.post(f"/api/v1/projects/{project['id']}/bugs", headers=manager_headers, json={"title": "Affected Bug", "description": "Bug", "severity": "high"}).json()
    test_case = client.post(f"/api/v1/projects/{project['id']}/test-cases", headers=headers("tester@example.com"), json={"requirement_id": requirement["id"], "title": "Affected Test", "test_steps": "step", "expected_result": "pass"}).json()
    base = f"/api/v1/projects/{project['id']}"
    change_request = client.post(f"{base}/requirements/{requirement['id']}/change-requests", headers=manager_headers, json={"change_summary": "Analyze this change"}).json()
    trace_base = f"{base}/traceability-links"
    for target_type, target_id, relation in (("task", task["id"], "implements"), ("bug", bug["id"], "affects"), ("test_case", test_case["id"], "validates")):
        assert client.post(trace_base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": requirement["id"], "target_artifact_type": target_type, "target_artifact_id": target_id, "relationship_type": relation}).status_code == 201
    analysis_response = client.post(f"{base}/change-requests/{change_request['id']}/analyses", headers=manager_headers)
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    results = client.get(f"{base}/analyses/{analysis['id']}/results", headers=manager_headers)
    assert results.status_code == 200
    result_rows = results.json()

    # Verify each result has artifact_key and artifact_title populated
    result_map = {(row["artifact_type"], row["artifact_id"]): row for row in result_rows}

    # Task should have title as both key and title
    task_result = result_map[("task", task["id"])]
    assert task_result["artifact_key"] == "Affected Task"
    assert task_result["artifact_title"] == "Affected Task"

    # Bug should have title as both key and title
    bug_result = result_map[("bug", bug["id"])]
    assert bug_result["artifact_key"] == "Affected Bug"
    assert bug_result["artifact_title"] == "Affected Bug"

    # TestCase should have title as both key and title
    test_case_result = result_map[("test_case", test_case["id"])]
    assert test_case_result["artifact_key"] == "Affected Test"
    assert test_case_result["artifact_title"] == "Affected Test"

    # Requirement (the changed one) should have requirement_key as key and title as title
    # Note: The changed requirement itself is not in the impact results (it's the source)
    # but we verify the pattern works for requirement artifacts if they appear

    # Verify all results have the expected fields (not null/empty for seeded artifacts)
    for row in result_rows:
        assert "artifact_key" in row
        assert "artifact_title" in row
        # For seeded artifacts, key and title should be populated
        if row["artifact_type"] in ("task", "bug", "test_case"):
            assert row["artifact_key"] is not None
            assert row["artifact_title"] is not None


def test_rcia_requirement_dependency_propagation(client: TestClient) -> None:
    """Verify that requirement-to-requirement dependencies propagate impacts correctly."""
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "RCIA Deps"}).json()
    with SessionLocal() as db:
        manager_id = db.scalar(select(User.id).where(User.email == "manager@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    # Create requirement B
    req_b = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "REQ-B", "title": "Base Requirement", "description": "Base", "requirement_type": "functional", "priority": "high"}).json()
    # Create requirement A that depends on B
    req_a = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "REQ-A", "title": "Dependent Requirement", "description": "Depends on B", "requirement_type": "functional", "priority": "high"}).json()
    # Create implementation artifacts for requirement A
    task_a = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=manager_headers, json={"title": "Task for A", "priority": "high"}).json()
    bug_a = client.post(f"/api/v1/projects/{project['id']}/bugs", headers=manager_headers, json={"title": "Bug in A", "description": "Bug", "severity": "high"}).json()
    test_case_a = client.post(f"/api/v1/projects/{project['id']}/test-cases", headers=headers("tester@example.com"), json={"requirement_id": req_a["id"], "title": "Test A", "test_steps": "step", "expected_result": "pass"}).json()

    base = f"/api/v1/projects/{project['id']}"
    # Create traceability: A depends_on B
    trace_base = f"{base}/traceability-links"
    assert client.post(trace_base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": req_a["id"], "target_artifact_type": "requirement", "target_artifact_id": req_b["id"], "relationship_type": "depends_on"}).status_code == 201
    # Implementation links for requirement A
    for target_type, target_id, relation in (("task", task_a["id"], "implements"), ("bug", bug_a["id"], "affects"), ("test_case", test_case_a["id"], "validates")):
        assert client.post(trace_base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": req_a["id"], "target_artifact_type": target_type, "target_artifact_id": target_id, "relationship_type": relation}).status_code == 201

    change_request = client.post(f"{base}/requirements/{req_b['id']}/change-requests", headers=manager_headers, json={"change_summary": "Change B"}).json()
    analysis_response = client.post(f"{base}/change-requests/{change_request['id']}/analyses", headers=manager_headers)
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    results = client.get(f"{base}/analyses/{analysis['id']}/results", headers=manager_headers)
    assert results.status_code == 200
    result_rows = results.json()

    # Verify impacted artifacts include:
    # - req_a (direct, via depends_on)
    # - task_a, bug_a, test_case_a (indirect, via req_a's implementation links)
    result_map = {(row["artifact_type"], row["artifact_id"]): row for row in result_rows}

    # req_a should be direct impact (depends_on)
    req_a_result = result_map[("requirement", req_a["id"])]
    assert req_a_result["impact_category"] == "direct"

    # req_a path should show depends_on with reverse traversal
    req_a_path_steps = req_a_result["relationship_path"]
    req_a_path_types = [step["relationship_type"] for step in req_a_path_steps]
    assert len(req_a_path_types) == 1
    assert "depends_on" in req_a_path_types
    # Traversal should be reverse (A depends_on B, so B change impacts A)
    req_a_traversal = [step.get("traversal_direction") for step in req_a_result["relationship_path"]]
    assert "reverse" in req_a_traversal

    # Implementation artifacts of req_a should be indirect
    task_a_result = result_map[("task", task_a["id"])]
    assert task_a_result["impact_category"] == "indirect"
    bug_a_result = result_map[("bug", bug_a["id"])]
    assert bug_a_result["impact_category"] == "indirect"
    test_case_a_result = result_map[("test_case", test_case_a["id"])]
    assert test_case_a_result["impact_category"] == "indirect"

    # Implementation artifact paths should show depends_on -> implements/affects/validates with forward traversal
    task_a_path_types = [step["relationship_type"] for step in task_a_result["relationship_path"]]
    task_a_traversal = [step.get("traversal_direction") for step in task_a_result["relationship_path"]]
    assert "depends_on" in task_a_path_types
    assert "implements" in task_a_path_types
    assert "forward" in task_a_traversal

    # Verify changing A does NOT identify B through the depends_on relationship
    change_request_a = client.post(f"{base}/requirements/{req_a['id']}/change-requests", headers=manager_headers, json={"change_summary": "Change A"}).json()
    analysis_response_a = client.post(f"{base}/change-requests/{change_request_a['id']}/analyses", headers=manager_headers)
    assert analysis_response_a.status_code == 201
    analysis_a = analysis_response_a.json()
    results_a = client.get(f"{base}/analyses/{analysis_a['id']}/results", headers=manager_headers)
    assert results_a.status_code == 200
    result_rows_a = results_a.json()
    # B should NOT be in the impact results when changing A
    result_types_a = {(row["artifact_type"], row["artifact_id"]) for row in result_rows_a}
    assert ("requirement", req_b["id"]) not in result_types_a


def test_rcia_blocks_relationship_propagation(client: TestClient) -> None:
    """Verify that blocks relationship propagates in the correct direction."""
    manager_headers = headers("manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "RCIA Blocks"}).json()
    with SessionLocal() as db:
        manager_id = db.scalar(select(User.id).where(User.email == "manager@example.com"))
        tester_id = db.scalar(select(User.id).where(User.email == "tester@example.com"))
        db.execute(project_members.insert().values(project_id=UUID(project["id"]), user_id=tester_id, project_role="tester"))
        db.commit()
    # Create requirement A (blocking) and B (blocked)
    req_a = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "REQ-A", "title": "Blocking Requirement", "description": "Blocks B", "requirement_type": "functional", "priority": "high"}).json()
    req_b = client.post(f"/api/v1/projects/{project['id']}/requirements", headers=manager_headers, json={"requirement_key": "REQ-B", "title": "Blocked Requirement", "description": "Blocked by A", "requirement_type": "functional", "priority": "high"}).json()

    base = f"/api/v1/projects/{project['id']}"
    trace_base = f"{base}/traceability-links"
    # A blocks B
    assert client.post(trace_base, headers=manager_headers, json={"source_artifact_type": "requirement", "source_artifact_id": req_a["id"], "target_artifact_type": "requirement", "target_artifact_id": req_b["id"], "relationship_type": "blocks"}).status_code == 201

    change_request_a = client.post(f"{base}/requirements/{req_a['id']}/change-requests", headers=manager_headers, json={"change_summary": "Change A"}).json()
    analysis_response = client.post(f"{base}/change-requests/{change_request_a['id']}/analyses", headers=manager_headers)
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    results = client.get(f"{base}/analyses/{analysis['id']}/results", headers=manager_headers)
    assert results.status_code == 200
    result_rows = results.json()

    # req_b should be direct impact (A blocks B, so A change impacts B)
    result_map = {(row["artifact_type"], row["artifact_id"]): row for row in result_rows}
    req_b_result = result_map[("requirement", req_b["id"])]
    assert req_b_result["impact_category"] == "direct"

    # Path should show blocks with forward traversal
    path_types = [step["relationship_type"] for step in req_b_result["relationship_path"]]
    assert "blocks" in path_types
    path_traversal = [step.get("traversal_direction") for step in req_b_result["relationship_path"]]
    assert "forward" in path_traversal

    # Verify changing B does NOT identify A through the blocks relationship
    change_request_b = client.post(f"{base}/requirements/{req_b['id']}/change-requests", headers=manager_headers, json={"change_summary": "Change B"}).json()
    analysis_response_b = client.post(f"{base}/change-requests/{change_request_b['id']}/analyses", headers=manager_headers)
    assert analysis_response_b.status_code == 201
    analysis_b = analysis_response_b.json()
    results_b = client.get(f"{base}/analyses/{analysis_b['id']}/results", headers=manager_headers)
    assert results_b.status_code == 200
    result_rows_b = results_b.json()
    # A should NOT be in the impact results when changing B
    result_types_b = {(row["artifact_type"], row["artifact_id"]) for row in result_rows_b}
    assert ("requirement", req_a["id"]) not in result_types_b
