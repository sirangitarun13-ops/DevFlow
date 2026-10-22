"""Authentication and role-assignment service functions."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import settings
from backend.app.models.auth import Role, User, user_roles
from backend.app.models.core import project_members

password_hasher = PasswordHasher()

ROLE_CATALOG = {
    "admin": "Administrator",
    "project_manager": "Project Manager",
    "team_lead": "Team Lead",
    "developer": "Developer",
    "tester": "Tester",
    "client": "Client",
}


def hash_password(password: str) -> str:
    """Hash a password with Argon2id through argon2-cffi."""

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches its stored hash."""

    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user: User) -> str:
    """Create a short-lived JWT containing only a user ID and role codes."""

    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY must be configured")
    now = datetime.now(timezone.utc)
    # Use demo override if set, otherwise use standard expiration
    expire_minutes = settings.demo_access_token_expire_minutes or settings.access_token_expire_minutes
    expires_at = now + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user.id),
        "roles": [role.code for role in user.roles],
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT, raising PyJWT errors for invalid tokens."""

    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY must be configured")
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Find an active user and verify the supplied password."""

    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or user.account_status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_or_create_role(db: Session, role_code: str) -> Role:
    """Return a catalog role, creating only a missing reference role."""

    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is not None:
        return role
    if role_code not in ROLE_CATALOG:
        raise ValueError("Unsupported role")
    role = Role(code=role_code, name=ROLE_CATALOG[role_code])
    db.add(role)
    db.flush()
    return role


def assign_role(db: Session, user: User, role_code: str) -> Role:
    """Assign a role through a service boundary, not a route handler."""

    role = get_or_create_role(db, role_code)
    if role not in user.roles:
        user.roles.append(role)
        db.flush()
    return role


def user_has_any_role(user: User, allowed_roles: set[str]) -> bool:
    """Return whether a user has at least one allowed role."""

    return any(role.code in allowed_roles for role in user.roles)


def list_directory_users(
    db: Session,
    project_id: UUID,
    search: str | None,
    limit: int,
    offset: int,
) -> list[User]:
    """Return active users who can be considered for a project team.

    The project id is deliberately required so a caller cannot use this
    endpoint as an unscoped user dump. Existing project members are excluded.
    """

    already_member = select(project_members.c.user_id).where(
        project_members.c.project_id == project_id,
        project_members.c.user_id == User.id,
    )
    query = (
        select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(User.account_status == "active")
        .where(Role.code == "developer")
        .where(~already_member.exists())
        .options(selectinload(User.roles))
        .order_by(User.full_name.asc(), User.email.asc())
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    return db.scalars(query.limit(limit).offset(offset)).unique().all()


def user_id_from_token(payload: dict) -> UUID:
    """Extract and validate the UUID subject from a JWT payload."""

    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token subject is missing")
    return UUID(str(subject))
