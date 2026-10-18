"""Registration, login, current-user, and role-protected auth routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.core.rate_limit import get_limiter
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.schemas.auth import LoginRequest, RoleRead, TokenResponse, UserCreate, UserRead
from backend.app.services.auth_service import (
    assign_role,
    authenticate_user,
    create_access_token,
    hash_password,
)

router = APIRouter(prefix="/auth")

limiter = get_limiter()


def get_login_limit() -> str:
    """Get login rate limit from settings at request time."""
    return settings.rate_limit_login


def get_register_limit() -> str:
    """Get registration rate limit from settings at request time."""
    return settings.rate_limit_register


def serialize_user(user: User) -> UserRead:
    """Create a response-safe user representation."""

    return UserRead(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        account_status=user.account_status,
        roles=[RoleRead.model_validate(role) for role in user.roles],
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_register_limit)
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """Register a user with the safe default Client rate."""

    if db.scalar(select(User).where(User.email == user_data.email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        full_name=user_data.full_name.strip(),
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )
    db.add(user)
    assign_role(db, user, "client")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    saved_user = db.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    return serialize_user(saved_user or user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_login_limit)
def login(request: Request, credentials: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate credentials and return a short-lived bearer token."""

    user = authenticate_user(db, credentials.email, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token = create_access_token(user)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from error
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.get("/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user)) -> UserRead:
    """Return the authenticated user's safe profile."""

    return serialize_user(user)


@router.get("/admin-check", response_model=UserRead)
def admin_check(user: User = Depends(require_roles("admin"))) -> UserRead:
    """Protected role-check endpoint used to verify backend authorization."""

    return serialize_user(user)
