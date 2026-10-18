"""Persistence services for sprints."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import Sprint


def create(db: Session, project_id: UUID, values: dict) -> Sprint:
    record = Sprint(project_id=project_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.start_date).limit(limit).offset(offset)).all()


def update(db: Session, record: Sprint, values: dict) -> Sprint:
    for key, value in values.items(): setattr(record, key, value)
    db.commit(); db.refresh(record); return record
