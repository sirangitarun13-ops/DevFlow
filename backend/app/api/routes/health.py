"""Root and service-health endpoints."""

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter()


@router.get("/", summary="API status")
def root() -> dict[str, str]:
    """Return basic service metadata without accessing the database."""

    return {
        "name": settings.app_name,
        "status": "ok",
        "environment": settings.app_environment,
    }


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    """Return process health; database connectivity is intentionally not probed yet."""

    return {
        "status": "ok",
        "service": "api",
        "database": "not_checked",
    }
