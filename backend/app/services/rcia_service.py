"""Deterministic, traceability-driven Requirement Change Impact Analysis."""

from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.core import Requirement
from backend.app.models.rcia import ImpactAnalysis, ImpactAnalysisResult, RequirementChangeRequest
from backend.app.models.traceability import TraceabilityLink
from backend.app.services.traceability_service import artifact_belongs_to_project


CHANGE_REQUEST_STATUSES = {"submitted", "under_review", "approved", "rejected", "implemented", "withdrawn"}
IMPACT_PROPAGATING_RELATIONSHIPS = {"implements", "validates", "affects"}
RESULT_ARTIFACT_TYPES = {"task", "bug", "test_case", "sprint", "user"}


def _requirement(db: Session, project_id: UUID, requirement_id: UUID) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise ValueError("Requirement not found")
    if requirement.project_id != project_id:
        raise ValueError("Requirement must belong to the project")
    return requirement


def create_change_request(db: Session, project_id: UUID, requirement_id: UUID, requested_by_user_id: UUID, values: dict) -> RequirementChangeRequest:
    _requirement(db, project_id, requirement_id)
    record = RequirementChangeRequest(requirement_id=requirement_id, requested_by_user_id=requested_by_user_id, **values)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_change_requests(db: Session, project_id: UUID, limit: int, offset: int):
    query = (
        select(RequirementChangeRequest)
        .join(Requirement, Requirement.id == RequirementChangeRequest.requirement_id)
        .where(Requirement.project_id == project_id)
        .order_by(RequirementChangeRequest.created_at, RequirementChangeRequest.id)
    )
    return db.scalars(query.limit(limit).offset(offset)).all()


def get_change_request(db: Session, project_id: UUID, change_request_id: UUID) -> RequirementChangeRequest:
    record = db.get(RequirementChangeRequest, change_request_id)
    if record is None:
        raise ValueError("Change request not found")
    _requirement(db, project_id, record.requirement_id)
    return record


def update_change_request(db: Session, project_id: UUID, change_request_id: UUID, reviewer_user_id: UUID, status: str) -> RequirementChangeRequest:
    if status not in CHANGE_REQUEST_STATUSES:
        raise ValueError("Invalid change-request status")
    record = get_change_request(db, project_id, change_request_id)
    record.status = status
    record.reviewed_by_user_id = reviewer_user_id
    record.reviewed_at = datetime.now(timezone.utc)
    if status == "implemented":
        record.implemented_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def _link_step(link: TraceabilityLink) -> dict[str, str]:
    return {
        "link_id": str(link.id),
        "source_artifact_type": link.source_artifact_type,
        "source_artifact_id": str(link.source_artifact_id),
        "target_artifact_type": link.target_artifact_type,
        "target_artifact_id": str(link.target_artifact_id),
        "relationship_type": link.relationship_type,
    }


def traverse_impacts(db: Session, project_id: UUID, requirement_id: UUID) -> list[dict]:
    """Traverse outgoing impact-propagating links deterministically."""

    queue = deque([("requirement", requirement_id, [])])
    visited: set[tuple[str, UUID]] = {("requirement", requirement_id)}
    impacts: dict[tuple[str, UUID], dict] = {}
    while queue:
        current_type, current_id, path = queue.popleft()
        links = db.scalars(
            select(TraceabilityLink)
            .where(
                TraceabilityLink.project_id == project_id,
                TraceabilityLink.source_artifact_type == current_type,
                TraceabilityLink.source_artifact_id == current_id,
                TraceabilityLink.relationship_type.in_(IMPACT_PROPAGATING_RELATIONSHIPS),
            )
            .order_by(TraceabilityLink.relationship_type, TraceabilityLink.target_artifact_type, TraceabilityLink.target_artifact_id, TraceabilityLink.id)
        ).all()
        for link in links:
            if not artifact_belongs_to_project(db, link.target_artifact_type, link.target_artifact_id, project_id):
                continue
            target = (link.target_artifact_type, link.target_artifact_id)
            new_path = path + [_link_step(link)]
            if target[0] in RESULT_ARTIFACT_TYPES and target not in impacts:
                impacts[target] = {
                    "artifact_type": target[0],
                    "artifact_id": target[1],
                    "impact_category": "direct" if len(new_path) == 1 else "indirect",
                    "relationship_path": new_path,
                }
            if target not in visited:
                visited.add(target)
                queue.append((target[0], target[1], new_path))
    return sorted(impacts.values(), key=lambda item: (item["artifact_type"], str(item["artifact_id"])))


def run_analysis(db: Session, project_id: UUID, change_request_id: UUID, initiated_by_user_id: UUID) -> ImpactAnalysis:
    change_request = get_change_request(db, project_id, change_request_id)
    analysis = ImpactAnalysis(
        project_id=project_id,
        requirement_id=change_request.requirement_id,
        change_request_id=change_request.id,
        initiated_by_user_id=initiated_by_user_id,
        status="pending",
    )
    db.add(analysis)
    db.flush()
    impacts = traverse_impacts(db, project_id, change_request.requirement_id)
    for impact in impacts:
        db.add(ImpactAnalysisResult(impact_analysis_id=analysis.id, **impact))
    analysis.status = "completed"
    analysis.summary = f"Deterministic traceability analysis identified {len(impacts)} impacted artifact(s)."
    analysis.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    return analysis


def get_analysis(db: Session, project_id: UUID, analysis_id: UUID) -> ImpactAnalysis:
    record = db.get(ImpactAnalysis, analysis_id)
    if record is None or record.project_id != project_id:
        raise ValueError("Impact analysis not found")
    return record


def list_results(db: Session, project_id: UUID, analysis_id: UUID):
    get_analysis(db, project_id, analysis_id)
    return db.scalars(
        select(ImpactAnalysisResult)
        .where(ImpactAnalysisResult.impact_analysis_id == analysis_id)
        .order_by(ImpactAnalysisResult.artifact_type, ImpactAnalysisResult.artifact_id)
    ).all()
