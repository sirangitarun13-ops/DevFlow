"""Phase 3 authentication unit and isolated integration tests."""

from collections.abc import Generator

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
from backend.app.services.auth_service import hash_password, verify_password

TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    Base.metadata.create_all(test_engine)
    with TestingSessionLocal() as session:
        for code, name in (
            ("admin", "Administrator"),
            ("client", "Client"),
            ("developer", "Developer"),
        ):
            session.add(Role(code=code, name=name))
        session.commit()
    monkeypatch.setattr(settings, "jwt_secret_key", "unit-test-secret-not-for-production")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 15)
    # Disable rate limiting for tests
    monkeypatch.setattr(settings, "rate_limit_login", "1000/minute")
    monkeypatch.setattr(settings, "rate_limit_register", "1000/minute")
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_payload() -> dict[str, str]:
    return {
        "full_name": "Client User",
        "email": "client@example.com",
        "password": "strong-password-123",
    }


def test_password_hashing_and_verification() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert password_hash.startswith("$argon2")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_successful_registration_and_login(client: TestClient) -> None:
    registration = client.post("/api/v1/auth/register", json=register_payload())
    assert registration.status_code == 201
    assert "password_hash" not in registration.json()
    assert registration.json()["roles"][0]["code"] == "client"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "CLIENT@example.com", "password": "strong-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]
    assert "password_hash" not in login.json()["user"]


def test_invalid_credentials_are_rejected(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_authenticated_user_endpoint_and_missing_token(client: TestClient) -> None:
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401

    client.post("/api/v1/auth/register", json=register_payload())
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "strong-password-123"},
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "client@example.com"


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_role_authorization(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "strong-password-123"},
    )
    token = login.json()["access_token"]

    forbidden = client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden.status_code == 403

    with TestingSessionLocal() as session:
        user = session.scalar(select(User).where(User.email == "client@example.com"))
        admin = session.scalar(select(Role).where(Role.code == "admin"))
        assert user is not None and admin is not None
        user.roles.append(admin)
        session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "strong-password-123"},
    )
    allowed = client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert allowed.status_code == 200


def test_token_creation_and_validation_with_valid_secret(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "strong-password-123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "client@example.com"
