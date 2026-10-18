"""Persistence services for requirements."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import Requirement


def create(db: Session, project_id: UUID, user_id: UUID, values: dict) -> Requirement:
    record = Requirement(project_id=project_id, created_by_user_id=user_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(Requirement).where(Requirement.project_id == project_id).order_by(Requirement.requirement_key).limit(limit).offset(offset)).all()


def update(db: Session, record: Requirement, user_id: UUID, values: dict) -> Requirement:
    for key, value in values.items(): setattr(record, key, value)
    record.version += 1; record.updated_by_user_id = user_id; db.commit(); db.refresh(record); return record
