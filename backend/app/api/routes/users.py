"""Project-scoped user directory routes for team management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.schemas.auth import RoleRead, UserDirectoryRead
from backend.app.services.auth_service import list_directory_users
from backend.app.services.core_service import get_project_or_404, require_project_management

router = APIRouter(prefix="/users")


@router.get("/developers", response_model=list[UserDirectoryRead])
def developer_directory(
    project_id: UUID,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id)
    require_project_management(db, project, user)
    users = list_directory_users(db, project_id, search, limit, offset)
    return [
        UserDirectoryRead(
            id=item.id,
            full_name=item.full_name,
            email=item.email,
            account_status=item.account_status,
            roles=[RoleRead.model_validate(item_role) for item_role in item.roles],
        )
        for item in users
    ]
