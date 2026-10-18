"""Create the approved Phase 5 traceability_links table."""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260922_03"
down_revision: Union[str, None] = "20260921_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "traceability_links",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_artifact_type", sa.String(length=30), nullable=False),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("target_artifact_type", sa.String(length=30), nullable=False),
        sa.Column("target_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')", name="ck_traceability_source_type"),
        sa.CheckConstraint("target_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')", name="ck_traceability_target_type"),
        sa.CheckConstraint("relationship_type IN ('implements', 'validates', 'affects', 'belongs_to', 'associated_with')", name="ck_traceability_relationship_type"),
        sa.CheckConstraint("source_artifact_type <> target_artifact_type OR source_artifact_id <> target_artifact_id", name="ck_traceability_not_self_link"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "source_artifact_type", "source_artifact_id", "target_artifact_type", "target_artifact_id", "relationship_type", name="uq_traceability_link"),
    )
    op.create_index("idx_traceability_source", "traceability_links", ["project_id", "source_artifact_type", "source_artifact_id"])
    op.create_index("idx_traceability_target", "traceability_links", ["project_id", "target_artifact_type", "target_artifact_id"])


def downgrade() -> None:
    op.drop_index("idx_traceability_target", table_name="traceability_links")
    op.drop_index("idx_traceability_source", table_name="traceability_links")
    op.drop_table("traceability_links")
