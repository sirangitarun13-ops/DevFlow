"""Persistence services for projects and project membership."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.auth import User
from backend.app.models.core import Project, Task, project_members


def list_projects(db: Session, user: User, limit: int, offset: int, is_admin: bool):
    query = select(Project).order_by(Project.created_at.desc())
    if not is_admin:
        query = query.outerjoin(project_members, project_members.c.project_id == Project.id).where(
            or_(Project.created_by_user_id == user.id, project_members.c.user_id == user.id)
        )
    return db.scalars(query.limit(limit).offset(offset)).all()


def create_project(db: Session, project: Project, owner_role: str = "project_manager") -> Project:
    db.add(project)
    db.flush()
    db.execute(project_members.insert().values(project_id=project.id, user_id=project.created_by_user_id, project_role=owner_role))
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, values: dict) -> Project:
    start_date = values.get("start_date", project.start_date)
    end_date = values.get("end_date", project.end_date)
    if start_date is not None and end_date is not None and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must not precede start_date")
    for key, value in values.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


def add_member(db: Session, project_id: UUID, user_id: UUID, project_role: str | None):
    member = db.get(User, user_id)
    if member is None or member.account_status != "active":
        raise HTTPException(status_code=422, detail="An active user is required")
    if not any(role.code == "developer" for role in member.roles):
        raise HTTPException(status_code=422, detail="Only users with the Developer role can be added through team management")
    if db.execute(select(project_members.c.user_id).where(project_members.c.project_id == project_id, project_members.c.user_id == user_id)).first():
        raise HTTPException(status_code=409, detail="User is already a project member")
    db.execute(project_members.insert().values(project_id=project_id, user_id=user_id, project_role=project_role))
    db.commit()


def list_members(db: Session, project_id: UUID):
    completed_task = case((Task.status == "completed", 1), else_=0)
    in_progress_task = case((Task.status == "in_progress", 1), else_=0)
    pending_task = case((Task.status == "todo", 1), else_=0)
    task_counts = (
        select(
            Task.assigned_to_user_id.label("user_id"),
            func.count(Task.id).label("assigned_task_count"),
            func.sum(completed_task).label("completed_task_count"),
            func.sum(in_progress_task).label("in_progress_task_count"),
            func.sum(pending_task).label("pending_task_count"),
        )
        .where(Task.project_id == project_id, Task.assigned_to_user_id.is_not(None))
        .group_by(Task.assigned_to_user_id)
        .subquery()
    )
    return db.execute(
        select(
            User,
            project_members.c.project_role,
            project_members.c.joined_at,
            func.coalesce(task_counts.c.assigned_task_count, 0).label("assigned_task_count"),
            func.coalesce(task_counts.c.completed_task_count, 0).label("completed_task_count"),
            func.coalesce(task_counts.c.in_progress_task_count, 0).label("in_progress_task_count"),
            func.coalesce(task_counts.c.pending_task_count, 0).label("pending_task_count"),
        )
        .join(project_members, project_members.c.user_id == User.id)
        .outerjoin(task_counts, task_counts.c.user_id == User.id)
        .options(selectinload(User.roles))
        .where(project_members.c.project_id == project_id)
        .order_by(User.full_name.asc(), User.email.asc())
    ).all()


def remove_member(db: Session, project: Project, user_id: UUID):
    if project.created_by_user_id == user_id:
        raise HTTPException(status_code=409, detail="The project owner cannot be removed")
    result = db.execute(
        project_members.delete().where(project_members.c.project_id == project.id, project_members.c.user_id == user_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Project member not found")
    db.commit()


def list_member_tasks(db: Session, project_id: UUID, user_id: UUID):
    return db.scalars(
        select(Task)
        .where(Task.project_id == project_id, Task.assigned_to_user_id == user_id)
        .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    ).all()
