"""Project-scoped RCIA and change-request routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.core import accessible_project, managed_project
from backend.app.db.session import get_db
from backend.app.models.auth import User
from backend.app.schemas.rcia import ChangeRequestCreate, ChangeRequestRead, ChangeRequestUpdate, ImpactAnalysisRead, ImpactAnalysisResultRead
from backend.app.services import rcia_service


router = APIRouter(prefix="/projects")


def _validation_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


@router.post("/{project_id}/requirements/{requirement_id}/change-requests", response_model=ChangeRequestRead, status_code=status.HTTP_201_CREATED)
def create_change_request(project_id: UUID, requirement_id: UUID, data: ChangeRequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    try:
        return rcia_service.create_change_request(db, project_id, requirement_id, user.id, data.model_dump())
    except ValueError as error:
        raise _validation_error(error) from error


@router.get("/{project_id}/change-requests", response_model=list[ChangeRequestRead])
def list_change_requests(project_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    return rcia_service.list_change_requests(db, project_id, limit, offset)


@router.get("/{project_id}/change-requests/{change_request_id}", response_model=ChangeRequestRead)
def get_change_request(project_id: UUID, change_request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    try:
        return rcia_service.get_change_request(db, project_id, change_request_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{project_id}/change-requests/{change_request_id}", response_model=ChangeRequestRead)
def update_change_request(project_id: UUID, change_request_id: UUID, data: ChangeRequestUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    try:
        return rcia_service.update_change_request(db, project_id, change_request_id, user.id, data.status)
    except ValueError as error:
        raise _validation_error(error) from error


@router.post("/{project_id}/change-requests/{change_request_id}/analyses", response_model=ImpactAnalysisRead, status_code=status.HTTP_201_CREATED)
def run_impact_analysis(project_id: UUID, change_request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    managed_project(db, project_id, user)
    try:
        return rcia_service.run_analysis(db, project_id, change_request_id, user.id)
    except ValueError as error:
        raise _validation_error(error) from error


@router.get("/{project_id}/analyses/{analysis_id}", response_model=ImpactAnalysisRead)
def get_impact_analysis(project_id: UUID, analysis_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    try:
        return rcia_service.get_analysis(db, project_id, analysis_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{project_id}/analyses/{analysis_id}/results", response_model=list[ImpactAnalysisResultRead])
def get_impact_analysis_results(project_id: UUID, analysis_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accessible_project(db, project_id, user)
    try:
        return rcia_service.list_results(db, project_id, analysis_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
