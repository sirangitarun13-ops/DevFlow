# API Specification

## Purpose

This document defines the DevFlow REST API through the completed Phase 4 hardening pass. It records the system endpoints, authentication contract, response safety rules, project-scoped SDLC routes, and versioning approach.

## System endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | / | Basic API service metadata. |
| GET | /api/v1/ | Versioned API service metadata. |
| GET | /api/v1/health | Process health; database is intentionally not probed. |

## Authentication endpoints

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| POST | /api/v1/auth/register | JSON: full_name, email, password. | 201 with safe user profile; public registration receives Client role. |
| POST | /api/v1/auth/login | JSON: email, password. | 200 with bearer JWT and safe user profile. |
| GET | /api/v1/auth/me | Bearer JWT. | 200 with current safe user profile. |
| GET | /api/v1/auth/admin-check | Bearer JWT with Admin role. | 200 for Admin; 403 for authenticated users without Admin. |

Authentication uses JWT bearer access tokens. The token subject is the user UUID, and the token includes role codes, issued-at time, and an expiration time. The backend validates the signature, algorithm, expiration, subject, account status, and current user record. Logout is client-side token removal as permitted by AUTH-04; no server-side session store is implemented.

## Roles

The supported SRS roles are Admin, Project Manager, Team Lead, Developer, Tester, and Client. Public registration assigns Client only and never grants Admin by default. Role assignment is kept in the authentication service layer; a general role-management CRUD API is outside this phase.

## Routing and response approach

Versioned routes are grouped below /api/v1 and implemented as modular FastAPI routers. Responses are structured JSON. Password hashes, passwords, JWT signing secrets, and other sensitive fields are excluded from response schemas.

## Documentation approach

FastAPI-generated OpenAPI documentation is available at /docs while the local server is running. Future resource endpoints must be added as modular routers under /api/v1 and documented alongside their authorized implementation phase.

## Phase 4 core SDLC endpoints

Persistence is organized in module services (`project_service`, `milestone_service`, `requirement_service`, `sprint_service`, `task_service`, `comment_service`, `bug_service`, and `test_case_service`). Routers handle request parsing, authentication dependencies, and responses; services perform persistence and business validation.

All endpoints require a bearer token. Project lists and records are scoped to project membership, except Admin users. Create and update routes require project-management roles unless otherwise noted.

Authorization in Phase 4 is as follows: Admin has global access; Project Manager and Team Lead manage records in projects they can access; assigned Developers may update only their own task status and may comment on accessible tasks; Testers may create/update bugs and test cases in accessible projects; Client users remain read-only. Assignment targets must already be project members.

| Resource | Routes |
| --- | --- |
| Projects | POST and GET /api/v1/projects; GET and PATCH /api/v1/projects/{project_id} |
| Members | POST and GET /api/v1/projects/{project_id}/members; DELETE /api/v1/projects/{project_id}/members/{user_id}; GET /api/v1/projects/{project_id}/members/{user_id}/tasks |
| Milestones | POST and GET /api/v1/projects/{project_id}/milestones; GET and PATCH /api/v1/projects/milestones/{id} |
| Requirements | POST and GET /api/v1/projects/{project_id}/requirements; GET and PATCH /api/v1/projects/requirements/{id} |
| Sprints | POST and GET /api/v1/projects/{project_id}/sprints; GET and PATCH /api/v1/projects/sprints/{id} |
| Tasks | POST and GET /api/v1/projects/{project_id}/tasks; GET and PATCH /api/v1/projects/tasks/{id} |
| Comments | POST and GET /api/v1/projects/tasks/{task_id}/comments |
| Bugs | POST and GET /api/v1/projects/{project_id}/bugs; GET and PATCH /api/v1/projects/bugs/{id} |
| Test cases | POST and GET /api/v1/projects/{project_id}/test-cases; GET and PATCH /api/v1/projects/test-cases/{id} |

List endpoints support limit and offset pagination. Requirements do not have a milestone association because that foreign key is absent from the approved schema.

## Project Manager team management

The team-management surface reuses the approved `project_members` junction table and does not add a new database entity. Admins and Project Managers with access to a project may add or remove Developers. Team Leads, Developers, and Clients cannot mutate membership. `GET /api/v1/users/developers?project_id={project_id}` returns safe, active users with the global Developer role who are not already members of that project; optional `search`, `limit`, and `offset` query parameters filter the directory. Password hashes and other sensitive fields are never returned.

`POST /api/v1/projects/{project_id}/members` adds an existing Developer with a `developer` project-role label. `DELETE /api/v1/projects/{project_id}/members/{user_id}` removes a Developer; the project owner cannot be removed. Responses include the user's name, email, global roles, project role, membership timestamp, assigned/completed/in-progress/pending task counts, and completion percentage (`completed / assigned * 100`, rounded to two decimals, or `0` when unassigned). `GET /api/v1/projects/{project_id}/members/{user_id}/tasks` returns only tasks assigned to that Developer within the selected project, including title, description, status, priority, requirement/sprint IDs, and due date.

The frontend exposes this as the role-aware **Team & developers** page at `/team`, using the selected project context. It does not grant permissions: all operations remain enforced by the backend.

The Phase 4 migration is present in Alembic but has not been applied in this workspace. SQLite tests cover application behavior and access control; PostgreSQL integration remains untested because PostgreSQL is unavailable.

## Phase 6 RCIA endpoints

RCIA is deterministic and traceability-driven. Change-request creation, status updates, and analysis execution require Admin, Project Manager, or Team Lead project-management access. Project members may read change requests and analyses. Clients, Developers, and Testers cannot trigger analyses.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/projects/{project_id}/requirements/{requirement_id}/change-requests` | Create a validated requirement change request. |
| GET | `/api/v1/projects/{project_id}/change-requests` | List project change requests with `limit` and `offset`. |
| GET | `/api/v1/projects/{project_id}/change-requests/{change_request_id}` | Retrieve a change request. |
| PATCH | `/api/v1/projects/{project_id}/change-requests/{change_request_id}` | Update the approved change-request status. |
| POST | `/api/v1/projects/{project_id}/change-requests/{change_request_id}/analyses` | Run deterministic impact analysis. |
| GET | `/api/v1/projects/{project_id}/analyses/{analysis_id}` | Retrieve persisted analysis metadata. |
| GET | `/api/v1/projects/{project_id}/analyses/{analysis_id}/results` | Retrieve sorted persisted impact results and paths. |

The engine follows only `implements`, `validates`, and `affects` links. `belongs_to` and `associated_with` are non-propagating. Results are classified as `direct` or `indirect`, include a structured relationship path, and are cycle-safe and deterministic. Phase 6 did not implement AI prediction or impact scoring; Phase 9 adds separate PDF report generation over persisted RCIA results.

## Phase 8 analytics endpoint

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/analytics/summary` | Return project-scoped deterministic progress and SDLC metrics. |

The summary aggregates requirement status/priority, milestone status, task status, sprint status and active-sprint progress, bug status/severity, test-case status, change-request lifecycle status, and persisted RCIA analysis/result counts. Project progress is `completed tasks / total tasks * 100`, rounded to two decimals and reported as `0` when there are no tasks. The endpoint requires project access and does not expose records from other projects. Empty categories return zero totals and empty maps; authorization or database errors are returned as errors rather than misleading zeroes.

## Phase 9 PDF report endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/reports/project-summary` | Download a project summary PDF. |
| GET | `/api/v1/projects/{project_id}/reports/sdlc-status` | Download a current SDLC status PDF. |
| GET | `/api/v1/projects/{project_id}/reports/change-impact/{change_request_id}` | Download a requirement change-impact PDF using persisted RCIA results. |

Report endpoints return `application/pdf` with an attachment filename and enforce the existing project-access dependency. Reports are generated dynamically with ReportLab; no report database table or PDF storage is introduced. A change-impact report explicitly states when no analysis has been generated.

## Browser integration and security

The backend accepts browser requests from the configured `CORS_ORIGINS` list (localhost Vite origins are provided in the example environment). CORS does not replace JWT authentication or project authorization; every protected endpoint still validates the bearer token and project access.

## Frontend integration notes

The React frontend uses `VITE_API_BASE_URL` and the documented JWT endpoints. It retrieves `/auth/me` after login, renders role-aware navigation for the six SRS roles, and uses the existing project-scoped endpoints plus the Phase 8 analytics summary for dashboard and detail views. It does not introduce client-side authorization as a replacement for backend enforcement or invent unsupported administrative/report APIs.

## Phase 5 traceability endpoints

Traceability links are project-scoped and require JWT authentication. Project Managers, Team Leads, and Admins may create or delete links. Any user with access to the project may read links; Clients remain read-only. The project path is validated against both referenced artifacts, so a client-supplied project identifier cannot authorize cross-project access.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/projects/{project_id}/traceability-links` | Create a validated traceability link. |
| GET | `/api/v1/projects/{project_id}/traceability-links` | List project links, optionally filtered by `relationship_type`; supports `limit` and `offset`. |
| GET | `/api/v1/projects/{project_id}/requirements/{requirement_id}/traceability-links` | List all links touching a requirement. |
| GET | `/api/v1/projects/{project_id}/artifacts/{artifact_type}/{artifact_id}/traceability-links` | Reverse/forward lookup for a supported artifact. |
| GET | `/api/v1/projects/{project_id}/traceability-links/{link_id}` | Retrieve one link. |
| DELETE | `/api/v1/projects/{project_id}/traceability-links/{link_id}` | Delete a link; management permission required. |

Supported artifact types are `requirement`, `task`, `bug`, `test_case`, `sprint`, and `user`. Supported relationship types are `implements`, `validates`, `affects`, `belongs_to`, and `associated_with`. Phase 5 permits requirement-to-task (`implements`), requirement-to-bug (`affects`), requirement-to-test-case (`validates`), requirement-to-sprint (`belongs_to`), and requirement-to-user (`belongs_to`) links, with `associated_with` where documented by the service matrix. Links are directional, duplicate tuples are rejected, and self-links are rejected. The deterministic Phase 6 RCIA service consumes these links; AI prediction and scoring are not implemented.
