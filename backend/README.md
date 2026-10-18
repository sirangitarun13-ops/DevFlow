# DevFlow Backend

This directory contains the Phase 2 FastAPI foundation and the Phase 3 authentication foundation.

## Run locally

From the repository root:

    source .venv/bin/activate
    uvicorn backend.app.main:app --reload

Set DATABASE_URL and JWT_SECRET_KEY in the ignored backend/.env before using authentication against PostgreSQL. The application does not run migrations or create tables automatically.

## Migration workflow

Review the migration first, then apply it explicitly when PostgreSQL is available:

    alembic history
    alembic upgrade head

Phase 3 supplies the authentication migration but does not apply it in this workspace.
