"""Persistence services for test cases."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.core import TestCase


def create(db: Session, project_id: UUID, user_id: UUID, values: dict) -> TestCase:
    record = TestCase(project_id=project_id, created_by_user_id=user_id, **values); db.add(record); db.commit(); db.refresh(record); return record


def list_for_project(db: Session, project_id: UUID, limit: int, offset: int):
    return db.scalars(select(TestCase).where(TestCase.project_id == project_id).order_by(TestCase.created_at.desc()).limit(limit).offset(offset)).all()


def update(db: Session, record: TestCase, values: dict) -> TestCase:
    for key, value in values.items(): setattr(record, key, value)
    db.commit(); db.refresh(record); return record
