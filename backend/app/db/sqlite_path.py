"""SQLite path resolution utilities for DevFlow development mode.

This module provides pure path-resolution functions with no side effects.
It can be safely imported by both the application (session.py) and the
initialization script (init_sqlite.py) without triggering database creation.
"""

from pathlib import Path


def resolve_sqlite_path(db_url: str, base_dir: Path | None = None) -> str:
    """Resolve relative SQLite paths relative to a base directory.

    Args:
        db_url: The database URL (e.g., "sqlite:///./devflow_local.db")
        base_dir: The directory to resolve relative paths against.
                  Defaults to the backend directory (parent of this file's grandparent).

    Returns:
        The resolved database URL with absolute path for file-based SQLite databases.
        Returns the original URL unchanged for non-SQLite, memory, or absolute paths.
    """
    if not db_url.startswith("sqlite://"):
        return db_url

    if base_dir is None:
        # Default to backend directory: this file is at backend/app/db/sqlite_path.py
        base_dir = Path(__file__).parent.parent.parent

    if db_url.startswith("sqlite:///"):
        path = db_url[10:]  # Remove 'sqlite:///'
        if path == ":memory:":
            return db_url
        if not Path(path).is_absolute():
            return f"sqlite:///{base_dir / path}"
        return db_url
    elif db_url.startswith("sqlite://"):
        path = db_url[9:]  # Remove 'sqlite://'
        if not path or path == ":memory:":
            return db_url
        if not Path(path).is_absolute():
            return f"sqlite:///{base_dir / path}"
        return f"sqlite:///{path}"
    return db_url


def get_sqlite_file_path(db_url: str, base_dir: Path | None = None) -> str | None:
    """Extract the filesystem path from a SQLite URL.

    Args:
        db_url: The database URL (e.g., "sqlite:///./devflow_local.db")
        base_dir: The directory to resolve relative paths against.

    Returns:
        The absolute filesystem path, or None for non-SQLite, memory, or invalid URLs.
    """
    resolved = resolve_sqlite_path(db_url, base_dir)
    if resolved.startswith("sqlite:///"):
        path = resolved[10:]
        if path == ":memory:":
            return None
        return str(Path(path).resolve())
    return None