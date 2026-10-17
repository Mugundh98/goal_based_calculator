from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recommendation(Base):
    """A recommendation for one goal, stored as a snapshot: what the user was told and why.

    Unlike goal projections (recomputed on every read), a recommendation depends on market data,
    the fund rankings and the risk profile of that day; keeping it lets the user (and an
    auditor) see later exactly what was advised, and how advice changed over time.
    """

    __tablename__ = "recommendations"
    # "Latest recommendation for a goal" and the history list: one index serves both.
    __table_args__ = (Index("ix_recommendations_goal_created", "goal_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    as_of: Mapped[date] = mapped_column(Date)  # last month of market data used
    risk_category: Mapped[str | None] = mapped_column(String(20))
    years_to_goal: Mapped[int] = mapped_column(SmallInteger)
    equity_share: Mapped[float] = mapped_column(Float)  # fraction
    expected_return: Mapped[float] = mapped_column(Float)  # fraction a year
    volatility: Mapped[float] = mapped_column(Float)  # fraction a year
    allocation: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # per sleeve
    funds: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # picks with reasons
    reasons: Mapped[list[str]] = mapped_column(JSONB)  # why this allocation
    # Assumptions behind it: capital market (returns, risk), rules, model versions, frontier.
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
