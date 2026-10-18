"""Persistence services for task comments."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import TaskComment


def create(db: Session, task_id: UUID, author_user_id: UUID, body: str) -> TaskComment:
    record = TaskComment(task_id=task_id, author_user_id=author_user_id, body=body); db.add(record); db.commit(); db.refresh(record); return record


def list_for_task(db: Session, task_id: UUID):
    return db.scalars(select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at)).all()
