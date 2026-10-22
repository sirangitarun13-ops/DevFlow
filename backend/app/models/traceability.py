"""Polymorphic traceability links used as Phase 5 input for future RCIA."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TraceabilityLink(Base):
    """A project-scoped typed relationship between two SDLC artifacts.

    Artifact IDs are intentionally polymorphic to match the approved schema;
    service-layer validation verifies existence and project ownership.
    """

    __tablename__ = "traceability_links"
    __table_args__ = (
        CheckConstraint(
            "source_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')",
            name="ck_traceability_source_type",
        ),
        CheckConstraint(
            "target_artifact_type IN ('requirement', 'task', 'bug', 'test_case', 'sprint', 'user')",
            name="ck_traceability_target_type",
        ),
        CheckConstraint(
            "relationship_type IN ('implements', 'validates', 'affects', 'belongs_to', 'associated_with', 'depends_on', 'blocks')",
            name="ck_traceability_relationship_type",
        ),
        CheckConstraint(
            "source_artifact_type <> target_artifact_type OR source_artifact_id <> target_artifact_id",
            name="ck_traceability_not_self_link",
        ),
        UniqueConstraint(
            "project_id",
            "source_artifact_type",
            "source_artifact_id",
            "target_artifact_type",
            "target_artifact_id",
            "relationship_type",
            name="uq_traceability_link",
        ),
        Index("idx_traceability_source", "project_id", "source_artifact_type", "source_artifact_id"),
        Index("idx_traceability_target", "project_id", "target_artifact_type", "target_artifact_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    source_artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_artifact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_artifact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
