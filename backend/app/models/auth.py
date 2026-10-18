"""Authentication and role-management ORM models."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), nullable=False, default=_now),
    Column("assigned_by_user_id", Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True),
)


class Role(Base):
    """One of the six roles defined by the SRS."""

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(
            "code IN ('admin', 'project_manager', 'team_lead', 'developer', 'tester', 'client')",
            name="ck_roles_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    users: Mapped[list["User"]] = relationship(
        secondary=user_roles,
        foreign_keys=[user_roles.c.user_id, user_roles.c.role_id],
        back_populates="roles",
    )


class User(Base):
    """User identity and secure password-hash storage."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "account_status IN ('active', 'inactive', 'suspended')",
            name="ck_users_account_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    account_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        foreign_keys=[user_roles.c.user_id, user_roles.c.role_id],
        back_populates="users",
    )
