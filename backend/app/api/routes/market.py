from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.deps import Audit, CurrentUser, DbSession, require_admin
from app.data_pipeline.cpi import DEFAULT_BASE_YEAR
from app.data_pipeline.indices import INDICES
from app.data_pipeline.jobs import JOBS, run_job
from app.models.user import User
from app.schemas.market import (
    IndexHistoryOut,
    InflationOut,
    JobRunOut,
    MarketSummary,
)
from app.services import market as service

router = APIRouter(prefix="/market", tags=["market data"])


@router.get("/summary", response_model=MarketSummary)
def summary(_: CurrentUser, db: DbSession) -> MarketSummary:
    """Freshness of every data set, index levels and the latest inflation figure."""
    return service.summary(db)


@router.get("/indices/{symbol}/history", response_model=IndexHistoryOut)
def index_history(
    symbol: str, _: CurrentUser, db: DbSession, start: date | None = None
) -> IndexHistoryOut:
    """Daily closes of a benchmark index (e.g. ^NSEI) from `start`, oldest first."""
    if symbol not in INDICES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown index")
    return IndexHistoryOut(
        symbol=symbol, name=INDICES[symbol], points=service.index_history(db, symbol, start)
    )


@router.get("/inflation", response_model=InflationOut)
def inflation(_: CurrentUser, db: DbSession) -> InflationOut:
    """Monthly All-India CPI with year-on-year inflation."""
    return InflationOut(base_year=DEFAULT_BASE_YEAR, points=service.inflation_series(db))


@router.get("/jobs", response_model=list[JobRunOut])
def job_runs(
    _: CurrentUser,
    db: DbSession,
    job_name: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[JobRunOut]:
    """The pipeline log, newest first."""
    return [JobRunOut.model_validate(run) for run in service.recent_runs(db, limit, job_name)]


@router.post("/jobs/{job_name}/run", status_code=status.HTTP_202_ACCEPTED)
def start_job(
    job_name: str,
    background: BackgroundTasks,
    admin: Annotated[User, Depends(require_admin)],
    audit: Audit,
) -> dict[str, str]:
    """Admin only: run a pipeline job now, in the background. Watch it in GET /jobs."""
    if job_name not in JOBS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown job")
    background.add_task(run_job, job_name, "admin")
    audit("admin.job.run", admin, details={"job": job_name})
    return {"detail": f"{job_name} started"}
