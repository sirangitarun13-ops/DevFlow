"""Build deterministic report data from existing domain services and models."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.core import Bug, Milestone, Project, Requirement, Sprint, Task, TestCase
from backend.app.models.auth import User
from backend.app.models.rcia import ImpactAnalysis, RequirementChangeRequest
from backend.app.services.analytics_service import get_project_summary
from backend.app.services.core_service import require_project_access
from backend.app.services.rcia_service import get_change_request, list_results


def _rows(db: Session, model, project_id: UUID):
    return db.scalars(select(model).where(model.project_id == project_id).order_by(model.created_at, model.id)).all()


def _base(project: Project, report_type: str, analytics: dict) -> dict:
    return {"type": report_type, "title": report_type.replace("-", " ").title(), "generated_at": datetime.now(timezone.utc).isoformat(), "project": {"name": project.name, "description": project.description, "status": project.status, "start_date": project.start_date, "end_date": project.end_date, "progress_percent": analytics["project"]["progress_percent"]}, "analytics": analytics}


def build_project_report(db: Session, project: Project, user: User, report_type: str) -> dict:
    require_project_access(db, project, user)
    analytics = get_project_summary(db, project, user)
    report = _base(project, report_type, analytics)
    # Detailed rows are intentionally prepared here, outside the renderer, so the renderer never queries the database.
    report["records"] = {"requirements": _rows(db, Requirement, project.id), "milestones": _rows(db, Milestone, project.id), "sprints": _rows(db, Sprint, project.id), "tasks": _rows(db, Task, project.id), "bugs": _rows(db, Bug, project.id), "test_cases": _rows(db, TestCase, project.id)}
    return report


def build_change_impact_report(db: Session, project: Project, user: User, change_request_id: UUID) -> dict:
    require_project_access(db, project, user)
    change = get_change_request(db, project.id, change_request_id)
    requirement = db.get(Requirement, change.requirement_id)
    if requirement is None:
        raise ValueError("Requirement not found")
    analysis = db.scalar(select(ImpactAnalysis).where(ImpactAnalysis.project_id == project.id, ImpactAnalysis.change_request_id == change.id).order_by(ImpactAnalysis.started_at.desc(), ImpactAnalysis.id.desc()))
    results = []
    if analysis:
        for result in list_results(db, project.id, analysis.id):
            path = " -> ".join(step.get("relationship_type", "traceability") for step in (result.relationship_path or [])) or "No path recorded"
            results.append({"impact_category": result.impact_category, "artifact_type": result.artifact_type, "artifact_id": str(result.artifact_id), "path": path, "explanation": result.explanation})
    report = _base(project, "change-impact", get_project_summary(db, project, user))
    report["requirement"] = {"requirement_key": requirement.requirement_key, "title": requirement.title, "priority": requirement.priority, "status": requirement.status}
    report["change_request"] = {"change_summary": change.change_summary, "status": change.status, "proposed_description": change.proposed_description}
    report["analysis"] = {"status": analysis.status, "started_at": analysis.started_at, "summary": analysis.summary} if analysis else None
    report["results"] = results
    return report
