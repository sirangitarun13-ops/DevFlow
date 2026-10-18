"""Validation, persistence, and lookup services for Phase 5 traceability."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.auth import User
from backend.app.models.core import Bug, Requirement, Sprint, Task, TestCase, project_members
from backend.app.models.traceability import TraceabilityLink


ARTIFACT_MODELS = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
    "test_case": TestCase,
    "sprint": Sprint,
    "user": User,
}
RELATIONSHIP_TYPES = {"implements", "validates", "affects", "belongs_to", "associated_with"}
SUPPORTED_PAIRS = {
    ("requirement", "task"): {"implements", "affects", "belongs_to", "associated_with"},
    ("requirement", "bug"): {"affects", "associated_with"},
    ("requirement", "test_case"): {"validates", "associated_with"},
    ("requirement", "sprint"): {"belongs_to", "associated_with"},
    ("requirement", "user"): {"belongs_to", "associated_with"},
}


def _artifact_project_id(db: Session, artifact_type: str, artifact_id: UUID, project_id: UUID) -> UUID:
    model = ARTIFACT_MODELS.get(artifact_type)
    if model is None:
        raise HTTPException(status_code=422, detail="Unsupported artifact type")
    artifact = db.get(model, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=422, detail=f"{artifact_type} artifact not found")
    if artifact_type == "user":
        member = db.execute(
            select(project_members.c.user_id).where(
                project_members.c.project_id == project_id,
                project_members.c.user_id == artifact_id,
            )
        ).first()
        if member is None:
            raise HTTPException(status_code=422, detail="User artifact must be a member of the project")
        return project_id
    if artifact.project_id != project_id:
        raise HTTPException(status_code=422, detail="Artifacts must belong to the selected project")
    return artifact.project_id


def artifact_belongs_to_project(db: Session, artifact_type: str, artifact_id: UUID, project_id: UUID) -> bool:
    """Return whether a polymorphic artifact is present in the requested project."""
    model = ARTIFACT_MODELS.get(artifact_type)
    if model is None:
        return False
    artifact = db.get(model, artifact_id)
    if artifact is None:
        return False
    if artifact_type == "user":
        return db.execute(
            select(project_members.c.user_id).where(
                project_members.c.project_id == project_id,
                project_members.c.user_id == artifact_id,
            )
        ).first() is not None
    return artifact.project_id == project_id


def validate_link(db: Session, project_id: UUID, source_type: str, source_id: UUID, target_type: str, target_id: UUID, relationship_type: str) -> None:
    allowed = SUPPORTED_PAIRS.get((source_type, target_type))
    if allowed is None or relationship_type not in allowed:
        raise HTTPException(status_code=422, detail="Unsupported traceability relationship")
    if source_type == target_type and source_id == target_id:
        raise HTTPException(status_code=422, detail="Self-links are not allowed")
    _artifact_project_id(db, source_type, source_id, project_id)
    _artifact_project_id(db, target_type, target_id, project_id)


def create_link(db: Session, project_id: UUID, created_by_user_id: UUID, values: dict) -> TraceabilityLink:
    validate_link(db, project_id, values["source_artifact_type"], values["source_artifact_id"], values["target_artifact_type"], values["target_artifact_id"], values["relationship_type"])
    existing = db.scalar(
        select(TraceabilityLink).where(
            TraceabilityLink.project_id == project_id,
            TraceabilityLink.source_artifact_type == values["source_artifact_type"],
            TraceabilityLink.source_artifact_id == values["source_artifact_id"],
            TraceabilityLink.target_artifact_type == values["target_artifact_type"],
            TraceabilityLink.target_artifact_id == values["target_artifact_id"],
            TraceabilityLink.relationship_type == values["relationship_type"],
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Traceability link already exists")
    record = TraceabilityLink(project_id=project_id, created_by_user_id=created_by_user_id, **values)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_link(db: Session, project_id: UUID, link_id: UUID) -> TraceabilityLink:
    record = db.get(TraceabilityLink, link_id)
    if record is None or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Traceability link not found")
    return record


def list_project_links(db: Session, project_id: UUID, limit: int, offset: int, relationship_type: str | None = None):
    query = select(TraceabilityLink).where(TraceabilityLink.project_id == project_id).order_by(TraceabilityLink.created_at, TraceabilityLink.id)
    if relationship_type is not None:
        if relationship_type not in RELATIONSHIP_TYPES:
            raise HTTPException(status_code=422, detail="Invalid relationship type")
        query = query.where(TraceabilityLink.relationship_type == relationship_type)
    return db.scalars(query.limit(limit).offset(offset)).all()


def list_requirement_links(db: Session, project_id: UUID, requirement_id: UUID, limit: int, offset: int):
    _artifact_project_id(db, "requirement", requirement_id, project_id)
    query = select(TraceabilityLink).where(
        TraceabilityLink.project_id == project_id,
        ((TraceabilityLink.source_artifact_type == "requirement") & (TraceabilityLink.source_artifact_id == requirement_id))
        | ((TraceabilityLink.target_artifact_type == "requirement") & (TraceabilityLink.target_artifact_id == requirement_id)),
    ).order_by(TraceabilityLink.created_at, TraceabilityLink.id)
    return db.scalars(query.limit(limit).offset(offset)).all()


def list_artifact_links(db: Session, project_id: UUID, artifact_type: str, artifact_id: UUID, limit: int, offset: int):
    _artifact_project_id(db, artifact_type, artifact_id, project_id)
    query = select(TraceabilityLink).where(
        TraceabilityLink.project_id == project_id,
        ((TraceabilityLink.source_artifact_type == artifact_type) & (TraceabilityLink.source_artifact_id == artifact_id))
        | ((TraceabilityLink.target_artifact_type == artifact_type) & (TraceabilityLink.target_artifact_id == artifact_id)),
    ).order_by(TraceabilityLink.created_at, TraceabilityLink.id)
    return db.scalars(query.limit(limit).offset(offset)).all()


def delete_link(db: Session, record: TraceabilityLink) -> None:
    db.delete(record)
    db.commit()
