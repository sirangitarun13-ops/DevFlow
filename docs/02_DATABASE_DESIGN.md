# Database Design

## 1. Purpose and Scope

This Phase 1 design defines a normalized PostgreSQL schema for DevFlow's persistent SDLC data. It supports the SRS entities (users, projects, requirements, sprints, tasks, bugs, test cases, reports, and traceability), along with SRS-required milestones and task comments. It also defines justified support for requirement change requests, recorded RCIA runs/results, role assignments, and audit records.

This is a design artifact plus the approved implementation contract. The Phase 5 traceability and Phase 6 RCIA migrations have been authored but not executed in this workspace. No seed data, frontend, analytics, or AI-based RCIA logic is included.

## 2. Database Technology

PostgreSQL is the SRS-mandated relational database. UUID primary keys prevent predictable identifiers and work well with future distributed client/server boundaries. The draft SQL enables PostgreSQL's `pgcrypto` extension solely to generate UUID values through `gen_random_uuid()`; deployment approval is required before using it.

## 3. Design Principles

- Use lowercase `snake_case` names, singular table names, UUID `id` primary keys, and `*_id` foreign-key columns.
- Store each fact once and use junction tables for many-to-many relationships.
- Enforce project-level isolation through `project_id` on project-owned records.
- Use `timestamptz` timestamps in UTC and preserve immutable audit events.
- Use controlled text values with database `CHECK` constraints rather than PostgreSQL enums, keeping later value evolution migration-friendly.
- Do not persist derived dashboard metrics; calculate them from source data in a future phase.

## 4. Entity Overview

| Table | Purpose |
| --- | --- |
| `roles`, `users`, `user_roles` | Global user identity and SRS role assignments. |
| `projects`, `project_members`, `milestones` | Project metadata, membership, and planning milestones. |
| `requirements`, `requirement_change_requests` | Versioned requirement records and proposed/recorded changes. |
| `sprints`, `tasks`, `task_comments` | Agile planning, assigned work, and collaboration comments. |
| `bugs`, `test_cases` | Defect and validation artifacts. |
| `traceability_links` | Typed links among supported project artifacts for RCIA. |
| `impact_analyses`, `impact_analysis_results` | An RCIA run and its persisted affected-artifact snapshot. |
| `reports` | Metadata/reference for generated project reports; not PDF binary data. |
| `audit_logs` | Append-only metadata on auditable project changes. |

## 5. Entity Relationship Description

A user may have one or more global roles through `user_roles`. A project has one creator, many members, and many milestones, requirements, sprints, tasks, bugs, test cases, reports, and audit records. `project_members` resolves project-user membership and may carry a project-specific role label if later authorization policy requires it.

Requirements are project-scoped and versioned. A requirement can have many change requests, tasks, traceability links, and RCIA runs. Tasks may be associated with one requirement and one sprint; tasks have one optional assignee and many comments. Bugs may be associated with a requirement and/or task. Test cases are associated with one requirement. The generic traceability table stores project-scoped typed links so a requirement can link to supported artifacts without duplicating relationship tables. An RCIA run stores the changed requirement and optional change request; each result stores an affected artifact reference and its relationship path.

## 6. Detailed Table Specifications

Legend: PK = primary key; FK = foreign key; NN = NOT NULL. All UUID identifiers default to `gen_random_uuid()` unless stated otherwise. All foreign keys are `ON DELETE RESTRICT` by default, except explicitly noted.

### roles

Purpose: controlled global role catalogue required by the SRS.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| code | varchar(32) | NN, UNIQUE; CHECK one of `admin`, `project_manager`, `team_lead`, `developer`, `tester`, `client`. |
| name | varchar(100) | NN, UNIQUE. |
| description | text | Nullable. |
| created_at | timestamptz | NN, default `now()`. |

### users

Purpose: user identity and authentication-related storage, without implementing authentication.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| full_name | varchar(150) | NN. |
| email | varchar(254) | NN, UNIQUE. |
| password_hash | text | NN; only a secure hash, never a plaintext password. |
| account_status | varchar(20) | NN, default `active`; CHECK `active`, `inactive`, `suspended`. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### user_roles

Purpose: junction table for many-to-many global role assignment.

| Column | Type | Rules |
| --- | --- | --- |
| user_id | uuid | PK/FK to `users.id`, NN. |
| role_id | uuid | PK/FK to `roles.id`, NN. |
| assigned_at | timestamptz | NN, default `now()`. |
| assigned_by_user_id | uuid | FK to `users.id`, nullable. |

### projects

Purpose: core project metadata.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| name | varchar(200) | NN. |
| description | text | Nullable. |
| status | varchar(20) | NN, default `planned`; CHECK `planned`, `active`, `on_hold`, `completed`, `cancelled`. |
| start_date | date | Nullable. |
| end_date | date | Nullable; CHECK end date is not before start date. |
| created_by_user_id | uuid | FK to `users.id`, NN. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

UNIQUE: `(name, created_by_user_id)` is intentionally not imposed because the SRS does not define project-name scope.

### project_members

Purpose: project-user membership junction table.

| Column | Type | Rules |
| --- | --- | --- |
| project_id | uuid | PK/FK to `projects.id`, NN. |
| user_id | uuid | PK/FK to `users.id`, NN. |
| project_role | varchar(32) | Nullable; constrained to the role codes when used. |
| joined_at | timestamptz | NN, default `now()`. |

### milestones

Purpose: project milestones required by SRS project management.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| name | varchar(200) | NN; UNIQUE with `project_id`. |
| description | text | Nullable. |
| target_date | date | Nullable. |
| status | varchar(20) | NN, default `planned`; CHECK `planned`, `in_progress`, `completed`, `cancelled`. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### requirements

Purpose: functional and non-functional requirement records.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| requirement_key | varchar(50) | NN; UNIQUE with `project_id`. |
| title | varchar(250) | NN. |
| description | text | NN. |
| requirement_type | varchar(20) | NN; CHECK `functional`, `non_functional`. |
| priority | varchar(20) | NN; CHECK `low`, `medium`, `high`, `critical`. |
| status | varchar(20) | NN, default `draft`; CHECK `draft`, `proposed`, `approved`, `in_progress`, `completed`, `rejected`. |
| version | integer | NN, default 1; CHECK `version > 0`. |
| created_by_user_id | uuid | FK to `users.id`, NN. |
| updated_by_user_id | uuid | FK to `users.id`, nullable. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### requirement_change_requests

Purpose: record a proposed or applied requirement change and maintain a deliberate change history for RCIA.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| requirement_id | uuid | FK to `requirements.id`, NN. |
| requested_by_user_id | uuid | FK to `users.id`, NN. |
| reviewed_by_user_id | uuid | FK to `users.id`, nullable. |
| change_summary | text | NN. |
| proposed_description | text | Nullable. |
| proposed_priority | varchar(20) | Nullable; same priority CHECK as requirements. |
| proposed_status | varchar(20) | Nullable; same requirement-status CHECK. |
| status | varchar(20) | NN, default `submitted`; CHECK `submitted`, `under_review`, `approved`, `rejected`, `implemented`, `withdrawn`. |
| reviewed_at | timestamptz | Nullable. |
| implemented_at | timestamptz | Nullable. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### sprints

Purpose: project-scoped Agile sprint planning and status.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| name | varchar(150) | NN; UNIQUE with `project_id`. |
| goal | text | Nullable. |
| start_date | date | NN. |
| end_date | date | NN; CHECK end date is not before start date. |
| status | varchar(20) | NN, default `planned`; CHECK `planned`, `active`, `completed`, `cancelled`. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### tasks

Purpose: implementation work, assignment, deadline, and progress.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| requirement_id | uuid | FK to `requirements.id`, nullable. |
| sprint_id | uuid | FK to `sprints.id`, nullable. |
| title | varchar(250) | NN. |
| description | text | Nullable. |
| assigned_to_user_id | uuid | FK to `users.id`, nullable. |
| priority | varchar(20) | NN; CHECK `low`, `medium`, `high`, `critical`. |
| status | varchar(20) | NN, default `todo`; CHECK `todo`, `in_progress`, `in_review`, `completed`, `blocked`. |
| due_date | date | Nullable. |
| created_by_user_id | uuid | FK to `users.id`, NN. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### task_comments

Purpose: collaboration comments required by TASK-04.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| task_id | uuid | FK to `tasks.id`, NN. |
| author_user_id | uuid | FK to `users.id`, NN. |
| body | text | NN. |
| created_at | timestamptz | NN, default `now()`. |
| updated_at | timestamptz | NN, default `now()`. |

### bugs

Purpose: reported defects, assignments, status, and associations.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| requirement_id | uuid | FK to `requirements.id`, nullable. |
| task_id | uuid | FK to `tasks.id`, nullable. |
| title | varchar(250) | NN. |
| description | text | NN. |
| severity | varchar(20) | NN; CHECK `low`, `medium`, `high`, `critical`. |
| status | varchar(20) | NN, default `open`; CHECK `open`, `in_progress`, `resolved`, `closed`, `reopened`. |
| assigned_to_user_id | uuid | FK to `users.id`, nullable. |
| reported_by_user_id | uuid | FK to `users.id`, NN. |
| created_at | timestamptz | NN, default `now()`. |
| resolved_at | timestamptz | Nullable. |
| updated_at | timestamptz | NN, default `now()`. |

### test_cases

Purpose: validation artifacts linked to requirements.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| requirement_id | uuid | FK to `requirements.id`, NN. |
| title | varchar(250) | NN. |
| preconditions | text | Nullable. |
| test_steps | text | NN. |
| expected_result | text | NN. |
| actual_result | text | Nullable. |
| status | varchar(20) | NN, default `not_run`; CHECK `not_run`, `passed`, `failed`, `blocked`. |
| created_by_user_id | uuid | FK to `users.id`, NN. |
| executed_by_user_id | uuid | FK to `users.id`, nullable. |
| created_at | timestamptz | NN, default `now()`. |
| executed_at | timestamptz | Nullable. |
| updated_at | timestamptz | NN, default `now()`. |

### traceability_links

Purpose: project-scoped typed relationships used by the traceability graph and RCIA.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| source_artifact_type | varchar(30) | NN; CHECK supported types `requirement`, `task`, `bug`, `test_case`, `sprint`, `user`. |
| source_artifact_id | uuid | NN; logical typed reference. |
| target_artifact_type | varchar(30) | NN; same supported-type CHECK. |
| target_artifact_id | uuid | NN; logical typed reference. |
| relationship_type | varchar(30) | NN; CHECK `implements`, `validates`, `affects`, `belongs_to`, `associated_with`. |
| created_by_user_id | uuid | FK to `users.id`, NN. |
| created_at | timestamptz | NN, default `now()`. |

UNIQUE: `(project_id, source_artifact_type, source_artifact_id, target_artifact_type, target_artifact_id, relationship_type)`. CHECK: source and target cannot be identical. The typed IDs cannot use ordinary SQL foreign keys because one column can reference different tables; the Phase 5 traceability service verifies entity existence, supported relationship direction, and same-project ownership before persistence. This remains an explicit polymorphic-reference limitation at the database layer.

### impact_analyses

Purpose: persisted RCIA invocation metadata and summary.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| requirement_id | uuid | FK to `requirements.id`, NN. |
| change_request_id | uuid | FK to `requirement_change_requests.id`, nullable. |
| initiated_by_user_id | uuid | FK to `users.id`, NN. |
| status | varchar(20) | NN, default `pending`; CHECK `pending`, `completed`, `failed`. |
| summary | text | Nullable. |
| started_at | timestamptz | NN, default `now()`. |
| completed_at | timestamptz | Nullable. |

### impact_analysis_results

Purpose: affected-artifact rows from an RCIA run.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| impact_analysis_id | uuid | FK to `impact_analyses.id`, NN, ON DELETE CASCADE. |
| artifact_type | varchar(30) | NN; CHECK `task`, `bug`, `test_case`, `sprint`, `user`. |
| artifact_id | uuid | NN; logical typed reference. |
| impact_category | varchar(20) | NN, default `direct`; CHECK `direct`, `indirect`. |
| relationship_path | jsonb | Nullable; planned traceability traversal path, not arbitrary business data. |
| created_at | timestamptz | NN, default `now()`. |

UNIQUE: `(impact_analysis_id, artifact_type, artifact_id)`. The typed artifact ID has the same later validation requirement as `traceability_links`.

### reports

Purpose: generated-report metadata or an object/file reference. PDF binary storage is intentionally excluded.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, NN. |
| report_type | varchar(30) | NN; CHECK `project_progress`, `requirement_coverage`, `rcia`. |
| generated_by_user_id | uuid | FK to `users.id`, NN. |
| impact_analysis_id | uuid | FK to `impact_analyses.id`, nullable. |
| storage_reference | text | NN; not a local server filesystem path in production. |
| generated_at | timestamptz | NN, default `now()`. |

### audit_logs

Purpose: append-only audit metadata for project artifacts and administrative actions.

| Column | Type | Rules |
| --- | --- | --- |
| id | uuid | PK, NN, default UUID. |
| project_id | uuid | FK to `projects.id`, nullable for platform-level activity. |
| actor_user_id | uuid | FK to `users.id`, nullable for system activity. |
| entity_type | varchar(40) | NN. |
| entity_id | uuid | Nullable; logical entity reference. |
| action | varchar(40) | NN; CHECK `create`, `update`, `delete`, `status_change`, `role_change`, `impact_analysis`, `report_generate`. |
| before_data | jsonb | Nullable; do not store passwords, tokens, or credential data. |
| after_data | jsonb | Nullable; same exclusion. |
| occurred_at | timestamptz | NN, default `now()`. |

## 7. Relationships and Cardinality

| Relationship | Cardinality | Handling |
| --- | --- | --- |
| Users to roles | Many-to-many | `user_roles`. |
| Users to projects | Many-to-many | `project_members`. |
| Project to milestones, requirements, sprints, tasks, bugs, test cases, reports | One-to-many | Each child has `project_id`. |
| Requirement to change requests | One-to-many | `requirement_change_requests.requirement_id`. |
| Requirement to tasks | One-to-many, optional from task | `tasks.requirement_id`. |
| Sprint to tasks | One-to-many, optional from task | `tasks.sprint_id`. |
| Task to comments | One-to-many | `task_comments.task_id`. |
| Requirement/task to bugs | One-to-many, optional from bug | `bugs.requirement_id`, `bugs.task_id`. |
| Requirement to test cases | One-to-many | `test_cases.requirement_id`. |
| Supported traceable artifacts | Many-to-many | `traceability_links` generic typed junction. |
| Requirement/change request to RCIA runs | One-to-many | `impact_analyses`. |
| RCIA run to results | One-to-many | `impact_analysis_results`. |

There are no required one-to-one relationships in the baseline SRS. The direct nullable foreign keys are convenient primary associations; the traceability junction supports additional relationships.

## 8. Indexing Strategy

Primary keys and UNIQUE constraints create indexes automatically. Add indexes on all foreign keys that will be used for joins: project ownership columns; `requirements.project_id`; task requirement/sprint/assignee columns; bug requirement/task/assignee columns; `test_cases.requirement_id`; and all reporting/audit/RCIA parents.

Use these composite indexes: `requirements(project_id, status)`, `tasks(project_id, status)`, `tasks(sprint_id, status)`, `bugs(project_id, status, severity)`, `traceability_links(project_id, source_artifact_type, source_artifact_id)`, `traceability_links(project_id, target_artifact_type, target_artifact_id)`, and `impact_analysis_results(impact_analysis_id, artifact_type)`. Indexes should be measured with PostgreSQL query plans before adding speculative indexes.

## 9. Data Integrity and Constraints

Primary keys, foreign keys, unique keys, NOT NULL requirements, status/type checks, non-self traceability links, positive requirement versions, and valid date ranges are expressed in the draft schema. Application or a later PostgreSQL constraint trigger must additionally validate that cross-table typed references exist, share the declared `project_id`, and that a task's linked sprint/requirement belongs to its project. These cross-table rules cannot be fully represented by independent single-column foreign keys.

## 10. Audit and Timestamp Strategy

`created_at` is immutable; `updated_at` is maintained by application code or a later database trigger. Business artifacts carry timestamps appropriate to their lifecycle (for example `resolved_at`, `executed_at`, and `completed_at`). `audit_logs` is append-only by policy and stores minimal before/after JSON metadata. Exact audit coverage, retention period, and whether database triggers create audit records require architect approval.

## 11. Security and Sensitive Data Considerations

Only `users.password_hash` may contain password-derived material; plaintext passwords, JWTs, reset tokens, API keys, and database credentials must never be stored. Enforce least-privilege database accounts in Phase 2 or later, use TLS in deployment, parameterized queries, encrypted backups where applicable, and role-based application authorization. Restrict audit payloads so they never capture password hashes or tokens. `storage_reference` must not expose secrets or unsafe local paths.

## 12. Normalization Considerations

The design targets third normal form: roles and memberships are junction tables; comments are separated from tasks; change requests and RCIA result rows are not repeated in requirements; report metadata is separated from project records; and derived analytics are not stored. `relationship_path`, audit snapshots, and change proposals use JSONB only for variable structured payloads whose schema is not specified by the SRS. Typed traceability references are a controlled polymorphic exception, documented with validation requirements.

## 13. Future Migration Strategy

Use version-controlled, forward-only migrations after a migration tool is selected during Phase 2. Each migration should have a reversible plan where practical, be tested on a clean database and a representative upgrade path, preserve data unless explicit approval permits otherwise, and include indexes/constraints with the relevant table change. Phase 1 does not select a migration framework, create migration files, or execute the draft SQL.

## 14. Open Questions and Assumptions

1. The SRS defines global roles but does not define whether a member can have multiple project-specific roles. This design permits one optional `project_role` label; the authorization model must decide whether to use it, replace it with a junction table, or rely solely on global `user_roles`.
2. The SRS lists tasks, bugs, test cases, sprints, and developers as traceable, but its detailed traceability requirements name requirements-to-task/bug/test-case/sprint links. Developer links remain supported by the plan's broader traceability scope; the architect should confirm permitted artifact pairs and relationship types.
3. The SRS does not define change-request lifecycle fields. This design assumes a change request is needed to preserve the reason and review status of a requirement change before RCIA; the final workflow and who can approve it require approval.
4. The SRS does not define a formal RCIA score or result-retention policy. This design stores direct/indirect result categories and a JSON relationship path, but does not store a score.
5. The SRS permits reports to be dynamically generated or referenced. This design stores a storage reference, not a PDF blob; final storage and retention need an architect decision.
6. The initial draft uses `pgcrypto` for UUID generation. The deployment environment must confirm extension availability, or UUIDs must be generated in the application layer.
