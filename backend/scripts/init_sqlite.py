#!/usr/bin/env python3
"""Development-only SQLite database initialization script.

This script creates the SQLite database schema for local development.
It is a development-only utility and MUST NOT be used in production.

Usage:
    python -m backend.scripts.init_sqlite
    or
    python backend/scripts/init_sqlite.py

The script:
1. Creates the SQLite database file (devflow_local.db by default)
2. Creates all tables using SQLAlchemy metadata
3. Inserts the default role catalog
4. Verifies foreign key constraints are enabled

This is a DEVELOPMENT-ONLY utility. Production deployments must use
Alembic migrations against PostgreSQL.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.sqlite_path import get_sqlite_file_path, resolve_sqlite_path
from backend.app.models import auth  # noqa: F401
from backend.app.models import core  # noqa: F401
from backend.app.models import traceability  # noqa: F401
from backend.app.models import rcia  # noqa: F401


def get_database_path() -> str:
    """Get the SQLite database file path from settings using shared resolver."""
    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        raise ValueError(f"Expected SQLite URL, got: {db_url}")

    path = get_sqlite_file_path(db_url)
    if path is None:
        raise ValueError(f"Invalid SQLite URL or in-memory database: {db_url}")
    return path


def initialize_database() -> bool:
    """Initialize the SQLite database with all tables and default data.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    db_path = get_database_path()

    # Create engine with SQLite-specific settings using resolved URL
    resolved_db_url = resolve_sqlite_path(settings.database_url)
    engine = create_engine(
        resolved_db_url,
        echo=settings.database_echo,
        connect_args={"check_same_thread": False},
    )

    # Enable foreign keys and WAL mode
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    try:
        # Create all tables
        print(f"Creating database at: {db_path}")
        Base.metadata.create_all(engine)
        print("Tables created successfully.")

        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Created tables: {', '.join(sorted(tables))}")

        # Verify foreign key enforcement
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            if result == 1 or result == "ON":
                print("Foreign key enforcement: ENABLED")
            else:
                print("WARNING: Foreign key enforcement may not be active")

        # Insert default roles
        from sqlalchemy.orm import Session
        from backend.app.models.auth import Role

        with Session(engine) as session:
            # Check if roles already exist
            existing_roles = session.query(Role).count()
            if existing_roles == 0:
                roles_data = [
                    {"code": "admin", "name": "Administrator", "description": "Platform administrator"},
                    {"code": "project_manager", "name": "Project Manager", "description": "Project planning and monitoring"},
                    {"code": "team_lead", "name": "Team Lead", "description": "Team coordination and sprint planning"},
                    {"code": "developer", "name": "Developer", "description": "Assigned implementation work"},
                    {"code": "tester", "name": "Tester", "description": "Test and defect management"},
                    {"code": "client", "name": "Client", "description": "Permitted view-only stakeholder"},
                ]
                for role_data in roles_data:
                    session.add(Role(**role_data))
                session.commit()
                print("Default roles inserted.")
            else:
                print(f"Roles already exist ({existing_roles} roles).")

        print("\n✓ SQLite database initialized successfully!")
        print(f"  Database file: {db_path}")
        print(f"  Environment: {settings.app_environment}")
        return True

    except Exception as e:
        print(f"\n✗ Initialization failed: {e}", file=sys.stderr)
        return False
    finally:
        engine.dispose()


def main() -> int:
    """Main entry point."""
    print("DevFlow SQLite Development Database Initialization")
    print("=" * 50)
    print(f"Environment: {settings.app_environment}")
    print(f"Database URL: {settings.database_url}")
    print()

    if not settings.is_sqlite():
        print("ERROR: DATABASE_URL is not configured for SQLite.", file=sys.stderr)
        print("Set DATABASE_URL=sqlite:///./devflow_local.db in backend/.env", file=sys.stderr)
        return 1

    success = initialize_database()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())