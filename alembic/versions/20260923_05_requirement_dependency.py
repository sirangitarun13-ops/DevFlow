"""Add requirement dependency relationship types.

Revision ID: 20260923_05
Revises: 20260922_04
Create Date: 2026-09-23

This migration adds support for requirement-to-requirement dependency relationships:
- depends_on: A depends on B. If B changes, A is potentially impacted.
- blocks: A blocks B. If A changes, B is potentially impacted.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_05"
down_revision: Union[str, None] = "20260922_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we're using SQLite (which doesn't support ALTER TABLE ... DROP CONSTRAINT)
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == "sqlite":
        # SQLite doesn't support DROP CONSTRAINT, so we recreate the table
        # Create new table with updated constraint
        op.execute("""
            CREATE TABLE traceability_links_new (
                id CHAR(32) NOT NULL,
                project_id CHAR(32) NOT NULL,
                source_artifact_type VARCHAR(30) NOT NULL,
                source_artifact_id CHAR(32) NOT NULL,
                target_artifact_type VARCHAR(30) NOT NULL,
                target_artifact_id CHAR(32) NOT NULL,
                relationship_type VARCHAR(30) NOT NULL,
                created_by_user_id CHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_traceability_source_type CHECK (source_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
                CONSTRAINT ck_traceability_target_type CHECK (target_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
                CONSTRAINT ck_traceability_relationship_type CHECK (relationship_type IN (
                    'implements', 'validates', 'affects', 'belongs_to', 'associated_with',
                    'depends_on', 'blocks'
                )),
                CONSTRAINT ck_traceability_not_self_link CHECK (source_artifact_type <> target_artifact_type OR source_artifact_id <> target_artifact_id),
                CONSTRAINT uq_traceability_link UNIQUE (project_id, source_artifact_type, source_artifact_id, target_artifact_type, target_artifact_id, relationship_type),
                FOREIGN KEY(project_id) REFERENCES projects (id),
                FOREIGN KEY(created_by_user_id) REFERENCES users (id)
            )
        """)
        # Copy data
        op.execute("""
            INSERT INTO traceability_links_new 
            SELECT id, project_id, source_artifact_type, source_artifact_id, 
                   target_artifact_type, target_artifact_id, relationship_type, 
                   created_by_user_id, created_at
            FROM traceability_links
        """)
        # Drop old table and rename
        op.execute("DROP TABLE traceability_links")
        op.execute("ALTER TABLE traceability_links_new RENAME TO traceability_links")
    else:
        # PostgreSQL and other databases support ALTER TABLE ... DROP CONSTRAINT
        op.execute("""
            ALTER TABLE traceability_links
            DROP CONSTRAINT ck_traceability_relationship_type
        """)
        op.execute("""
            ALTER TABLE traceability_links
            ADD CONSTRAINT ck_traceability_relationship_type
            CHECK (relationship_type IN (
                'implements', 'validates', 'affects', 'belongs_to', 'associated_with',
                'depends_on', 'blocks'
            ))
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == "sqlite":
        # SQLite: recreate table with old constraint
        op.execute("""
            CREATE TABLE traceability_links_new (
                id CHAR(32) NOT NULL,
                project_id CHAR(32) NOT NULL,
                source_artifact_type VARCHAR(30) NOT NULL,
                source_artifact_id CHAR(32) NOT NULL,
                target_artifact_type VARCHAR(30) NOT NULL,
                target_artifact_id CHAR(32) NOT NULL,
                relationship_type VARCHAR(30) NOT NULL,
                created_by_user_id CHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_traceability_source_type CHECK (source_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
                CONSTRAINT ck_traceability_target_type CHECK (target_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')),
                CONSTRAINT ck_traceability_relationship_type CHECK (relationship_type IN (
                    'implements', 'validates', 'affects', 'belongs_to', 'associated_with'
                )),
                CONSTRAINT ck_traceability_not_self_link CHECK (source_artifact_type <> target_artifact_type OR source_artifact_id <> target_artifact_id),
                CONSTRAINT uq_traceability_link UNIQUE (project_id, source_artifact_type, source_artifact_id, target_artifact_type, target_artifact_id, relationship_type),
                FOREIGN KEY(project_id) REFERENCES projects (id),
                FOREIGN KEY(created_by_user_id) REFERENCES users (id)
            )
        """)
        op.execute("""
            INSERT INTO traceability_links_new 
            SELECT id, project_id, source_artifact_type, source_artifact_id, 
                   target_artifact_type, target_artifact_id, relationship_type, 
                   created_by_user_id, created_at
            FROM traceability_links
        """)
        op.execute("DROP TABLE traceability_links")
        op.execute("ALTER TABLE traceability_links_new RENAME TO traceability_links")
    else:
        # PostgreSQL and other databases
        op.execute("""
            ALTER TABLE traceability_links
            DROP CONSTRAINT ck_traceability_relationship_type
        """)
        op.execute("""
            ALTER TABLE traceability_links
            ADD CONSTRAINT ck_traceability_relationship_type
            CHECK (relationship_type IN (
                'implements', 'validates', 'affects', 'belongs_to', 'associated_with'
            ))
        """)