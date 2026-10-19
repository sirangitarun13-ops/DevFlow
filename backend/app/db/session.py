"""SQLAlchemy engine and request-scoped session dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.sqlite_path import resolve_sqlite_path
from backend.app.models import auth, core, rcia, traceability  # noqa: F401 - register models
from backend.app.models.auth import Role


def _configure_sqlite_engine(engine: Engine) -> None:
    """Configure SQLite-specific settings: enable FK enforcement and WAL mode."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _insert_default_roles(engine: Engine) -> None:
    """Insert default roles if they don't exist (SQLite development mode only)."""
    with Session(engine) as session:
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


resolved_db_url = resolve_sqlite_path(settings.database_url)

engine = create_engine(
    resolved_db_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if settings.is_sqlite() else {},
)

if settings.is_sqlite():
    _configure_sqlite_engine(engine)

# Create tables for SQLite development mode
if settings.is_sqlite():
    Base.metadata.create_all(engine)
    _insert_default_roles(engine)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session and close it after request processing."""

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
