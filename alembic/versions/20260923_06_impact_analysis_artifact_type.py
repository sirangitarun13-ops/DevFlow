"""Add requirement to impact_analysis_results artifact_type.

Revision ID: 20260923_06
Revises: 20260923_05
Create Date: 2026-09-23

This migration adds 'requirement' to the artifact_type check constraint
in the impact_analysis_results table to support requirement-to-requirement
dependency impact analysis.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_06"
down_revision: Union[str, None] = "20260923_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we're using SQLite (which doesn't support ALTER TABLE ... DROP CONSTRAINT)
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == "sqlite":
        # SQLite doesn't support DROP CONSTRAINT, so we recreate the table
        op.execute("""
            CREATE TABLE impact_analysis_results_new (
                id CHAR(32) NOT NULL,
                impact_analysis_id CHAR(32) NOT NULL,
                artifact_type VARCHAR(30) NOT NULL,
                artifact_id CHAR(32) NOT NULL,
                impact_category VARCHAR(20) NOT NULL,
                relationship_path JSON,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_impact_results_artifact_type CHECK (artifact_type IN (
                    'task', 'bug', 'test_case', 'sprint', 'user', 'requirement'
                )),
                CONSTRAINT ck_impact_results_category CHECK (impact_category IN ('direct', 'indirect')),
                CONSTRAINT uq_impact_analysis_artifact UNIQUE (impact_analysis_id, artifact_type, artifact_id),
                FOREIGN KEY(impact_analysis_id) REFERENCES impact_analyses (id) ON DELETE CASCADE
            )
        """)
        op.execute("""
            INSERT INTO impact_analysis_results_new 
            SELECT id, impact_analysis_id, artifact_type, artifact_id, impact_category, relationship_path, created_at
            FROM impact_analysis_results
        """)
        op.execute("DROP TABLE impact_analysis_results")
        op.execute("ALTER TABLE impact_analysis_results_new RENAME TO impact_analysis_results")
    else:
        # PostgreSQL and other databases support ALTER TABLE ... DROP CONSTRAINT
        op.execute("""
            ALTER TABLE impact_analysis_results
            DROP CONSTRAINT ck_impact_results_artifact_type
        """)
        op.execute("""
            ALTER TABLE impact_analysis_results
            ADD CONSTRAINT ck_impact_results_artifact_type
            CHECK (artifact_type IN (
                'task', 'bug', 'test_case', 'sprint', 'user', 'requirement'
            ))
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == "sqlite":
        # SQLite: recreate table with old constraint
        op.execute("""
            CREATE TABLE impact_analysis_results_new (
                id CHAR(32) NOT NULL,
                impact_analysis_id CHAR(32) NOT NULL,
                artifact_type VARCHAR(30) NOT NULL,
                artifact_id CHAR(32) NOT NULL,
                impact_category VARCHAR(20) NOT NULL,
                relationship_path JSON,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_impact_results_artifact_type CHECK (artifact_type IN (
                    'task', 'bug', 'test_case', 'sprint', 'user'
                )),
                CONSTRAINT ck_impact_results_category CHECK (impact_category IN ('direct', 'indirect')),
                CONSTRAINT uq_impact_analysis_artifact UNIQUE (impact_analysis_id, artifact_type, artifact_id),
                FOREIGN KEY(impact_analysis_id) REFERENCES impact_analyses (id) ON DELETE CASCADE
            )
        """)
        op.execute("""
            INSERT INTO impact_analysis_results_new 
            SELECT id, impact_analysis_id, artifact_type, artifact_id, impact_category, relationship_path, created_at
            FROM impact_analysis_results
        """)
        op.execute("DROP TABLE impact_analysis_results")
        op.execute("ALTER TABLE impact_analysis_results_new RENAME TO impact_analysis_results")
    else:
        # PostgreSQL and other databases
        op.execute("""
            ALTER TABLE impact_analysis_results
            DROP CONSTRAINT ck_impact_results_artifact_type
        """)
        op.execute("""
            ALTER TABLE impact_analysis_results
            ADD CONSTRAINT ck_impact_results_artifact_type
            CHECK (artifact_type IN (
                'task', 'bug', 'test_case', 'sprint', 'user'
            ))
        """)
