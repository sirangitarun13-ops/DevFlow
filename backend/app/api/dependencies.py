"""Reusable authentication and authorization dependencies."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.services.auth_service import decode_access_token, user_has_any_role, user_id_from_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate a bearer token and load the active user with roles."""

    try:
        payload = decode_access_token(token)
        user_id = user_id_from_token(payload)
    except (jwt.PyJWTError, RuntimeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    if user is None or user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Build a dependency that permits users with any listed role."""

    allowed = set(allowed_roles)

    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if not user_has_any_role(user, allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return user

    return role_dependency
