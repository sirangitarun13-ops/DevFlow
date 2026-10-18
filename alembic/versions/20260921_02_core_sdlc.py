"""Create Phase 4 core SDLC tables.

Revision ID: 20260921_02
Revises: 20260921_01
Create Date: 2026-09-21

This migration has not been applied in this workspace.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260921_02"
down_revision: Union[str, None] = "20260921_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def id_column():
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("projects", id_column(), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("status", sa.String(20), server_default="planned", nullable=False), sa.Column("start_date", sa.Date()), sa.Column("end_date", sa.Date()), sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), *timestamps(), sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_projects_dates"), sa.PrimaryKeyConstraint("id"))
    op.create_table("project_members", sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("project_role", sa.String(32)), sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("project_role IS NULL OR project_role IN ('admin', 'project_manager', 'team_lead', 'developer', 'tester', 'client')", name="ck_project_members_role"), sa.PrimaryKeyConstraint("project_id", "user_id"))
    op.create_table("milestones", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("target_date", sa.Date()), sa.Column("status", sa.String(20), server_default="planned", nullable=False), *timestamps(), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "name"))
    op.create_table("requirements", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("requirement_key", sa.String(50), nullable=False), sa.Column("title", sa.String(250), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("requirement_type", sa.String(20), nullable=False), sa.Column("priority", sa.String(20), nullable=False), sa.Column("status", sa.String(20), server_default="draft", nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False), sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")), *timestamps(), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "requirement_key"))
    op.create_table("sprints", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("name", sa.String(150), nullable=False), sa.Column("goal", sa.Text()), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), sa.Column("status", sa.String(20), server_default="planned", nullable=False), *timestamps(), sa.CheckConstraint("end_date >= start_date", name="ck_sprints_dates"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "name"))
    op.create_table("tasks", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("requirement_id", sa.Uuid(), sa.ForeignKey("requirements.id")), sa.Column("sprint_id", sa.Uuid(), sa.ForeignKey("sprints.id")), sa.Column("title", sa.String(250), nullable=False), sa.Column("description", sa.Text()), sa.Column("assigned_to_user_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("priority", sa.String(20), nullable=False), sa.Column("status", sa.String(20), server_default="todo", nullable=False), sa.Column("due_date", sa.Date()), sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), *timestamps(), sa.PrimaryKeyConstraint("id"))
    op.create_table("task_comments", id_column(), sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("body", sa.Text(), nullable=False), *timestamps(), sa.PrimaryKeyConstraint("id"))
    op.create_table("bugs", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("requirement_id", sa.Uuid(), sa.ForeignKey("requirements.id")), sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id")), sa.Column("title", sa.String(250), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("severity", sa.String(20), nullable=False), sa.Column("status", sa.String(20), server_default="open", nullable=False), sa.Column("assigned_to_user_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("reported_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_table("test_cases", id_column(), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("requirement_id", sa.Uuid(), sa.ForeignKey("requirements.id"), nullable=False), sa.Column("title", sa.String(250), nullable=False), sa.Column("preconditions", sa.Text()), sa.Column("test_steps", sa.Text(), nullable=False), sa.Column("expected_result", sa.Text(), nullable=False), sa.Column("actual_result", sa.Text()), sa.Column("status", sa.String(20), server_default="not_run", nullable=False), sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("executed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("executed_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.PrimaryKeyConstraint("id"))
    for name, table, condition in (
        ("ck_projects_status", "projects", "status IN ('planned', 'active', 'on_hold', 'completed', 'cancelled')"),
        ("ck_milestones_status", "milestones", "status IN ('planned', 'in_progress', 'completed', 'cancelled')"),
        ("ck_requirements_type", "requirements", "requirement_type IN ('functional', 'non_functional')"),
        ("ck_requirements_priority", "requirements", "priority IN ('low', 'medium', 'high', 'critical')"),
        ("ck_requirements_status", "requirements", "status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')"),
        ("ck_requirements_version", "requirements", "version > 0"),
        ("ck_sprints_status", "sprints", "status IN ('planned', 'active', 'completed', 'cancelled')"),
        ("ck_tasks_priority", "tasks", "priority IN ('low', 'medium', 'high', 'critical')"),
        ("ck_tasks_status", "tasks", "status IN ('todo', 'in_progress', 'in_review', 'completed', 'blocked')"),
        ("ck_bugs_severity", "bugs", "severity IN ('low', 'medium', 'high', 'critical')"),
        ("ck_bugs_status", "bugs", "status IN ('open', 'in_progress', 'resolved', 'closed', 'reopened')"),
        ("ck_test_cases_status", "test_cases", "status IN ('not_run', 'passed', 'failed', 'blocked')"),
    ):
        op.create_check_constraint(name, table, condition)
    for name, table, columns in (
        ("idx_project_members_user_id", "project_members", ["user_id"]), ("idx_milestones_project_id", "milestones", ["project_id"]),
        ("idx_requirements_project_status", "requirements", ["project_id", "status"]), ("idx_sprints_project_id", "sprints", ["project_id"]),
        ("idx_tasks_project_status", "tasks", ["project_id", "status"]), ("idx_tasks_requirement_id", "tasks", ["requirement_id"]),
        ("idx_tasks_sprint_status", "tasks", ["sprint_id", "status"]), ("idx_tasks_assigned_to_user_id", "tasks", ["assigned_to_user_id"]),
        ("idx_task_comments_task_id", "task_comments", ["task_id"]), ("idx_bugs_project_status_severity", "bugs", ["project_id", "status", "severity"]),
        ("idx_bugs_requirement_id", "bugs", ["requirement_id"]), ("idx_bugs_task_id", "bugs", ["task_id"]),
        ("idx_bugs_assigned_to_user_id", "bugs", ["assigned_to_user_id"]), ("idx_test_cases_requirement_id", "test_cases", ["requirement_id"]),
    ):
        op.create_index(name, table, columns)


def downgrade() -> None:
    for table in ("test_cases", "bugs", "task_comments", "tasks", "sprints", "requirements", "milestones", "project_members", "projects"):
        op.drop_table(table)
