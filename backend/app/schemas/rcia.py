"""Pydantic schemas for change requests and deterministic RCIA results."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ChangeRequestStatus = Literal["submitted", "under_review", "approved", "rejected", "implemented", "withdrawn"]
Priority = Literal["low", "medium", "high", "critical"]
RequirementStatus = Literal["draft", "proposed", "approved", "in_progress", "completed", "rejected"]


class ChangeRequestCreate(BaseModel):
    change_summary: str = Field(min_length=1)
    proposed_description: str | None = None
    proposed_priority: Priority | None = None
    proposed_status: RequirementStatus | None = None


class ChangeRequestUpdate(BaseModel):
    status: ChangeRequestStatus


class ChangeRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requirement_id: UUID
    requested_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    change_summary: str
    proposed_description: str | None
    proposed_priority: str | None
    proposed_status: str | None
    status: str
    reviewed_at: datetime | None
    implemented_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImpactAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    requirement_id: UUID
    change_request_id: UUID | None
    initiated_by_user_id: UUID
    status: str
    summary: str | None
    started_at: datetime
    completed_at: datetime | None


class ImpactAnalysisResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    impact_analysis_id: UUID
    artifact_type: str
    artifact_id: UUID
    artifact_key: str | None = None
    artifact_title: str | None = None
    impact_category: str
    relationship_path: list | None
    explanation: str
    created_at: datetime
