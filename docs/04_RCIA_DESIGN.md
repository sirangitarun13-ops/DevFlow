# Requirement Change Impact Analysis Design

## 1. Purpose

RCIA identifies project artifacts affected by a requirement change. Phase 6 implements a deterministic, explainable engine driven only by persisted Phase 5 traceability links. AI/LLM prediction, scoring, probability, analytics, reports, and frontend screens are out of scope.

## 2. Inputs and lifecycle

An authorized project user creates a `requirement_change_requests` record for a project requirement. The request records a change summary, optional proposed requirement values, requester, status, and timestamps. An authorized project manager, team lead, or admin starts an analysis for that change request. The engine persists one `impact_analyses` record and its `impact_analysis_results` snapshot.

The lifecycle is:

1. `submitted` change request is created.
2. The request may move through the approved statuses (`under_review`, `approved`, `rejected`, `implemented`, or `withdrawn`).
3. An analysis is started for the request's requirement.
4. The analysis traverses the project's traceability graph and is marked `completed` with a deterministic summary.

## 3. Traversal rules

Traversal starts at the changed requirement and follows outgoing links within the same project. Only these impact-propagating relationship types are followed:

- `implements`
- `validates`
- `affects`

`belongs_to` and `associated_with` are intentionally non-propagating. They may remain useful for traceability display but do not create impact results. The current Phase 5 service creates requirement-origin links; the traversal remains generic enough to handle additional stored downstream links without changing its deterministic rules.

The traversal records each link in order, including source and target artifact types/IDs and relationship type. A visited set prevents cycles. Results are keyed by artifact type and artifact ID, so duplicate paths cannot create duplicate result rows. Results are sorted by artifact type and artifact ID.

## 4. Impact classification

- `direct`: the artifact is reached by one impact-propagating link from the changed requirement.
- `indirect`: the artifact is reached through two or more permitted links.

No additional scoring, probability, severity, or confidence category is introduced.

## 5. Persistence model

`requirement_change_requests` stores the requested change. `impact_analyses` stores the project, changed requirement, triggering request, initiating user, lifecycle status, summary, and timestamps. `impact_analysis_results` stores each artifact type/ID, direct/indirect category, and a JSON relationship path. The path is sufficient to reproduce an explanation such as: “Task T is impacted because Requirement R has an `implements` relationship to T.”

The approved polymorphic artifact references cannot use ordinary foreign keys. Service-layer validation verifies that the requirement, change request, traceability links, and resulting project ownership are consistent.

## 6. Authorization

All RCIA endpoints require JWT authentication. Project access is required to list or retrieve change requests and analyses. Admin, Project Manager, and Team Lead roles may create change requests, update their status, and run analyses for projects they can manage. Developers, Testers, and Clients cannot trigger analyses. Cross-project requirement IDs, change requests, links, and analyses are rejected.

## 7. Determinism and limitations

Given the same project, change request, requirement, and traceability graph, the engine produces the same artifacts, classifications, paths, explanations, and ordering. PostgreSQL integration is pending environment availability; tests currently use isolated SQLite. The Phase 6 implementation does not mutate requirements or traceability links and does not generate impact reports.

## 8. API surface

The implementation is exposed under `/api/v1/projects` for change-request creation/list/detail/status updates, analysis execution, analysis retrieval, and result retrieval. See `docs/03_API_SPECIFICATION.md` for the endpoint table.
