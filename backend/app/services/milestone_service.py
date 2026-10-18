"""Persistence services for milestones."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import Milestone


def create(db: Session, project_id: UUID, values: dict) -> Milestone:
    record = Milestone(project_id=project_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.target_date).limit(limit).offset(offset)).all()


def update(db: Session, record: Milestone, values: dict) -> Milestone:
    for key, value in values.items(): setattr(record, key, value)
    db.commit(); db.refresh(record); return record
