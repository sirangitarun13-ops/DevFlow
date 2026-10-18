"""API schemas for Phase 5 traceability links."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


ArtifactType = Literal["requirement", "task", "bug", "test_case", "sprint", "user"]
RelationshipType = Literal["implements", "validates", "affects", "belongs_to", "associated_with"]


class TraceabilityLinkCreate(BaseModel):
    source_artifact_type: ArtifactType
    source_artifact_id: UUID
    target_artifact_type: ArtifactType
    target_artifact_id: UUID
    relationship_type: RelationshipType


class TraceabilityLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_artifact_type: str
    source_artifact_id: UUID
    target_artifact_type: str
    target_artifact_id: UUID
    relationship_type: str
    created_by_user_id: UUID
    created_at: datetime
