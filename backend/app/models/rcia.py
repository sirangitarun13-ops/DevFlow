"""ORM models for change requests and deterministic RCIA results."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RequirementChangeRequest(Base):
    __tablename__ = "requirement_change_requests"
    __table_args__ = (
        CheckConstraint("status IN ('submitted', 'under_review', 'approved', 'rejected', 'implemented', 'withdrawn')", name="ck_change_requests_status"),
        CheckConstraint("proposed_priority IS NULL OR proposed_priority IN ('low', 'medium', 'high', 'critical')", name="ck_change_requests_priority"),
        CheckConstraint("proposed_status IS NULL OR proposed_status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')", name="ck_change_requests_requirement_status"),
        Index("idx_requirement_change_requests_requirement_id", "requirement_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id"), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_description: Mapped[str] = mapped_column(Text, nullable=True)
    proposed_priority: Mapped[str] = mapped_column(String(20), nullable=True)
    proposed_status: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    implemented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'completed', 'failed')", name="ck_impact_analyses_status"),
        Index("idx_impact_analyses_requirement_id", "requirement_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id"), nullable=False)
    change_request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirement_change_requests.id"), nullable=True)
    initiated_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    results: Mapped[list["ImpactAnalysisResult"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class ImpactAnalysisResult(Base):
    __tablename__ = "impact_analysis_results"
    __table_args__ = (
        CheckConstraint("artifact_type IN ('task', 'bug', 'test_case', 'sprint', 'user')", name="ck_impact_results_artifact_type"),
        CheckConstraint("impact_category IN ('direct', 'indirect')", name="ck_impact_results_category"),
        UniqueConstraint("impact_analysis_id", "artifact_type", "artifact_id", name="uq_impact_analysis_artifact"),
        Index("idx_impact_analysis_results_analysis_type", "impact_analysis_id", "artifact_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    impact_analysis_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("impact_analyses.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    impact_category: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")
    relationship_path: Mapped[list] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    analysis: Mapped[ImpactAnalysis] = relationship(back_populates="results")

    @property
    def explanation(self) -> str:
        if not self.relationship_path:
            return "No traceability path recorded."
        relationships = " -> ".join(step.get("relationship_type", "traceability") for step in self.relationship_path)
        return f"{self.artifact_type} {self.artifact_id} is impacted through {relationships}."
