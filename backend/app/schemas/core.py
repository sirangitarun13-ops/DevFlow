"""Pydantic schemas for Phase 4 core SDLC modules."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.auth import RoleRead


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list
    limit: int
    offset: int


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: str = "planned"
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates_are_valid(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class ProjectUpdate(ProjectCreate):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = None


class ProjectRead(ORMModel):
    id: UUID
    name: str
    description: str | None
    status: str
    start_date: date | None
    end_date: date | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class MemberCreate(BaseModel):
    user_id: UUID
    project_role: Literal["admin", "project_manager", "team_lead", "developer", "tester", "client"] | None = None


class MemberRead(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    account_status: str
    roles: list[RoleRead]
    project_role: str | None
    joined_at: datetime
    assigned_task_count: int = 0
    completed_task_count: int = 0
    in_progress_task_count: int = 0
    pending_task_count: int = 0
    completion_percent: float = 0


class MilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_date: date | None = None
    status: str = "planned"


class MilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    target_date: date | None = None
    status: str | None = None


class MilestoneRead(ORMModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    target_date: date | None
    status: str


class RequirementCreate(BaseModel):
    requirement_key: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1)
    requirement_type: str
    priority: str
    status: str = "draft"


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = None
    priority: str | None = None
    status: str | None = None


class RequirementRead(ORMModel):
    id: UUID
    project_id: UUID
    requirement_key: str
    title: str
    description: str
    requirement_type: str
    priority: str
    status: str
    version: int


class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    goal: str | None = None
    start_date: date
    end_date: date
    status: str = "planned"

    @model_validator(mode="after")
    def dates_are_valid(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class SprintUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None


class SprintRead(ORMModel):
    id: UUID
    project_id: UUID
    name: str
    goal: str | None
    start_date: date
    end_date: date
    status: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str | None = None
    requirement_id: UUID | None = None
    sprint_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    priority: str
    status: str = "todo"
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = None
    requirement_id: UUID | None = None
    sprint_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    priority: str | None = None
    status: str | None = None
    due_date: date | None = None


class TaskRead(ORMModel):
    id: UUID
    project_id: UUID
    requirement_id: UUID | None
    sprint_id: UUID | None
    title: str
    description: str | None
    assigned_to_user_id: UUID | None
    priority: str
    status: str
    due_date: date | None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(ORMModel):
    id: UUID
    task_id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime


class BugCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1)
    requirement_id: UUID | None = None
    task_id: UUID | None = None
    severity: str
    status: str = "open"
    assigned_to_user_id: UUID | None = None


class BugUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    assigned_to_user_id: UUID | None = None


class BugRead(ORMModel):
    id: UUID
    project_id: UUID
    requirement_id: UUID | None
    task_id: UUID | None
    title: str
    severity: str
    status: str
    assigned_to_user_id: UUID | None


class TestCaseCreate(BaseModel):
    requirement_id: UUID
    title: str = Field(min_length=1, max_length=250)
    preconditions: str | None = None
    test_steps: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    actual_result: str | None = None
    status: str = "not_run"
    executed_by_user_id: UUID | None = None


class TestCaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    preconditions: str | None = None
    test_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    status: str | None = None
    executed_by_user_id: UUID | None = None


class TestCaseRead(ORMModel):
    id: UUID
    project_id: UUID
    requirement_id: UUID
    title: str
    status: str
