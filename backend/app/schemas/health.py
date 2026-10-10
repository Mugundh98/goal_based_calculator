from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    connected: bool
    pgvector: bool
    error: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" when every dependency is reachable, otherwise "degraded"
    app: str
    version: str
    environment: str
    database: DatabaseStatus
