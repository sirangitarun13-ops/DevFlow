"""Create approved requirement-change and RCIA result tables."""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260922_04"
down_revision: Union[str, None] = "20260922_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_change_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("proposed_description", sa.Text(), nullable=True),
        sa.Column("proposed_priority", sa.String(length=20), nullable=True),
        sa.Column("proposed_status", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="submitted", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('submitted', 'under_review', 'approved', 'rejected', 'implemented', 'withdrawn')", name="ck_change_requests_status"),
        sa.CheckConstraint("proposed_priority IS NULL OR proposed_priority IN ('low', 'medium', 'high', 'critical')", name="ck_change_requests_priority"),
        sa.CheckConstraint("proposed_status IS NULL OR proposed_status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')", name="ck_change_requests_requirement_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_requirement_change_requests_requirement_id", "requirement_change_requests", ["requirement_id"])
    op.create_table(
        "impact_analyses",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("change_request_id", sa.Uuid(), sa.ForeignKey("requirement_change_requests.id"), nullable=True),
        sa.Column("initiated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed')", name="ck_impact_analyses_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_impact_analyses_requirement_id", "impact_analyses", ["requirement_id"])
    op.create_table(
        "impact_analysis_results",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("impact_analysis_id", sa.Uuid(), sa.ForeignKey("impact_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(length=30), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("impact_category", sa.String(length=20), server_default="direct", nullable=False),
        sa.Column("relationship_path", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("artifact_type IN ('task', 'bug', 'test_case', 'sprint', 'user')", name="ck_impact_results_artifact_type"),
        sa.CheckConstraint("impact_category IN ('direct', 'indirect')", name="ck_impact_results_category"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("impact_analysis_id", "artifact_type", "artifact_id", name="uq_impact_analysis_artifact"),
    )
    op.create_index("idx_impact_analysis_results_analysis_type", "impact_analysis_results", ["impact_analysis_id", "artifact_type"])


def downgrade() -> None:
    op.drop_index("idx_impact_analysis_results_analysis_type", table_name="impact_analysis_results")
    op.drop_table("impact_analysis_results")
    op.drop_index("idx_impact_analyses_requirement_id", table_name="impact_analyses")
    op.drop_table("impact_analyses")
    op.drop_index("idx_requirement_change_requests_requirement_id", table_name="requirement_change_requests")
    op.drop_table("requirement_change_requests")
