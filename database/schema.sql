-- DevFlow Phase 1 draft PostgreSQL schema.
-- Design only: do not execute this file against a database during Phase 1.
-- No credentials, seed data, application logic, routes, or authentication logic are included.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(32) NOT NULL UNIQUE CHECK (code IN ('admin', 'project_manager', 'team_lead', 'developer', 'tester', 'client')),
    name varchar(100) NOT NULL UNIQUE,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name varchar(150) NOT NULL,
    email varchar(254) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    account_status varchar(20) NOT NULL DEFAULT 'active' CHECK (account_status IN ('active', 'inactive', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_roles (
    user_id uuid NOT NULL REFERENCES users(id),
    role_id uuid NOT NULL REFERENCES roles(id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    assigned_by_user_id uuid REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(200) NOT NULL,
    description text,
    status varchar(20) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'on_hold', 'completed', 'cancelled')),
    start_date date,
    end_date date,
    created_by_user_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE project_members (
    project_id uuid NOT NULL REFERENCES projects(id),
    user_id uuid NOT NULL REFERENCES users(id),
    project_role varchar(32) CHECK (project_role IS NULL OR project_role IN ('admin', 'project_manager', 'team_lead', 'developer', 'tester', 'client')),
    joined_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE milestones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    name varchar(200) NOT NULL,
    description text,
    target_date date,
    status varchar(20) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, name)
);

CREATE TABLE requirements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    requirement_key varchar(50) NOT NULL,
    title varchar(250) NOT NULL,
    description text NOT NULL,
    requirement_type varchar(20) NOT NULL CHECK (requirement_type IN ('functional', 'non_functional')),
    priority varchar(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by_user_id uuid NOT NULL REFERENCES users(id),
    updated_by_user_id uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, requirement_key)
);

CREATE TABLE requirement_change_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id uuid NOT NULL REFERENCES requirements(id),
    requested_by_user_id uuid NOT NULL REFERENCES users(id),
    reviewed_by_user_id uuid REFERENCES users(id),
    change_summary text NOT NULL,
    proposed_description text,
    proposed_priority varchar(20) CHECK (proposed_priority IS NULL OR proposed_priority IN ('low', 'medium', 'high', 'critical')),
    proposed_status varchar(20) CHECK (proposed_status IS NULL OR proposed_status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')),
    status varchar(20) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'under_review', 'approved', 'rejected', 'implemented', 'withdrawn')),
    reviewed_at timestamptz,
    implemented_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sprints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    name varchar(150) NOT NULL,
    goal text,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'completed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date),
    UNIQUE (project_id, name)
);

CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    requirement_id uuid REFERENCES requirements(id),
    sprint_id uuid REFERENCES sprints(id),
    title varchar(250) NOT NULL,
    description text,
    assigned_to_user_id uuid REFERENCES users(id),
    priority varchar(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status varchar(20) NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'in_review', 'completed', 'blocked')),
    due_date date,
    created_by_user_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE task_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id),
    author_user_id uuid NOT NULL REFERENCES users(id),
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bugs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    requirement_id uuid REFERENCES requirements(id),
    task_id uuid REFERENCES tasks(id),
    title varchar(250) NOT NULL,
    description text NOT NULL,
    severity varchar(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status varchar(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed', 'reopened')),
    assigned_to_user_id uuid REFERENCES users(id),
    reported_by_user_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE test_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    requirement_id uuid NOT NULL REFERENCES requirements(id),
    title varchar(250) NOT NULL,
    preconditions text,
    test_steps text NOT NULL,
    expected_result text NOT NULL,
    actual_result text,
    status varchar(20) NOT NULL DEFAULT 'not_run' CHECK (status IN ('not_run', 'passed', 'failed', 'blocked')),
    created_by_user_id uuid NOT NULL REFERENCES users(id),
    executed_by_user_id uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    executed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE traceability_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_artifact_type varchar(30) NOT NULL CHECK (source_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
    source_artifact_id uuid NOT NULL,
    target_artifact_type varchar(30) NOT NULL CHECK (target_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
    target_artifact_id uuid NOT NULL,
    relationship_type varchar(30) NOT NULL CHECK (relationship_type IN ('implements', 'validates', 'affects', 'belongs_to', 'associated_with')),
    created_by_user_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_artifact_type <> target_artifact_type OR source_artifact_id <> target_artifact_id),
    UNIQUE (project_id, source_artifact_type, source_artifact_id, target_artifact_type, target_artifact_id, relationship_type)
);

CREATE TABLE impact_analyses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    requirement_id uuid NOT NULL REFERENCES requirements(id),
    change_request_id uuid REFERENCES requirement_change_requests(id),
    initiated_by_user_id uuid NOT NULL REFERENCES users(id),
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    summary text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE impact_analysis_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    impact_analysis_id uuid NOT NULL REFERENCES impact_analyses(id) ON DELETE CASCADE,
    artifact_type varchar(30) NOT NULL CHECK (artifact_type IN ('task', 'bug', 'test_case', 'sprint', 'user')),
    artifact_id uuid NOT NULL,
    impact_category varchar(20) NOT NULL DEFAULT 'direct' CHECK (impact_category IN ('direct', 'indirect')),
    relationship_path jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (impact_analysis_id, artifact_type, artifact_id)
);

CREATE TABLE reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    report_type varchar(30) NOT NULL CHECK (report_type IN ('project_progress', 'requirement_coverage', 'rcia')),
    generated_by_user_id uuid NOT NULL REFERENCES users(id),
    impact_analysis_id uuid REFERENCES impact_analyses(id),
    storage_reference text NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id),
    actor_user_id uuid REFERENCES users(id),
    entity_type varchar(40) NOT NULL,
    entity_id uuid,
    action varchar(40) NOT NULL CHECK (action IN ('create', 'update', 'delete', 'status_change', 'role_change', 'impact_analysis', 'report_generate')),
    before_data jsonb,
    after_data jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_project_members_user_id ON project_members(user_id);
CREATE INDEX idx_milestones_project_id ON milestones(project_id);
CREATE INDEX idx_requirements_project_status ON requirements(project_id, status);
CREATE INDEX idx_requirement_change_requests_requirement_id ON requirement_change_requests(requirement_id);
CREATE INDEX idx_sprints_project_id ON sprints(project_id);
CREATE INDEX idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX idx_tasks_requirement_id ON tasks(requirement_id);
CREATE INDEX idx_tasks_sprint_status ON tasks(sprint_id, status);
CREATE INDEX idx_tasks_assigned_to_user_id ON tasks(assigned_to_user_id);
CREATE INDEX idx_task_comments_task_id ON task_comments(task_id);
CREATE INDEX idx_bugs_project_status_severity ON bugs(project_id, status, severity);
CREATE INDEX idx_bugs_requirement_id ON bugs(requirement_id);
CREATE INDEX idx_bugs_task_id ON bugs(task_id);
CREATE INDEX idx_bugs_assigned_to_user_id ON bugs(assigned_to_user_id);
CREATE INDEX idx_test_cases_requirement_id ON test_cases(requirement_id);
CREATE INDEX idx_traceability_source ON traceability_links(project_id, source_artifact_type, source_artifact_id);
CREATE INDEX idx_traceability_target ON traceability_links(project_id, target_artifact_type, target_artifact_id);
CREATE INDEX idx_impact_analyses_requirement_id ON impact_analyses(requirement_id);
CREATE INDEX idx_impact_analysis_results_analysis_type ON impact_analysis_results(impact_analysis_id, artifact_type);
CREATE INDEX idx_reports_project_id ON reports(project_id);
CREATE INDEX idx_audit_logs_project_occurred_at ON audit_logs(project_id, occurred_at);

-- Deferred integrity: typed artifact IDs in traceability_links and
-- impact_analysis_results need an approved constraint-trigger or service-layer
-- validator to verify entity existence and project ownership.
