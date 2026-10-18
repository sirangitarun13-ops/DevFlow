"""Persistence services for bugs."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import Bug


def create(db: Session, project_id: UUID, reporter_user_id: UUID, values: dict) -> Bug:
    record = Bug(project_id=project_id, reported_by_user_id=reporter_user_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(Bug).where(Bug.project_id == project_id).order_by(Bug.created_at.desc()).limit(limit).offset(offset)).all()


def update(db: Session, record: Bug, values: dict) -> Bug:
    for key, value in values.items(): setattr(record, key, value)
    db.commit(); db.refresh(record); return record
