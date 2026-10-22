# DevFlow

DevFlow is an intelligent Software Development Lifecycle (SDLC) analytics and Requirement Change Impact Analysis (RCIA) platform. It is a web-based application for centralizing project artifacts and making the consequences of requirement changes visible across related work.

## Problem Statement

Software teams commonly manage requirements, sprints, tasks, bugs, and testing activities in separate or loosely connected records. When a requirement changes, identifying affected tasks, developers, bugs, test cases, and sprint schedules can require manual analysis. This increases the risk of missed dependencies, delayed communication, inefficient planning, and reduced project visibility.

## Objectives and Key Features

- **Integrated SDLC Platform**: Unified management of projects, requirements, sprints, tasks, bugs, and test cases
- **Traceability**: Maintain bidirectional links among requirements, tasks, bugs, test cases, sprints, and team members
- **Requirement Change Impact Analysis (RCIA)**: Deterministic impact propagation through traceability graph with direct/indirect classification
- **Engineering Analytics**: Project progress, workload distribution, and requirement coverage metrics
- **Dynamic PDF Reports**: Project summary, SDLC status, and change-impact reports generated on demand
- **Role-Aware Access Control**: Six roles (Admin, Project Manager, Team Lead, Developer, Tester, Client) with project-scoped permissions
- **Authentication**: JWT-based authentication with registration, login, and secure password hashing (Argon2)

## Current Capabilities and Scope

| Capability | Status | Notes |
|------------|--------|-------|
| Authentication & Authorization | Implemented | JWT, role-based, project-scoped |
| Project & SDLC Management | Implemented | Requirements, sprints, tasks, bugs, test cases |
| Traceability Links | Implemented | Validated, project-isolated |
| RCIA Engine | Implemented | Deterministic, graph-based, no AI |
| Analytics Dashboard | Implemented | Progress, workload, coverage |
| PDF Report Generation | Implemented | ReportLab, dynamic (not persisted) |
| Frontend (React + Vite) | Implemented | Role-aware routing, protected pages |
| E2E Tests (Playwright) | Implemented | Isolated backend, CORS verified |
| SQLite Development Mode | Implemented | No PostgreSQL required locally |
| PostgreSQL Production Mode | Designed | Migrations ready, not verified in CI |
| AI Prediction | Not Implemented | Out of scope |
| Advanced Graph Visualization | Not Implemented | Basic React Flow integration only |
| Report Persistence/History | Not Implemented | Reports generated on demand |
| Production Deployment | Not Implemented | Docker, CI/CD not included |

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Vite 7 |
| **Styling** | Tailwind CSS 3.4 |
| **State/Routing** | React Router 7, React Context |
| **Graph Visualization** | React Flow 11 |
| **Charts** | Recharts (via analytics components) |
| **Testing (Frontend)** | Vitest, Playwright |
| **Backend** | FastAPI 0.115, Python 3.11+ |
| **Database ORM** | SQLAlchemy 2.0 |
| **Database (Dev)** | SQLite (file-based, WAL mode) |
| **Database (Prod)** | PostgreSQL 15+ with psycopg 3 |
| **Migrations** | Alembic 1.14 |
| **Authentication** | JWT (PyJWT), Argon2 (argon2-cffi) |
| **Rate Limiting** | slowapi |
| **PDF Generation** | ReportLab 4.2 |
| **Testing (Backend)** | pytest 8.3, httpx |
| **Configuration** | pydantic-settings 2.7 |

## System Architecture

```mermaid
graph TB
    subgraph "Frontend (React + Vite)"
        UI[Browser UI]
        API_CLIENT[API Client]
        AUTH_CTX[Auth Context]
        PAGES[Pages: Dashboard, Requirements, RCIA, Analytics, Reports]
    end

    subgraph "Backend (FastAPI)"
        API[FastAPI App]
        AUTH[Auth Routes]
        CORE[Core SDLC Routes]
        TRACE[Traceability Routes]
        RCIA[RCIA Routes]
        ANALYTICS[Analytics Routes]
        REPORTS[Reports Routes]
        USERS[User Routes]
        SERVICES[Service Layer]
        MODELS[SQLAlchemy Models]
    end

    subgraph "Database"
        SQLITE[(SQLite Dev)]
        PG[(PostgreSQL Prod)]
    end

    UI --> API_CLIENT
    API_CLIENT --> AUTH_CTX
    AUTH_CTX --> PAGES
    PAGES --> API_CLIENT
    API_CLIENT -.->|HTTPS/REST| API
    API --> AUTH
    API --> CORE
    API --> TRACE
    API --> RCIA
    API --> ANALYTICS
    API --> REPORTS
    API --> USERS
    CORE --> SERVICES
    TRACE --> SERVICES
    RCIA --> SERVICES
    ANALYTICS --> SERVICES
    REPORTS --> SERVICES
    SERVICES --> MODELS
    MODELS -.-> SQLITE
    MODELS -.-> PG
```

## Major Modules and Responsibilities

### Backend (`backend/app/`)

| Module | Responsibility |
|--------|----------------|
| `api/routes/auth.py` | Registration, login, current user, JWT token management |
| `api/routes/core.py` | Projects, requirements, sprints, tasks, bugs, test cases, milestones |
| `api/routes/traceability.py` | Traceability link CRUD with validation |
| `api/routes/rcia.py` | Change requests, impact analysis execution, result retrieval |
| `api/routes/analytics.py` | Project summary metrics (progress, workload, coverage) |
| `api/routes/reports.py` | Dynamic PDF generation (project summary, SDLC status, change impact) |
| `api/routes/users.py` | User listing, project membership management |
| `services/` | Business logic, authorization, RCIA engine, report builders |
| `models/` | SQLAlchemy ORM models for all entities |
| `schemas/` | Pydantic request/response schemas |
| `core/config.py` | Environment-backed settings with validation |
| `core/rate_limit.py` | SlowAPI rate limiter for auth endpoints |
| `db/` | Database session, SQLite path resolver, base model |

### Frontend (`frontend/src/`)

| Module | Responsibility |
|--------|----------------|
| `pages/` | Page components for each route (Dashboard, Requirements, Tasks, RCIA, Analytics, Reports, Team) |
| `api/client.ts` | Axios instance with JWT interceptor |
| `api/types.ts` | TypeScript interfaces matching backend schemas |
| `auth/AuthContext.tsx` | Global auth state, login/logout, token persistence |
| `layout.tsx` | Role-aware navigation, protected routes |
| `components/` | Reusable UI components (tables, forms, charts, React Flow) |

## Repository Directory Structure

```text
DevFlow/
├── README.md                    # This file
├── .gitignore                   # Root ignore rules
├── .env.example                 # Reference: all environment variables
├── alembic.ini                  # Alembic configuration (PostgreSQL default)
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Root requirements (empty, use backend/)
├── alembic/                     # Database migrations
│   ├── env.py                   # Migration environment (reads backend/.env)
│   ├── script.py.mako           # Migration template
│   └── versions/                # Migration scripts (6 revisions)
├── backend/
│   ├── .gitignore               # Backend-specific ignores
│   ├── .env.example             # Backend environment template
│   ├── requirements.txt         # Python dependencies
│   ├── README.md                # Backend-specific docs
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── api/                 # API route modules
│   │   ├── core/                # Config, rate limiting, security
│   │   ├── db/                  # Database session, base model
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   └── services/            # Business logic services
│   └── scripts/
│       ├── init_sqlite.py       # SQLite schema + role seed (dev only)
│       ├── seed_demo.py         # Demo data seed (idempotent)
│       ├── seed_review_demo.py  # Extended demo data for review
│       └── start_e2e_backend.py # Isolated backend for E2E tests
├── frontend/
│   ├── .gitignore               # Frontend-specific ignores
│   ├── .env.example             # Frontend environment template
│   ├── package.json             # npm dependencies and scripts
│   ├── package-lock.json        # Locked dependencies
│   ├── tsconfig.json            # TypeScript config
│   ├── vite.config.ts           # Vite config
│   ├── tailwind.config.js       # Tailwind config
│   ├── postcss.config.js        # PostCSS config
│   ├── index.html               # Entry HTML
│   ├── src/                     # React application source
│   │   ├── main.tsx             # App bootstrap
│   │   ├── App.tsx              # Root component, routing
│   │   ├── api/                 # API client and types
│   │   ├── auth/                # Auth context
│   │   ├── pages/               # Page components
│   │   ├── project/             # Project context/hooks
│   │   └── styles.css           # Global styles (Tailwind)
│   ├── e2e/                     # Playwright E2E tests
│   ├── playwright.config.ts     # Playwright config
│   ├── global-setup.ts          # E2E global setup
│   └── global-teardown.ts       # E2E global teardown
├── database/
│   └── schema.sql               # PostgreSQL schema design (reference only)
├── diagrams/
│   └── devflow_database_erd.mmd # Mermaid ER diagram
├── docs/
│   ├── 00_PROJECT_CONTEXT.md
│   ├── 01_IMPLEMENTATION_PLAN.md
│   ├── 02_DATABASE_DESIGN.md
│   ├── 03_API_SPECIFICATION.md
│   ├── 04_RCIA_DESIGN.md
│   ├── 05_TESTING_STRATEGY.md
│   └── 06_SETUP_GUIDE.md
├── tests/                       # Backend pytest tests
│   ├── test_authentication.py
│   ├── test_core_modules.py
│   ├── test_analytics.py
│   ├── test_reports.py
│   ├── test_rate_limit.py
│   ├── test_sqlite_dev.py
│   ├── test_team_management.py
│   └── test_backend_foundation.py
└── scripts/                     # Utility scripts (currently empty)
```

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Frontend build tooling |
| npm | 10+ | Frontend package manager |
| PostgreSQL | 15+ | Production database (optional for local dev) |
| Git | 2.30+ | Version control |

**Note**: SQLite is used for local development; PostgreSQL is required for production. No Docker is required for local development.

## Installation and Environment Configuration

### 1. Clone the Repository

```bash
git clone <repository-url>
cd DevFlow
```

### 2. Backend Setup

```bash
# From repository root
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env and set JWT_SECRET_KEY (generate with command below)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste the output into JWT_SECRET_KEY in backend/.env

# Initialize SQLite database (development only)
python -m backend.scripts.init_sqlite

# Optional: Seed demo data
python -m backend.scripts.seed_demo
# Or for extended review data:
python -m backend.scripts.seed_review_demo

# Start the API server
uvicorn backend.app.main:app --reload
```

The API will be available at:
- Root: http://localhost:8000/
- Health: http://localhost:8000/api/v1/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3. Frontend Setup

```bash
# From repository root
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env if backend runs on a different URL (default: http://localhost:8000/api/v1)

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173 (or next available port).

### 4. Production Database Setup (PostgreSQL)

```bash
# From repository root with .venv activated
# 1. Ensure PostgreSQL is running and accessible
# 2. Create database and user
# 3. Update backend/.env with PostgreSQL DATABASE_URL:
#    DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname
# 4. Run migrations
alembic upgrade head
# 5. Start the API server
uvicorn backend.app.main:app --reload
```

## Database Initialization and Migrations

### SQLite (Development)
- File: `backend/devflow_local.db` (gitignored)
- Created by: `python -m backend.scripts.init_sqlite`
- Creates all tables, enables foreign keys + WAL mode, seeds default roles
- Reset: delete the `.db` file and re-run init script

### PostgreSQL (Production)
- Managed via Alembic migrations in `alembic/versions/`
- Current migrations:
  1. `20260921_01_auth_foundation.py` - Roles, users, user_roles
  2. `20260921_02_core_sdlc.py` - Projects, SDLC entities
  3. `20260922_03_traceability.py` - Traceability links
  4. `20260922_04_rcia.py` - Change requests, impact analyses
  5. `20260923_05_requirement_dependency.py` - Requirement dependencies
  6. `20260923_06_impact_analysis_artifact_type.py` - Impact analysis artifact types
- Apply: `alembic upgrade head`
- Review SQL: `alembic upgrade head --sql`

**Important**: The `alembic/env.py` reads `DATABASE_URL` from `backend/.env` (via `backend.app.core.config.settings`). Ensure `backend/.env` has the correct PostgreSQL URL before running migrations.

## Running Tests

### Backend Tests

```bash
# From repository root with .venv activated
# Run all tests (uses isolated SQLite in-memory databases)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider

# Run specific test file
.venv/bin/pytest tests/test_authentication.py -v

# Run with coverage
.venv/bin/pytest --cov=backend.app --cov-report=term-missing
```

### Frontend Tests

```bash
# From frontend/ directory
npm run test          # Vitest unit tests
npm run test:e2e      # Playwright E2E tests (requires running backend)
```

### E2E Tests (Full Stack)

The Playwright E2E tests start an isolated backend instance automatically:

```bash
cd frontend
npm run test:e2e
```

## Accessing the Application

| Interface | URL | Purpose |
|-----------|-----|---------|
| Frontend (Dev) | http://localhost:5173 | Main application UI |
| Backend API | http://localhost:8000 | API root |
| API Health | http://localhost:8000/api/v1/health | Health check |
| Swagger UI | http://localhost:8000/docs | Interactive API docs |
| ReDoc | http://localhost:8000/redoc | Alternative API docs |

### Default Roles (Seeded by init_sqlite)

| Role Code | Name | Description |
|-----------|------|-------------|
| `admin` | Administrator | Platform administrator |
| `project_manager` | Project Manager | Project planning and monitoring |
| `team_lead` | Team Lead | Team coordination and sprint planning |
| `developer` | Developer | Assigned implementation work |
| `tester` | Tester | Test and defect management |
| `client` | Client | Permitted view-only stakeholder |

Registration assigns the `client` role by default. Project membership and project roles are managed separately.

## API Documentation

The complete API specification is in [`docs/03_API_SPECIFICATION.md`](docs/03_API_SPECIFICATION.md).

Key endpoint groups:
- `/api/v1/auth/*` - Authentication (register, login, me)
- `/api/v1/projects/*` - Project and SDLC entity management
- `/api/v1/projects/{project_id}/traceability-links/*` - Traceability
- `/api/v1/projects/{project_id}/change-requests/*` - Change requests
- `/api/v1/projects/{project_id}/impact-analyses/*` - RCIA execution
- `/api/v1/projects/{project_id}/analytics/summary` - Analytics
- `/api/v1/projects/{project_id}/reports/*` - PDF report downloads

All project-scoped endpoints require project membership (except Admin).

## Screenshots and Diagrams

| Asset | Location | Description |
|-------|----------|-------------|
| Database ERD | `diagrams/devflow_database_erd.mmd` | Mermaid entity-relationship diagram |
| Architecture Diagram | Above (in this README) | Mermaid system architecture |

To view the Mermaid diagrams, use a Markdown viewer with Mermaid support (GitHub, VS Code with extension, or mermaid.live).

## Known Limitations and Setup Caveats

1. **SQLite vs PostgreSQL Differences**: Development uses SQLite; production requires PostgreSQL. Key differences:
   - UUID generation: Python `uuid4()` vs `gen_random_uuid()`
   - JSON storage: SQLite `JSON` (text) vs PostgreSQL `JSONB`
   - Timestamps: Python `datetime.now(timezone.utc)` vs server `now()`
   - Concurrent writes: SQLite has file-lock limitations

2. **PostgreSQL Not Verified in CI**: Alembic migrations are designed for PostgreSQL but have not been executed against a live PostgreSQL instance in the current environment.

3. **No Production Deployment Config**: Docker, Kubernetes, CI/CD pipelines, and reverse proxy configuration are not included.

4. **Report Persistence**: PDF reports are generated dynamically on each request and are not stored.

5. **AI Features**: Requirement summarization, test-case suggestion, and predictive risk analysis are not implemented.

6. **Frontend Build for Production**: `npm run build` outputs to `frontend/dist/` (gitignored). Serve with a static file server or integrate with backend.

7. **Rate Limiting**: Applied only to `/auth/login` and `/auth/register` endpoints.

8. **CORS**: Configured via `CORS_ORIGINS` in `backend/.env`. Default allows `http://localhost:5173` and `http://127.0.0.1:5173`.

## Contributors

- [Starun](https://github.com/starun) - Primary developer

## Project Links

- Repository: [GitHub URL - to be added]
- Issue Tracker: [GitHub Issues - to be added]
- Demo Video: [URL - to be added]
- Deployed Demo: [URL - to be added]

## License

[License to be determined - not yet specified]