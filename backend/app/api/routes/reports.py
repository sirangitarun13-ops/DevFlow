"""Project-scoped dynamic PDF report endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.core import accessible_project
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.services.pdf_service import render_report
from backend.app.services.report_service import build_change_impact_report, build_project_report

router = APIRouter(prefix="/projects")


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{project_id}/reports/project-summary")
def project_summary_report(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    return _pdf(render_report(build_project_report(db, project, user, "project-summary")), f"devflow-{project_id}-project-summary.pdf")


@router.get("/{project_id}/reports/sdlc-status")
def sdlc_status_report(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    return _pdf(render_report(build_project_report(db, project, user, "sdlc-status")), f"devflow-{project_id}-sdlc-status.pdf")


@router.get("/{project_id}/reports/change-impact/{change_request_id}")
def change_impact_report(project_id: UUID, change_request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = accessible_project(db, project_id, user)
    try:
        report = build_change_impact_report(db, project, user, change_request_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _pdf(render_report(report), f"devflow-{project_id}-change-impact-{change_request_id}.pdf")
