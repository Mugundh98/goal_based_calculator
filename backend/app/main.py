"""FastAPI application entry point. Run with: uv run uvicorn app.main:app --reload"""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.data_pipeline.scheduler import create_scheduler
from app.simulation.models import preload_fitting_libraries

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start the market data scheduler with the app (if enabled) and stop it on shutdown."""
    # Importing arch/hmmlearn (pandas, scipy) takes seconds; do it now, not on the first run.
    threading.Thread(target=preload_fitting_libraries, daemon=True).start()
    scheduler = create_scheduler() if settings.scheduler_enabled else None
    if scheduler:
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
