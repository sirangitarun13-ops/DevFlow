"""Project analytics endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.core import accessible_project
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.schemas.analytics import ProjectAnalyticsSummary
from backend.app.services.analytics_service import get_project_summary

router = APIRouter(prefix="/projects")


@router.get("/{project_id}/analytics/summary", response_model=ProjectAnalyticsSummary)
def project_analytics_summary(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    return get_project_summary(db, project, user)
