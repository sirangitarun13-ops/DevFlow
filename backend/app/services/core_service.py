"""Project-scoped authorization and validation helpers for Phase 4."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.auth import User
from backend.app.models.core import Project, project_members
from backend.app.services.auth_service import user_has_any_role

MANAGER_ROLES = {"admin", "project_manager", "team_lead"}
TEAM_MANAGEMENT_ROLES = {"admin", "project_manager"}
REQUIREMENT_TYPES = {"functional", "non_functional"}
PRIORITIES = {"low", "medium", "high", "critical"}
PROJECT_STATUSES = {"planned", "active", "on_hold", "completed", "cancelled"}
MILESTONE_STATUSES = {"planned", "in_progress", "completed", "cancelled"}
REQUIREMENT_STATUSES = {"draft", "proposed", "approved", "in_progress", "completed", "rejected"}
SPRINT_STATUSES = {"planned", "active", "completed", "cancelled"}
TASK_STATUSES = {"todo", "in_progress", "in_review", "completed", "blocked"}
BUG_STATUSES = {"open", "in_progress", "resolved", "closed", "reopened"}
TEST_CASE_STATUSES = {"not_run", "passed", "failed", "blocked"}


def validate_choice(value: str, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid {field}")


def get_project_or_404(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def is_project_member(db: Session, project_id: UUID, user_id: UUID) -> bool:
    return db.execute(
        select(project_members.c.user_id).where(
            project_members.c.project_id == project_id,
            project_members.c.user_id == user_id,
        )
    ).first() is not None


def require_project_access(db: Session, project: Project, user: User) -> None:
    if user_has_any_role(user, {"admin"}):
        return
    if project.created_by_user_id == user.id or is_project_member(db, project.id, user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access is not permitted")


def require_project_management(db: Session, project: Project, user: User) -> None:
    require_project_access(db, project, user)
    if not user_has_any_role(user, MANAGER_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project management permission is required")


def require_team_management(db: Session, project: Project, user: User) -> None:
    """Require project access plus Admin or Project Manager authority."""

    require_project_access(db, project, user)
    if not user_has_any_role(user, TEAM_MANAGEMENT_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team management permission is required")


def ensure_project_member(db: Session, project_id: UUID, user_id: UUID) -> None:
    if db.get(User, user_id) is None or not is_project_member(db, project_id, user_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user must be a project member")
