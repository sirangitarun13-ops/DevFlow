"""Project-scoped Phase 4 CRUD routers."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.models.core import Bug, Milestone, Project, Requirement, Sprint, Task, TaskComment, TestCase, project_members
from backend.app.schemas.core import (
    BugCreate, BugRead, BugUpdate, CommentCreate, CommentRead, MemberCreate, MemberRead,
    MilestoneCreate, MilestoneRead, MilestoneUpdate, ProjectCreate, ProjectRead, ProjectUpdate,
    RequirementCreate, RequirementRead, RequirementUpdate, SprintCreate, SprintRead, SprintUpdate,
    TaskCreate, TaskRead, TaskUpdate, TestCaseCreate, TestCaseRead, TestCaseUpdate,
)
from backend.app.services.core_service import (
    BUG_STATUSES, MILESTONE_STATUSES, PRIORITIES, PROJECT_STATUSES, REQUIREMENT_STATUSES,
    REQUIREMENT_TYPES, SPRINT_STATUSES, TASK_STATUSES, TEST_CASE_STATUSES, ensure_project_member,
    get_project_or_404, require_project_access, require_project_management, require_team_management, validate_choice,
)
from backend.app.services import (
    bug_service, comment_service, milestone_service, project_service,
    requirement_service, sprint_service, task_service, test_case_service,
)

router = APIRouter(prefix="/projects")


def page(db: Session, query, limit: int, offset: int):
    return db.scalars(query.limit(limit).offset(offset)).all()


def record_or_404(db: Session, model, record_id: UUID):
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


def managed_project(db: Session, project_id: UUID, user: User) -> Project:
    project = get_project_or_404(db, project_id)
    require_project_management(db, project, user)
    return project


def accessible_project(db: Session, project_id: UUID, user: User) -> Project:
    project = get_project_or_404(db, project_id)
    require_project_access(db, project, user)
    return project


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "project_manager"))):
    validate_choice(data.status, PROJECT_STATUSES, "project status")
    return project_service.create_project(db, Project(**data.model_dump(), created_by_user_id=user.id))


@router.get("", response_model=list[ProjectRead])
def list_projects(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return project_service.list_projects(db, user, limit, offset, any(role.code == "admin" for role in user.roles))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return accessible_project(db, project_id, user)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, data: ProjectUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = managed_project(db, project_id, user)
    values = data.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is not None:
        validate_choice(values["status"], PROJECT_STATUSES, "project status")
    return project_service.update_project(db, project, values)


@router.post("/{project_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(project_id: UUID, data: MemberCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_or_404(db, project_id)
    require_team_management(db, project, user)
    project_service.add_member(db, project_id, data.user_id, data.project_role)
    return next(serialize_member(row) for row in project_service.list_members(db, project_id) if row.User.id == data.user_id)


@router.get("/{project_id}/members", response_model=list[MemberRead])
def list_members(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    return [serialize_member(row) for row in project_service.list_members(db, project_id)]


def serialize_member(row) -> MemberRead:
    user = row.User
    return MemberRead(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        account_status=user.account_status,
        roles=[{"code": role.code, "name": role.name} for role in user.roles],
        project_role=row.project_role,
        joined_at=row.joined_at,
        assigned_task_count=row.assigned_task_count,
        completed_task_count=row.completed_task_count,
        in_progress_task_count=row.in_progress_task_count,
        pending_task_count=row.pending_task_count,
        completion_percent=round((row.completed_task_count / row.assigned_task_count) * 100, 2) if row.assigned_task_count else 0,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(project_id: UUID, user_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_or_404(db, project_id)
    require_team_management(db, project, user)
    project_service.remove_member(db, project, user_id)


@router.get("/{project_id}/members/{user_id}/tasks", response_model=list[TaskRead])
def list_member_tasks(project_id: UUID, user_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    member = next((row for row in project_service.list_members(db, project.id) if row.User.id == user_id), None)
    if member is None:
        raise HTTPException(status_code=404, detail="Project member not found")
    if not any(role.code == "developer" for role in member.User.roles):
        raise HTTPException(status_code=422, detail="Task details are available for Developers only")
    return project_service.list_member_tasks(db, project.id, user_id)


@router.post("/{project_id}/milestones", response_model=MilestoneRead, status_code=201)
def create_milestone(project_id: UUID, data: MilestoneCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user); validate_choice(data.status, MILESTONE_STATUSES, "milestone status")
    return milestone_service.create(db, project_id, data.model_dump())


@router.get("/{project_id}/milestones", response_model=list[MilestoneRead])
def list_milestones(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return milestone_service.list_for_project(db, project_id, limit, offset)


@router.patch("/milestones/{record_id}", response_model=MilestoneRead)
def update_milestone(record_id: UUID, data: MilestoneUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Milestone, record_id); managed_project(db, record.project_id, user)
    values = data.model_dump(exclude_unset=True)
    if values.get("status"): validate_choice(values["status"], MILESTONE_STATUSES, "milestone status")
    return milestone_service.update(db, record, values)


@router.get("/milestones/{record_id}", response_model=MilestoneRead)
def get_milestone(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Milestone, record_id); accessible_project(db, record.project_id, user); return record


@router.post("/{project_id}/requirements", response_model=RequirementRead, status_code=201)
def create_requirement(project_id: UUID, data: RequirementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    validate_choice(data.requirement_type, REQUIREMENT_TYPES, "requirement type"); validate_choice(data.priority, PRIORITIES, "priority"); validate_choice(data.status, REQUIREMENT_STATUSES, "requirement status")
    return requirement_service.create(db, project_id, user.id, data.model_dump())


@router.get("/{project_id}/requirements", response_model=list[RequirementRead])
def list_requirements(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return requirement_service.list_for_project(db, project_id, limit, offset)


@router.patch("/requirements/{record_id}", response_model=RequirementRead)
def update_requirement(record_id: UUID, data: RequirementUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Requirement, record_id); managed_project(db, record.project_id, user)
    values = data.model_dump(exclude_unset=True)
    if values.get("priority"): validate_choice(values["priority"], PRIORITIES, "priority")
    if values.get("status"): validate_choice(values["status"], REQUIREMENT_STATUSES, "requirement status")
    return requirement_service.update(db, record, user.id, values)


@router.get("/requirements/{record_id}", response_model=RequirementRead)
def get_requirement(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Requirement, record_id); accessible_project(db, record.project_id, user); return record


@router.post("/{project_id}/sprints", response_model=SprintRead, status_code=201)
def create_sprint(project_id: UUID, data: SprintCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user); validate_choice(data.status, SPRINT_STATUSES, "sprint status")
    return sprint_service.create(db, project_id, data.model_dump())


@router.get("/{project_id}/sprints", response_model=list[SprintRead])
def list_sprints(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return sprint_service.list_for_project(db, project_id, limit, offset)


@router.patch("/sprints/{record_id}", response_model=SprintRead)
def update_sprint(record_id: UUID, data: SprintUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Sprint, record_id); managed_project(db, record.project_id, user)
    values = data.model_dump(exclude_unset=True)
    if values.get("status"): validate_choice(values["status"], SPRINT_STATUSES, "sprint status")
    if "start_date" in values or "end_date" in values:
        new_start = values.get("start_date", record.start_date)
        new_end = values.get("end_date", record.end_date)
        if new_end < new_start:
            raise HTTPException(status_code=422, detail="end_date must not precede start_date")
    return sprint_service.update(db, record, values)


@router.get("/sprints/{record_id}", response_model=SprintRead)
def get_sprint(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Sprint, record_id); accessible_project(db, record.project_id, user); return record


def validate_task_links(db: Session, project_id: UUID, values: dict):
    if values.get("requirement_id"):
        item = db.get(Requirement, values["requirement_id"])
        if item is None or item.project_id != project_id: raise HTTPException(status_code=422, detail="Requirement must belong to the project")
    if values.get("sprint_id"):
        item = db.get(Sprint, values["sprint_id"])
        if item is None or item.project_id != project_id: raise HTTPException(status_code=422, detail="Sprint must belong to the project")
    if values.get("assigned_to_user_id"): ensure_project_member(db, project_id, values["assigned_to_user_id"])


@router.post("/{project_id}/tasks", response_model=TaskRead, status_code=201)
def create_task(project_id: UUID, data: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user); validate_choice(data.priority, PRIORITIES, "priority"); validate_choice(data.status, TASK_STATUSES, "task status")
    values = data.model_dump(); validate_task_links(db, project_id, values)
    return task_service.create(db, project_id, user.id, values)


@router.get("/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return task_service.list_for_project(db, project_id, limit, offset)


@router.patch("/tasks/{record_id}", response_model=TaskRead)
def update_task(record_id: UUID, data: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Task, record_id); project = accessible_project(db, record.project_id, user)
    values = data.model_dump(exclude_unset=True)
    is_manager = any(role.code in {"admin", "project_manager", "team_lead"} for role in user.roles)
    if not is_manager:
        if record.assigned_to_user_id != user.id or set(values) - {"status"}:
            raise HTTPException(status_code=403, detail="Only assigned developers may update task status")
    if values.get("priority"): validate_choice(values["priority"], PRIORITIES, "priority")
    if values.get("status"): validate_choice(values["status"], TASK_STATUSES, "task status")
    validate_task_links(db, record.project_id, values)
    return task_service.update(db, record, values)


@router.get("/tasks/{record_id}", response_model=TaskRead)
def get_task(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Task, record_id); accessible_project(db, record.project_id, user); return record


@router.post("/tasks/{task_id}/comments", response_model=CommentRead, status_code=201)
def add_comment(task_id: UUID, data: CommentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = record_or_404(db, Task, task_id); accessible_project(db, task.project_id, user)
    return comment_service.create(db, task_id, user.id, data.body)


@router.get("/tasks/{task_id}/comments", response_model=list[CommentRead])
def list_comments(task_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = record_or_404(db, Task, task_id); accessible_project(db, task.project_id, user)
    return comment_service.list_for_task(db, task_id)


def validate_bug_links(db: Session, project_id: UUID, values: dict):
    if values.get("requirement_id"):
        item = db.get(Requirement, values["requirement_id"])
        if item is None or item.project_id != project_id: raise HTTPException(status_code=422, detail="Requirement must belong to the project")
    if values.get("task_id"):
        item = db.get(Task, values["task_id"])
        if item is None or item.project_id != project_id: raise HTTPException(status_code=422, detail="Task must belong to the project")
    if values.get("assigned_to_user_id"): ensure_project_member(db, project_id, values["assigned_to_user_id"])


@router.post("/{project_id}/bugs", response_model=BugRead, status_code=201)
def create_bug(project_id: UUID, data: BugCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    if not any(role.code in {"admin", "project_manager", "team_lead", "tester"} for role in user.roles):
        raise HTTPException(status_code=403, detail="Bug reporting permission is required")
    validate_choice(data.severity, PRIORITIES, "severity"); validate_choice(data.status, BUG_STATUSES, "bug status")
    values = data.model_dump(); validate_bug_links(db, project.id, values)
    return bug_service.create(db, project.id, user.id, values)


@router.get("/{project_id}/bugs", response_model=list[BugRead])
def list_bugs(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return bug_service.list_for_project(db, project_id, limit, offset)


@router.patch("/bugs/{record_id}", response_model=BugRead)
def update_bug(record_id: UUID, data: BugUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Bug, record_id); accessible_project(db, record.project_id, user)
    values = data.model_dump(exclude_unset=True)
    is_manager = any(role.code in {"admin", "project_manager", "team_lead"} for role in user.roles)
    is_tester = any(role.code == "tester" for role in user.roles)
    if not is_manager and not is_tester:
        raise HTTPException(status_code=403, detail="Bug update permission is required")
    if not is_manager and "assigned_to_user_id" in values:
        raise HTTPException(status_code=403, detail="Only project managers may assign bugs")
    if values.get("severity"): validate_choice(values["severity"], PRIORITIES, "severity")
    if values.get("status"): validate_choice(values["status"], BUG_STATUSES, "bug status")
    validate_bug_links(db, record.project_id, values)
    return bug_service.update(db, record, values)


@router.get("/bugs/{record_id}", response_model=BugRead)
def get_bug(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, Bug, record_id); accessible_project(db, record.project_id, user); return record


@router.post("/{project_id}/test-cases", response_model=TestCaseRead, status_code=201)
def create_test_case(project_id: UUID, data: TestCaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    if not any(role.code in {"admin", "project_manager", "team_lead", "tester"} for role in user.roles):
        raise HTTPException(status_code=403, detail="Test-case permission is required")
    validate_choice(data.status, TEST_CASE_STATUSES, "test case status")
    requirement = db.get(Requirement, data.requirement_id)
    if requirement is None or requirement.project_id != project_id: raise HTTPException(status_code=422, detail="Requirement must belong to the project")
    if data.executed_by_user_id: ensure_project_member(db, project_id, data.executed_by_user_id)
    return test_case_service.create(db, project_id, user.id, data.model_dump())


@router.get("/{project_id}/test-cases", response_model=list[TestCaseRead])
def list_test_cases(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user); return test_case_service.list_for_project(db, project_id, limit, offset)


@router.patch("/test-cases/{record_id}", response_model=TestCaseRead)
def update_test_case(record_id: UUID, data: TestCaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, TestCase, record_id); accessible_project(db, record.project_id, user)
    if not any(role.code in {"admin", "project_manager", "team_lead", "tester"} for role in user.roles):
        raise HTTPException(status_code=403, detail="Test-case permission is required")
    values = data.model_dump(exclude_unset=True)
    if values.get("status"): validate_choice(values["status"], TEST_CASE_STATUSES, "test case status")
    if values.get("executed_by_user_id"): ensure_project_member(db, record.project_id, values["executed_by_user_id"])
    return test_case_service.update(db, record, values)


@router.get("/test-cases/{record_id}", response_model=TestCaseRead)
def get_test_case(record_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = record_or_404(db, TestCase, record_id); accessible_project(db, record.project_id, user); return record
