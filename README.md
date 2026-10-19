# DevFlow

DevFlow is an intelligent Software Development Lifecycle (SDLC) analytics and Requirement Change Impact Analysis platform. It is planned as a web-based application for centralizing project artifacts and making the consequences of requirement changes visible across related work.

## Problem statement

Software teams commonly manage requirements, sprints, tasks, bugs, and testing activities in separate or loosely connected records. When a requirement changes, identifying affected tasks, developers, bugs, test cases, and sprint schedules can require manual analysis. This increases the risk of missed dependencies, delayed communication, inefficient planning, and reduced project visibility.

## Objectives

- Provide an integrated platform for SDLC management.
- Maintain traceability among requirements, tasks, bugs, test cases, and sprints.
- Automate Requirement Change Impact Analysis (RCIA).
- Improve project visibility through engineering analytics and dashboards.
- Support Agile planning, monitoring, and collaboration.

## Project scope and implemented foundation

- Authentication and role management
- Project, requirement, sprint, task, bug, and test-case management
- Requirement traceability and graph visualization
- Requirement Change Impact Analysis
- Analytics dashboard
- PDF report generation

Authentication, Phase 4 core SDLC modules, Phase 5 traceability, deterministic Phase 6 RCIA, the Phase 7 role-aware frontend foundation, Phase 8 project analytics, and Phase 9 dynamic PDF reports are implemented. AI prediction remains outside the current scope.

## Technology stack

| Layer | Planned technology |
| --- | --- |
| Frontend | React |
| Styling | Tailwind CSS |
| Backend | FastAPI |
| Database | PostgreSQL |
| Authentication | JWT |
| Graph visualization | React Flow |
| Charts | Recharts |
| API style | REST with JSON |

## Current implementation phase

**Phase 10 - Testing, Stabilization & Final Documentation.** This repository includes authenticated, project-scoped backend workflows, deterministic analytics aggregation, dynamic ReportLab PDF reports, and a React frontend for role-aware dashboards, requirements, change requests, traceability, RCIA, project insights, and report downloads. AI prediction, advanced graph visualization, report persistence/history, and production deployment are not implemented.

## Documentation

The `docs/` directory contains the project context, authorized implementation roadmap, database design, API specification, RCIA design, testing strategy, and setup guide.

## Backend startup (SQLite development mode)

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r backend/requirements.txt
    cp backend/.env.example backend/.env
    # Generate a secure JWT secret
    python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Edit backend/.env and set JWT_SECRET_KEY to the generated value
    python -m backend.scripts.init_sqlite
    uvicorn backend.app.main:app --reload

The root endpoint is /, the versioned health endpoint is /api/v1/health, and FastAPI's generated documentation is /docs. SQLite is used for local development; PostgreSQL is required for production.

## Backend startup (PostgreSQL production mode)

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r backend/requirements.txt
    cp backend/.env.example backend/.env
    # Edit backend/.env with PostgreSQL DATABASE_URL and JWT_SECRET_KEY
    alembic upgrade head
    uvicorn backend.app.main:app --reload

## Authentication

Registration is available at /api/v1/auth/register and assigns the safe default Client role. Login is available at /api/v1/auth/login and returns a short-lived JWT bearer token. The current user is available at /api/v1/auth/me. Set JWT_SECRET_KEY in backend/.env; do not commit credentials or secrets.

## Core API modules

The Phase 4 routes are available below /api/v1/projects. All records are project-scoped, list endpoints accept limit and offset, and access requires a project member relationship unless the user is an Admin. Project Manager, Team Lead, and Admin roles manage project artifacts; Tester may report bugs and manage test cases. The full endpoint reference is in docs/03_API_SPECIFICATION.md.

Admins and Project Managers can manage a project's Developers from the frontend `/team` page. The page uses the project membership endpoints to add existing Developer users, remove Developers (except the project owner), review workload percentages, and inspect project-scoped assigned task details. Team Leads, Developers, and Clients remain read-only for membership. No new database table or migration is required; task assignment remains project-scoped through the existing task API.

Assigned Developers may update their own task status and comment on accessible tasks. Client users have read-only project access.

Traceability routes are also available below `/api/v1/projects/{project_id}/traceability-links`. They support validated requirement-to-task, bug, test-case, sprint, and developer links with project isolation. Traceability is the data foundation consumed by the deterministic RCIA service.

RCIA routes are available below `/api/v1/projects/{project_id}` for change requests, analysis execution, and persisted result retrieval. The engine follows only impact-propagating traceability relationships and records deterministic direct/indirect explanations. It does not use AI, scoring, or reports.

The role-aware React frontend is available in `frontend/`. It provides login, protected routing, role-specific dashboards/navigation, project and requirement views, change-request actions, and persisted RCIA result views using `VITE_API_BASE_URL`. Build it with `npm run build` from that directory.

Project analytics are available at `/api/v1/projects/{project_id}/analytics/summary` and in the frontend at `/projects/:projectId/analytics`. Metrics are calculated from persisted project records; no production data is fabricated. Project progress uses completed tasks divided by total tasks, with zero progress for projects without tasks.

PDF reports are available at `/api/v1/projects/{project_id}/reports/project-summary`, `/api/v1/projects/{project_id}/reports/sdlc-status`, and `/api/v1/projects/{project_id}/reports/change-impact/{change_request_id}`. The frontend provides downloads at `/projects/:projectId/reports`; files are generated dynamically and are not persisted.

## Final implementation status

Implemented and locally verified: authentication, role-aware authorization, project/SDLC modules, traceability, deterministic RCIA, analytics, PDF reports, frontend production build, isolated automated tests, localhost browser CORS integration, and **SQLite development mode**.

Not verified: PostgreSQL integration execution, because PostgreSQL was unavailable in the development environment.

Not implemented: AI prediction, advanced graph visualization, report persistence/history, and production deployment infrastructure.

## Future improvements

Future-scope items in the SRS include external integrations, AI-assisted requirement summarization, automatic test-case suggestion, predictive project risk analysis, and daily database backup. They are not part of the baseline implementation without explicit authorization.
