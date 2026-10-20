#!/usr/bin/env python3
"""Start dedicated E2E backend server with isolated SQLite database.

This script starts a FastAPI backend server configured specifically for E2E testing:
- Uses an isolated SQLite database in a temporary directory
- Uses a test-only JWT secret
- Runs on a separate port (default 8001)
- Does not interfere with normal development database
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to path so 'backend' module can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.auth import Role, User, user_roles
from backend.app.models import auth, core, rcia, traceability  # noqa: F401 - register models

import uvicorn


def create_test_users(db_url: str) -> None:
    """Create deterministic test users with required roles for E2E testing."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Ensure all roles exist
        role_catalog = {
            "admin": "Administrator",
            "project_manager": "Project Manager",
            "team_lead": "Team Lead",
            "developer": "Developer",
            "tester": "Tester",
            "client": "Client",
        }
        for code, name in role_catalog.items():
            role = session.query(Role).filter(Role.code == code).first()
            if not role:
                session.add(Role(code=code, name=name))
        session.flush()

        from backend.app.services.auth_service import hash_password
        password_hash = hash_password("password123")

        # Define test users with their emails and global roles
        test_users = [
            {
                "email": "e2etest@example.com",
                "full_name": "E2E Test User",
                "global_roles": ["project_manager"],
            },
            {
                "email": "session-test@example.com",
                "full_name": "Session Test User",
                "global_roles": ["client"],
            },
            {
                "email": "admin@example.com",
                "full_name": "Admin User",
                "global_roles": ["admin"],
            },
            {
                "email": "pm@example.com",
                "full_name": "Project Manager User",
                "global_roles": ["project_manager"],
            },
            {
                "email": "lead@example.com",
                "full_name": "Team Lead User",
                "global_roles": ["team_lead"],
            },
            {
                "email": "dev@example.com",
                "full_name": "Developer User",
                "global_roles": ["developer"],
            },
            {
                "email": "client@example.com",
                "full_name": "Client User",
                "global_roles": ["client"],
            },
            {
                "email": "devtest@example.com",
                "full_name": "Test Developer",
                "global_roles": ["developer"],
            },
        ]

        password_hash = hash_password("password123")

        try:
            for user_data in test_users:
                email = user_data["email"]
                user = session.query(User).filter(User.email == email).first()
                if user:
                    # Ensure user has the correct roles
                    for role_code in user_data["global_roles"]:
                        role = session.query(Role).filter(Role.code == role_code).first()
                        if role and role not in user.roles:
                            user.roles.append(role)
                else:
                    user = User(
                        full_name=user_data["full_name"],
                        email=user_data["email"],
                        password_hash=hash_password("password123"),
                        account_status="active",
                    )
                    session.add(user)
                    session.flush()
                    for role_code in user_data["global_roles"]:
                        role = session.query(Role).filter(Role.code == role_code).first()
                        if role:
                            user.roles.append(role)
            session.commit()
            print(f"Created/verified {len(test_users)} test users")
        except Exception as e:
            session.rollback()
            print(f"ERROR creating test users: {e}")
            raise


def main() -> int:
    # Create isolated SQLite database in temp directory
    with tempfile.TemporaryDirectory(prefix="devflow_e2e_") as tmpdir:
        db_path = Path(tmpdir) / "e2e.db"
        db_url = f"sqlite:///{db_path}"

        # Set required environment variables for E2E backend
        os.environ["DATABASE_URL"] = db_url
        os.environ["JWT_SECRET_KEY"] = "e2e-test-secret-key-for-testing-only-32-chars"
        os.environ["APP_ENVIRONMENT"] = "e2e"
        os.environ["RATE_LIMIT_LOGIN"] = "1000/minute"
        os.environ["RATE_LIMIT_REGISTER"] = "1000/minute"
        os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"

        # Create deterministic test users
        create_test_users(db_url)

        print(f"Starting E2E backend on port 8001")
        print(f"Database: {db_url}")
        print(f"Environment: e2e")
        print(f"Temp directory: {tmpdir}")

        # Run the server - this blocks until server stops
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8001,
            reload=False,
            log_level="info",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())