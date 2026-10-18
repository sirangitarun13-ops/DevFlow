"""Project-scoped Phase 5 traceability routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.core import accessible_project, managed_project
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.schemas.traceability import ArtifactType, RelationshipType, TraceabilityLinkCreate, TraceabilityLinkRead
from backend.app.services import traceability_service


router = APIRouter(prefix="/projects")


@router.post("/{project_id}/traceability-links", response_model=TraceabilityLinkRead, status_code=status.HTTP_201_CREATED)
def create_traceability_link(project_id: UUID, data: TraceabilityLinkCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    return traceability_service.create_link(db, project_id, user.id, data.model_dump())


@router.get("/{project_id}/traceability-links", response_model=list[TraceabilityLinkRead])
def list_traceability_links(
    project_id: UUID,
    relationship_type: RelationshipType | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accessible_project(db, project_id, user)
    return traceability_service.list_project_links(db, project_id, limit, offset, relationship_type)


@router.get("/{project_id}/requirements/{requirement_id}/traceability-links", response_model=list[TraceabilityLinkRead])
def list_requirement_traceability_links(project_id: UUID, requirement_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    return traceability_service.list_requirement_links(db, project_id, requirement_id, limit, offset)


@router.get("/{project_id}/artifacts/{artifact_type}/{artifact_id}/traceability-links", response_model=list[TraceabilityLinkRead])
def list_artifact_traceability_links(project_id: UUID, artifact_type: ArtifactType, artifact_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    return traceability_service.list_artifact_links(db, project_id, artifact_type, artifact_id, limit, offset)


@router.get("/{project_id}/traceability-links/{link_id}", response_model=TraceabilityLinkRead)
def get_traceability_link(project_id: UUID, link_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    return traceability_service.get_link(db, project_id, link_id)


@router.delete("/{project_id}/traceability-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_traceability_link(project_id: UUID, link_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    record = traceability_service.get_link(db, project_id, link_id)
    traceability_service.delete_link(db, record)
