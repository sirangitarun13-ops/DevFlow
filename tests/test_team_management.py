"""Project Manager team and developer management integration tests."""

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
from backend.app.services.auth_service import create_access_token, hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def database(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        roles = {code: Role(code=code, name=code.replace("_", " ").title()) for code in ("project_manager", "team_lead", "developer", "client")}
        manager = User(full_name="Project Manager", email="team-manager@example.com", password_hash=hash_password("password-123"), roles=[roles["project_manager"]])
        lead = User(full_name="Team Lead", email="team-lead@example.com", password_hash=hash_password("password-123"), roles=[roles["team_lead"]])
        developer = User(full_name="Ada Developer", email="ada@example.com", password_hash=hash_password("password-123"), roles=[roles["developer"]])
        client = User(full_name="Client Viewer", email="team-client@example.com", password_hash=hash_password("password-123"), roles=[roles["client"]])
        db.add_all([*roles.values(), manager, lead, developer, client]); db.commit()
    monkeypatch.setattr(settings, "jwt_secret_key", "team-management-test-secret")
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


def auth(email: str) -> dict[str, str]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_manager_can_build_and_manage_a_project_team(client: TestClient) -> None:
    manager_headers = auth("team-manager@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Team project"}).json()
    project_id = project["id"]
    assert client.delete(f"/api/v1/projects/{project_id}/members/{project['created_by_user_id']}", headers=manager_headers).status_code == 409
    with SessionLocal() as db:
        developer_id = db.scalar(select(User.id).where(User.email == "ada@example.com"))
        assert developer_id is not None

    directory = client.get(f"/api/v1/users/developers?project_id={project_id}", headers=manager_headers)
    assert directory.status_code == 200
    assert any(item["email"] == "ada@example.com" for item in directory.json())

    added = client.post(f"/api/v1/projects/{project_id}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "developer"})
    assert added.status_code == 201
    assert added.json()["full_name"] == "Ada Developer"
    assert added.json()["roles"][0]["code"] == "developer"
    assert added.json()["assigned_task_count"] == 0
    assert added.json()["completion_percent"] == 0
    duplicate = client.post(f"/api/v1/projects/{project_id}/members", headers=manager_headers, json={"user_id": str(developer_id), "project_role": "developer"})
    assert duplicate.status_code == 409

    task_payload = {"title": "Completed task", "priority": "high", "assigned_to_user_id": str(developer_id), "due_date": "2026-10-10"}
    completed = client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json=task_payload).json()
    assert client.patch(f"/api/v1/projects/tasks/{completed['id']}", headers=manager_headers, json={"status": "completed"}).status_code == 200
    client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json={**task_payload, "title": "In progress task", "status": "in_progress"})
    client.post(f"/api/v1/projects/{project_id}/tasks", headers=manager_headers, json={**task_payload, "title": "Todo task", "status": "todo"})
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=manager_headers).json()
    developer_member = next(item for item in members if item["user_id"] == str(developer_id))
    assert (developer_member["assigned_task_count"], developer_member["completed_task_count"], developer_member["in_progress_task_count"], developer_member["pending_task_count"], developer_member["completion_percent"]) == (3, 1, 1, 1, 33.33)
    developer_tasks = client.get(f"/api/v1/projects/{project_id}/members/{developer_id}/tasks", headers=manager_headers)
    assert developer_tasks.status_code == 200
    assert len(developer_tasks.json()) == 3
    assert developer_tasks.json()[0]["due_date"] == "2026-10-10"

    remaining_directory = client.get(f"/api/v1/users/developers?project_id={project_id}", headers=manager_headers).json()
    assert all(item["email"] != "ada@example.com" for item in remaining_directory)

    removed = client.delete(f"/api/v1/projects/{project_id}/members/{developer_id}", headers=manager_headers)
    assert removed.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}/members", headers=manager_headers).json()


def test_team_management_is_project_scoped_and_role_protected(client: TestClient) -> None:
    manager_headers = auth("team-manager@example.com")
    client_headers = auth("team-client@example.com")
    developer_headers = auth("ada@example.com")
    project = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Restricted team"}).json()
    project_id = UUID(project["id"])
    with SessionLocal() as db:
        client_id = db.scalar(select(User.id).where(User.email == "team-client@example.com"))
        assert client_id is not None

    lead_headers = auth("team-lead@example.com")
    with SessionLocal() as db:
        developer_id = db.scalar(select(User.id).where(User.email == "ada@example.com"))
        client_id = db.scalar(select(User.id).where(User.email == "team-client@example.com"))
        assert developer_id is not None and client_id is not None
        db.execute(project_members.insert().values(project_id=project_id, user_id=developer_id, project_role="developer"))
        db.commit()

    assert client.get(f"/api/v1/users/developers?project_id={project_id}", headers=client_headers).status_code == 403
    assert client.get(f"/api/v1/users/developers?project_id={project_id}", headers=lead_headers).status_code == 403
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=client_headers, json={"user_id": str(client_id), "project_role": "client"}).status_code == 403
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=manager_headers, json={"user_id": str(client_id), "project_role": "developer"}).status_code == 422
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=lead_headers, json={"user_id": str(developer_id), "project_role": "developer"}).status_code == 403
    assert client.delete(f"/api/v1/projects/{project_id}/members/{developer_id}", headers=lead_headers).status_code == 403
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=developer_headers, json={"user_id": str(developer_id), "project_role": "developer"}).status_code == 403
    assert client.delete(f"/api/v1/projects/{project_id}/members/{developer_id}", headers=developer_headers).status_code == 403
    assert client.delete(f"/api/v1/projects/{project_id}/members/{client_id}", headers=client_headers).status_code == 403

    other = client.post("/api/v1/projects", headers=manager_headers, json={"name": "Other team"}).json()
    assert client.delete(f"/api/v1/projects/{other['id']}/members/{developer_id}", headers=manager_headers).status_code == 404
