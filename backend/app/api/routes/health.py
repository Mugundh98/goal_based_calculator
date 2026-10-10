from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import DatabaseStatus, HealthResponse
from app.services.health import check_database

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[DatabaseStatus, Depends(check_database)],
) -> HealthResponse:
    """Report whether the API is running and can reach its database."""
    return HealthResponse(
        status="ok" if database.connected and database.pgvector else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
    )
