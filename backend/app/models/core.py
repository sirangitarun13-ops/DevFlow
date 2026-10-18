"""Core SDLC ORM models authorized for Phase 4."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.auth import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


project_members = Table(
    "project_members",
    Base.metadata,
    Column("project_id", Uuid(as_uuid=True), ForeignKey("projects.id"), primary_key=True),
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("project_role", String(32), nullable=True),
    Column("joined_at", DateTime(timezone=True), nullable=False, default=_now),
    CheckConstraint("project_role IS NULL OR project_role IN ('admin', 'project_manager', 'team_lead', 'developer', 'tester', 'client')", name="ck_project_members_role"),
)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_projects_dates"),
        CheckConstraint("status IN ('planned', 'active', 'on_hold', 'completed', 'cancelled')", name="ck_projects_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    start_date: Mapped[date] = mapped_column(Date, nullable=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sprints: Mapped[list["Sprint"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    bugs: Mapped[list["Bug"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    members: Mapped[list["User"]] = relationship("User", secondary=project_members, viewonly=True)


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_milestones_project_name"),
        CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_milestones_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="milestones")


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint("project_id", "requirement_key", name="uq_requirements_project_key"),
        CheckConstraint("requirement_type IN ('functional', 'non_functional')", name="ck_requirements_type"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_requirements_priority"),
        CheckConstraint("status IN ('draft', 'proposed', 'approved', 'in_progress', 'completed', 'rejected')", name="ck_requirements_status"),
        CheckConstraint("version > 0", name="ck_requirements_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    requirement_key: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="requirements")
    tasks: Mapped[list["Task"]] = relationship(back_populates="requirement", foreign_keys="Task.requirement_id")
    bugs: Mapped[list["Bug"]] = relationship(back_populates="requirement", foreign_keys="Bug.requirement_id")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="requirement")


class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_sprints_project_name"),
        CheckConstraint("end_date >= start_date", name="ck_sprints_dates"),
        CheckConstraint("status IN ('planned', 'active', 'completed', 'cancelled')", name="ck_sprints_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="sprints")
    tasks: Mapped[list["Task"]] = relationship(back_populates="sprint")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_tasks_priority"),
        CheckConstraint("status IN ('todo', 'in_progress', 'in_review', 'completed', 'blocked')", name="ck_tasks_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    requirement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id"), nullable=True, index=True)
    sprint_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sprints.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    assigned_to_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="todo")
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="tasks")
    requirement: Mapped[Requirement] = relationship(back_populates="tasks", foreign_keys=[requirement_id])
    sprint: Mapped[Sprint] = relationship(back_populates="tasks")
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    bugs: Mapped[list["Bug"]] = relationship(back_populates="task", foreign_keys="Bug.task_id")


class TaskComment(Base):
    __tablename__ = "task_comments"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    author_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    task: Mapped[Task] = relationship(back_populates="comments")


class Bug(Base):
    __tablename__ = "bugs"
    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_bugs_severity"),
        CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'closed', 'reopened')", name="ck_bugs_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    requirement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id"), nullable=True)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    assigned_to_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reported_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="bugs")
    requirement: Mapped[Requirement] = relationship(back_populates="bugs", foreign_keys=[requirement_id])
    task: Mapped[Task] = relationship(back_populates="bugs", foreign_keys=[task_id])


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (CheckConstraint("status IN ('not_run', 'passed', 'failed', 'blocked')", name="ck_test_cases_status"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    requirement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requirements.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    preconditions: Mapped[str] = mapped_column(Text, nullable=True)
    test_steps: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    actual_result: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_run")
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    executed_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    project: Mapped[Project] = relationship(back_populates="test_cases")
    requirement: Mapped[Requirement] = relationship(back_populates="test_cases")
