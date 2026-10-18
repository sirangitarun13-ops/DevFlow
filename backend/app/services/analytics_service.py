"""Project-scoped deterministic analytics aggregation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.core import Bug, Milestone, Project, Requirement, Sprint, Task, TestCase
from backend.app.models.rcia import ImpactAnalysis, ImpactAnalysisResult, RequirementChangeRequest
from backend.app.models.auth import User
from backend.app.services.core_service import require_project_access


def _grouped_counts(db: Session, model, column, project_id: UUID) -> dict[str, int]:
    rows = db.execute(
        select(column, func.count()).where(model.project_id == project_id).group_by(column)
    ).all()
    return {str(value): int(count) for value, count in rows if value is not None}


def _count(db: Session, model, project_id: UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0)


def _summary(total: int, statuses: dict[str, int]) -> dict[str, object]:
    return {"total": total, "by_status": statuses}


def _change_request_counts(db: Session, project_id: UUID) -> dict[str, int]:
    rows = db.execute(
        select(RequirementChangeRequest.status, func.count())
        .join(Requirement, Requirement.id == RequirementChangeRequest.requirement_id)
        .where(Requirement.project_id == project_id)
        .group_by(RequirementChangeRequest.status)
    ).all()
    return {str(value): int(count) for value, count in rows}


def get_project_summary(db: Session, project: Project, user: User) -> dict:
    """Return deterministic project metrics using database-side aggregation."""

    require_project_access(db, project, user)

    task_status = _grouped_counts(db, Task, Task.status, project.id)
    task_total = sum(task_status.values())
    completed_tasks = task_status.get("completed", 0)
    progress = round((completed_tasks / task_total) * 100, 2) if task_total else 0.0

    requirement_status = _grouped_counts(db, Requirement, Requirement.status, project.id)
    requirement_priority = _grouped_counts(db, Requirement, Requirement.priority, project.id)
    milestone_status = _grouped_counts(db, Milestone, Milestone.status, project.id)
    sprint_status = _grouped_counts(db, Sprint, Sprint.status, project.id)
    bug_status = _grouped_counts(db, Bug, Bug.status, project.id)
    bug_severity = _grouped_counts(db, Bug, Bug.severity, project.id)
    test_status = _grouped_counts(db, TestCase, TestCase.status, project.id)
    change_status = _change_request_counts(db, project.id)

    active_sprint = db.execute(
        select(Sprint).where(Sprint.project_id == project.id, Sprint.status == "active").order_by(Sprint.start_date, Sprint.id)
    ).scalars().first()
    active = None
    if active_sprint:
        sprint_task_rows = db.execute(
            select(Task.status, func.count()).where(Task.project_id == project.id, Task.sprint_id == active_sprint.id).group_by(Task.status)
        ).all()
        sprint_tasks = {str(value): int(count) for value, count in sprint_task_rows}
        sprint_total = sum(sprint_tasks.values())
        active = {
            "id": str(active_sprint.id),
            "name": active_sprint.name,
            "status": active_sprint.status,
            "task_total": sprint_total,
            "task_completed": sprint_tasks.get("completed", 0),
            "progress_percent": round((sprint_tasks.get("completed", 0) / sprint_total) * 100, 2) if sprint_total else 0.0,
        }

    analysis_status = dict(_grouped_counts(db, ImpactAnalysis, ImpactAnalysis.status, project.id))
    analysis_total = _count(db, ImpactAnalysis, project.id)
    impact_rows = db.execute(
        select(ImpactAnalysisResult.impact_category, func.count(ImpactAnalysisResult.id))
        .join(ImpactAnalysis, ImpactAnalysis.id == ImpactAnalysisResult.impact_analysis_id)
        .where(ImpactAnalysis.project_id == project.id)
        .group_by(ImpactAnalysisResult.impact_category)
    ).all()
    impact_categories = {str(value): int(count) for value, count in impact_rows}

    personal = None
    if any(role.code == "developer" for role in user.roles):
        personal_task_status = dict(
            db.execute(
                select(Task.status, func.count())
                .where(Task.project_id == project.id, Task.assigned_to_user_id == user.id)
                .group_by(Task.status)
            ).all()
        )
        personal = {
            "tasks_total": sum(personal_task_status.values()),
            "tasks_completed": personal_task_status.get("completed", 0),
            "bugs_total": int(db.scalar(select(func.count()).select_from(Bug).where(Bug.project_id == project.id, Bug.assigned_to_user_id == user.id)) or 0),
        }
    elif any(role.code == "tester" for role in user.roles):
        personal = {
            "tasks_total": 0,
            "tasks_completed": 0,
            "bugs_total": int(db.scalar(select(func.count()).select_from(Bug).where(Bug.project_id == project.id, Bug.assigned_to_user_id == user.id)) or 0),
        }

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "progress_percent": progress,
            "progress_formula": "completed tasks / total tasks * 100; 0 when no tasks exist",
            "start_date": project.start_date,
            "end_date": project.end_date,
        },
        "requirements": {**_summary(sum(requirement_status.values()), requirement_status), "by_priority": requirement_priority},
        "milestones": _summary(sum(milestone_status.values()), milestone_status),
        "tasks": _summary(task_total, task_status),
        "sprints": {"total": sum(sprint_status.values()), "by_status": sprint_status, "active": active},
        "bugs": _summary(sum(bug_status.values()), bug_status),
        "bugs_by_severity": bug_severity,
        "test_cases": _summary(sum(test_status.values()), test_status),
        "change_requests": _summary(sum(change_status.values()), change_status),
        "impact_analysis": {
            "total_analyses": analysis_total,
            "by_status": analysis_status,
            "impacted_artifacts": sum(impact_categories.values()),
            "by_category": impact_categories,
        },
        "personal": personal,
        "generated_at": datetime.now(timezone.utc),
    }
