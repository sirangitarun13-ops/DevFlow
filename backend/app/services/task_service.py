"""Persistence services for tasks."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import Task


def create(db: Session, project_id: UUID, user_id: UUID, values: dict) -> Task:
    record = Task(project_id=project_id, created_by_user_id=user_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc()).limit(limit).offset(offset)).all()


def update(db: Session, record: Task, values: dict) -> Task:
    for key, value in values.items(): setattr(record, key, value)
    db.commit(); db.refresh(record); return record
