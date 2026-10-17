from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class UserCounts(BaseModel):
    total: int
    active: int
    admins: int
    new_last_7_days: int


class ActivityCounts(BaseModel):
    goals: int
    transactions: int
    saved_simulations: int
    recommendations: int
    logins_7_days: int
    failed_logins_7_days: int


class JobStatus(BaseModel):
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_written: int


class ActiveModel(BaseModel):
    name: str
    version: int
    trained_at: datetime


class ToolUsage(BaseModel):
    tool: str
    calls: int
    errors: int
    average_ms: float


class AssistantStats(BaseModel):
    questions_7_days: int
    answers_7_days: int
    fallback_answers_7_days: int  # the model was unavailable or rate-limited
    answers_with_ungrounded_numbers_7_days: int
    tools: list[ToolUsage]  # last 7 days


class AdminOverview(BaseModel):
    users: UserCounts
    activity: ActivityCounts
    funds: int
    latest_nav_date: date | None
    jobs: list[JobStatus]  # the latest run of each job
    models: list[ActiveModel]
    assistant: AssistantStats


class AdminUserRow(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    goals: int


class AdminUserPage(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    actor_id: int | None
    actor_email: str | None
    action: str
    description: str
    entity_type: str | None
    entity_id: int | None
    details: dict[str, Any]
    ip_address: str | None


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    total: int
    page: int
    page_size: int


class ModelVersionOut(BaseModel):
    id: int
    name: str
    version: int
    algorithm: str
    data_start: date
    data_end: date
    trained_at: datetime
    is_active: bool
    headline: dict[str, Any]  # a few validation numbers
