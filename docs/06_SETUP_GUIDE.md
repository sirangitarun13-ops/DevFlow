# Development Environment Setup Guide

## Scope

This guide covers the Phase 2 backend foundation, Phase 3 authentication foundation, Phase 4 core SDLC modules, Phase 5 traceability, Phase 6 deterministic RCIA, Phase 7 role-aware frontend setup, Phase 8 analytics, and Phase 9 PDF reports. AI prediction remains deferred.

## Backend setup

### Option A: SQLite (local development, no PostgreSQL required)

From the repository root:

1. Create a virtual environment: `python3 -m venv .venv`.
2. Activate it: `source .venv/bin/activate`.
3. Install dependencies: `python -m pip install -r backend/requirements.txt`.
4. Copy backend/.env.example to the ignored file backend/.env:
   `cp backend/.env.example backend/.env`
5. The default `.env` already uses SQLite: `DATABASE_URL=sqlite:///./devflow_local.db`
6. Generate a JWT secret:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   Copy the output to `JWT_SECRET_KEY` in `backend/.env`.
7. Initialize the SQLite database:
   `python -m backend.scripts.init_sqlite`
8. Start the API: `uvicorn backend.app.main:app --reload`
9. Open http://localhost:8000/docs for the generated API documentation.

### Option B: PostgreSQL (production)

From the repository root:

1. Create a virtual environment: `python3 -m venv .venv`.
2. Activate it: `source .venv/bin/activate`.
3. Install dependencies: `python -m pip install -r backend/requirements.txt`.
4. Copy backend/.env.example to the ignored file backend/.env.
5. Set a long random JWT_SECRET_KEY and a PostgreSQL DATABASE_URL.
6. Run Alembic migrations:
   `alembic upgrade head`
7. Start the API: `uvicorn backend.app.main:app --reload`.
8. Open /docs for the generated API documentation.

## Required environment variables

| Variable | Purpose |
| --- | --- |
| APP_NAME | API display name. |
| APP_ENVIRONMENT | Runtime environment label. |
| API_V1_PREFIX | Versioned API prefix, normally /api/v1. |
| DATABASE_URL | Database connection URL (SQLite for dev, PostgreSQL for prod). |
| DATABASE_ECHO | SQLAlchemy SQL logging toggle; keep false normally. |
| JWT_SECRET_KEY | Required signing secret; never commit it. |
| JWT_ALGORITHM | JWT signing algorithm, currently HS256. |
| ACCESS_TOKEN_EXPIRE_MINUTES | Access-token lifetime in minutes. |
| CORS_ORIGINS | Comma-separated browser origins allowed to call the API. |
| FORWARDED_ALLOW_IPS | Trusted proxy IPs for Uvicorn (comma-separated). |

Authentication will fail safely if JWT_SECRET_KEY is not configured. No secret is hardcoded in application code.

## Alembic migration workflow (PostgreSQL only)

Review migration history:

    alembic history

Review generated SQL without applying changes:

    alembic upgrade head --sql

Apply the reviewed migration only against an authorized PostgreSQL database:

    alembic upgrade head

Phase 3 adds the authentication migration for roles, users, and user_roles. It has not been applied in this workspace. The application does not create, delete, or migrate tables at startup.

Phase 4 adds the core SDLC migration after the authentication revision. Review the generated SQL before explicitly running alembic upgrade head against PostgreSQL.

Phase 4 uses module-specific services for persistence and project-scoped authorization. The approved migration is the source of deployed database constraints; ORM metadata mirrors the representable status, role, date, and positive-version checks.

Nullable database columns remain nullable in the SQLAlchemy column definitions. The project models retain the repository's established scalar `Mapped` annotations for compatibility with the pinned SQLAlchemy/Python runtime; response schemas accurately expose nullable values.

Phase 5 adds the `20260922_03` Alembic revision for `traceability_links`. Review it with `alembic history`, generate SQL with `alembic upgrade head --sql`, and apply only against an authorized PostgreSQL environment. The polymorphic artifact IDs are validated by the traceability service because PostgreSQL cannot express a conventional foreign key to multiple artifact tables.

Phase 6 adds the `20260922_04` revision for `requirement_change_requests`, `impact_analyses`, and `impact_analysis_results`. Review the complete chain offline before applying it. RCIA tests use isolated SQLite; PostgreSQL execution remains untested.

Phase 8 analytics is derived from existing tables and requires no new migration. The endpoint is `GET /api/v1/projects/{project_id}/analytics/summary`. Its progress formula is completed tasks divided by total tasks, multiplied by 100; a project with no tasks reports 0%. Analytics access uses the same project-membership authorization as other project endpoints.

Phase 9 reports are generated dynamically with the pinned `reportlab` dependency in `backend/requirements.txt`. The available downloads are project summary, SDLC status, and change-impact reports. No report files are retained by the backend. The frontend report page is available at `/projects/:projectId/reports` and downloads authenticated PDF blobs.

## SQLite development mode

For local development without PostgreSQL:

1. Ensure `backend/.env` has:
   ```
   DATABASE_URL=sqlite:///./devflow_local.db
   ```

2. Run the initialization script (creates tables, enables FK, inserts roles):
   ```bash
   python -m backend.scripts.init_sqlite
   ```

3. The database file `devflow_local.db` is created in the backend directory and is gitignored.

4. To reset the database, delete the file and re-run the init script.

**Important:** SQLite mode is for local development only. Production deployments must use PostgreSQL with Alembic migrations. Some PostgreSQL-specific features (e.g., `gen_random_uuid()`, `JSONB`, advanced constraints) are not available in SQLite and are handled via Python-side defaults.

## Final verification commands

From the repository root:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider
    .venv/bin/alembic history
    .venv/bin/alembic upgrade head --sql

From `frontend/`:

    npm run test
    npm run build

The verified local suite uses isolated SQLite for backend behavior. PostgreSQL integration testing remains pending because PostgreSQL was unavailable in the development environment.

## Frontend setup

From `frontend/`:

1. Install dependencies: `npm install`.
2. Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` to the backend API base, including `/api/v1`.
3. Start the development server: `npm run dev`.
4. Build for production: `npm run build`.
5. Run frontend tests: `npm run test`.

The React application stores only the JWT access token in browser storage, retrieves the current user through `/auth/me`, and derives navigation from the returned role codes. Frontend role checks hide or disable actions for usability; backend authorization remains authoritative. The frontend includes `/projects/:projectId/analytics` and consumes only implemented project, requirement, traceability, change-request, RCIA, and analytics APIs. PostgreSQL is not required for the frontend build, but live data requires a running authorized backend and database.

## PostgreSQL prerequisite and limitation

PostgreSQL is required for production database operations and migrations. The psql client was unavailable during verification, so the migration was not applied and the Phase 1 schema was not executed. Authentication tests use an isolated in-memory SQLite database; this validates application behavior but is not a substitute for PostgreSQL migration testing.

Phase 4 API tests also use isolated SQLite. They validate request handling, authorization, project isolation, and approved foreign-key associations, but do not replace PostgreSQL integration tests.

### Known SQLite vs PostgreSQL differences

| Feature | PostgreSQL | SQLite (dev) |
|---------|------------|--------------|
| UUID generation | `gen_random_uuid()` | Python `uuid4()` |
| JSON storage | `JSONB` | `JSON` (text) |
| Timestamps | `now()` server default | Python `datetime.now(timezone.utc)` |
| Check constraints | Full support | Full support |
| Foreign keys | Full support | Enabled via PRAGMA |
| Concurrent writes | Full MVCC | Limited (file lock) |
| `pgcrypto` extension | Required | Not used |

These differences are handled transparently by the ORM models and session configuration.
