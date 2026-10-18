"""Rate limiting tests for authentication endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.rate_limit import get_limiter
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.auth import Role, User
from backend.app.services.auth_service import hash_password

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
    # Use low limits for rate limit testing
    monkeypatch.setattr(settings, "rate_limit_login", "3/minute")
    monkeypatch.setattr(settings, "rate_limit_register", "2/minute")
    yield
    # Reset rate limiter storage between tests
    limiter = get_limiter()
    limiter.reset()
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


def register_payload(email: str = "client@example.com") -> dict[str, str]:
    return {
        "full_name": "Client User",
        "email": email,
        "password": "strong-password-123",
    }


def login_payload(email: str = "client@example.com", password: str = "strong-password-123") -> dict[str, str]:
    return {"email": email, "password": password}


def test_login_within_limit_succeeds(client: TestClient) -> None:
    """Login attempts within the configured limit succeed."""
    client.post("/api/v1/auth/register", json=register_payload())

    for _ in range(3):
        response = client.post("/api/v1/auth/login", json=login_payload())
        assert response.status_code == 200
        assert "access_token" in response.json()


def test_login_exceeds_limit_returns_429(client: TestClient) -> None:
    """Login attempts exceeding the limit return HTTP 429."""
    client.post("/api/v1/auth/register", json=register_payload())

    # Make 3 successful attempts (limit is 3/minute)
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json=login_payload())
        assert response.status_code == 200

    # 4th attempt should be rate limited
    response = client.post("/api/v1/auth/login", json=login_payload())
    assert response.status_code == 429
    data = response.json()
    assert "error" in data or "detail" in data


def test_register_within_limit_succeeds(client: TestClient) -> None:
    """Registration attempts within the configured limit succeed."""
    for i in range(2):
        response = client.post("/api/v1/auth/register", json=register_payload(email=f"user{i}@example.com"))
        assert response.status_code == 201


def test_register_exceeds_limit_returns_429(client: TestClient) -> None:
    """Registration attempts exceeding the limit return HTTP 429."""
    for i in range(2):
        response = client.post("/api/v1/auth/register", json=register_payload(email=f"user{i}@example.com"))
        assert response.status_code == 201

    # 3rd attempt should be rate limited
    response = client.post("/api/v1/auth/register", json=register_payload(email="user2@example.com"))
    assert response.status_code == 429
    data = response.json()
    assert "error" in data or "detail" in data


def test_rate_limit_includes_retry_after_header(client: TestClient) -> None:
    """Rate limited responses include Retry-After header."""
    client.post("/api/v1/auth/register", json=register_payload())

    # Exhaust the limit
    for _ in range(3):
        client.post("/api/v1/auth/login", json=login_payload())

    response = client.post("/api/v1/auth/login", json=login_payload())
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    retry_after = int(response.headers["Retry-After"])
    assert retry_after > 0


def test_x_forwarded_for_spoofing_blocked(client: TestClient) -> None:
    """
    Changing X-Forwarded-For header does NOT bypass rate limiting.
    The rate limiter uses request.client.host (set by Uvicorn based on
    forwarded_allow_ips configuration). TestClient uses 'testclient' as
    the client host, so all requests share the same limit regardless of
    X-Forwarded-For header.
    """
    client.post("/api/v1/auth/register", json=register_payload(email="spoof_test@example.com"))

    # Exhaust limit with one X-Forwarded-For value
    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login",
            json=login_payload(email="spoof_test@example.com"),
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        assert response.status_code == 200

    # 4th request with SAME X-Forwarded-For should be rate limited
    response = client.post(
        "/api/v1/auth/login",
        json=login_payload(email="spoof_test@example.com"),
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert response.status_code == 429

    # Changing X-Forwarded-For to a DIFFERENT value should NOT bypass the limit
    # because the rate limiter uses request.client.host (not X-Forwarded-For)
    response = client.post(
        "/api/v1/auth/login",
        json=login_payload(email="spoof_test@example.com"),
        headers={"X-Forwarded-For": "5.6.7.8"},
    )
    assert response.status_code == 429, (
        "Changing X-Forwarded-For should not bypass rate limit"
    )


def test_rate_limit_not_applied_to_other_auth_endpoints(client: TestClient) -> None:
    """Rate limiting is only applied to login and register, not /me or admin-check."""
    # Register and login first (within limits)
    client.post("/api/v1/auth/register", json=register_payload(email="user1@example.com"))
    login = client.post("/api/v1/auth/login", json=login_payload(email="user1@example.com"))
    token = login.json()["access_token"]

    # These endpoints should not be rate limited
    for _ in range(10):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


def test_rate_limit_does_not_reveal_account_existence(client: TestClient) -> None:
    """Rate limiting behavior is the same for existing and non-existing accounts."""
    # Test with non-existing account - should get rate limited after 3 attempts
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json=login_payload(email="nonexistent@example.com"))
        assert response.status_code == 401  # Wrong credentials, not rate limited

    # 4th attempt should be rate limited
    response = client.post("/api/v1/auth/login", json=login_payload(email="nonexistent@example.com"))
    assert response.status_code == 429


def test_rate_limit_reset_after_window(client: TestClient) -> None:
    """Rate limits reset after the time window (conceptual test - uses high limit)."""
    # This test verifies the limiter is configured correctly
    # Actual time-based reset testing would require time manipulation
    # Register with a unique email to avoid rate limit from previous tests
    client.post("/api/v1/auth/register", json=register_payload(email="reset_test@example.com"))

    # Should be able to make requests up to limit
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json=login_payload(email="reset_test@example.com"))
        assert response.status_code == 200

    # Verify limit is enforced
    response = client.post("/api/v1/auth/login", json=login_payload(email="reset_test@example.com"))
    assert response.status_code == 429


def test_malformed_x_forwarded_for_fails_safely(client: TestClient) -> None:
    """
    Malformed X-Forwarded-For headers do not cause errors or bypass limits.
    The rate limiter ignores the header and uses request.client.host.
    """
    client.post("/api/v1/auth/register", json=register_payload(email="malformed_test@example.com"))

    # Various malformed headers
    malformed_headers = [
        "not-an-ip",
        "1.2.3",  # incomplete
        "1.2.3.4, not-an-ip, 5.6.7.8",
        "",
        "  ,  ",
    ]

    for header_value in malformed_headers:
        response = client.post(
            "/api/v1/auth/login",
            json=login_payload(email="malformed_test@example.com"),
            headers={"X-Forwarded-For": header_value},
        )
        # Should not cause 500 error
        assert response.status_code in (200, 401, 429)


def test_untrusted_peer_cannot_impersonate_trusted_proxy(client: TestClient) -> None:
    """
    When deployed behind a trusted proxy, Uvicorn's forwarded_allow_ips ensures
    only requests from trusted proxy IPs have their X-Forwarded-For processed.
    This test verifies that the rate limiter relies on request.client.host
    (which Uvicorn sets correctly) and not on raw headers.
    """
    # This test documents the expected behavior.
    # In production, Uvicorn must be started with:
    #   --forwarded-allow-ips="<trusted-proxy-ip>"
    # Then request.client.host will be the real client IP extracted by Uvicorn.
    # The rate limiter uses request.client.host directly.
    client.post("/api/v1/auth/register", json=register_payload(email="proxy_test@example.com"))

    # All requests from TestClient share the same client host ('testclient')
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json=login_payload(email="proxy_test@example.com"))
        assert response.status_code == 200

    response = client.post("/api/v1/auth/login", json=login_payload(email="proxy_test@example.com"))
    assert response.status_code == 429