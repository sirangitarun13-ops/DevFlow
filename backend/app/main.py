"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.core import router as core_router
from backend.app.api.routes.traceability import router as traceability_router
from backend.app.api.routes.rcia import router as rcia_router
from backend.app.api.routes.analytics import router as analytics_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.users import router as users_router
from backend.app.core.config import settings
from backend.app.core.rate_limit import get_limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(
    title=settings.app_name,
    description="Backend foundation for the DevFlow SDLC analytics platform.",
    version="0.1.0",
)

app.state.limiter = get_limiter()
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Service status", tags=["system"])
def root() -> dict[str, str]:
    """Return basic service metadata at the application root."""

    return {
        "name": settings.app_name,
        "status": "ok",
        "environment": settings.app_environment,
    }


app.include_router(
    health_router,
    prefix=settings.api_v1_prefix,
    tags=["system"],
)

app.include_router(
    core_router,
    prefix=settings.api_v1_prefix,
    tags=["core-sdlc"],
)

app.include_router(
    traceability_router,
    prefix=settings.api_v1_prefix,
    tags=["traceability"],
)

app.include_router(
    rcia_router,
    prefix=settings.api_v1_prefix,
    tags=["rcia"],
)

app.include_router(
    analytics_router,
    prefix=settings.api_v1_prefix,
    tags=["analytics"],
)

app.include_router(
    reports_router,
    prefix=settings.api_v1_prefix,
    tags=["reports"],
)

app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
    tags=["authentication"],
)

app.include_router(
    users_router,
    prefix=settings.api_v1_prefix,
    tags=["users"],
)
