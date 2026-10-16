"""Machine-learning models and their outputs (Phase 7).

`ml_models` is a registry: every training run adds a new VERSION of a named model with its
metrics, and exactly one version per name is active (a partial unique index, as job_runs uses
for running jobs). Predictions and cluster assignments are written by a batch scoring job and
reference the model version that produced them, so every number shown can be traced back.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

MODEL_NAMES = ("fund_ranker", "fund_clusters", "inflation_forecast")


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        CheckConstraint(
            "name IN ('fund_ranker', 'fund_clusters', 'inflation_forecast')",
            name="ck_ml_models_name",
        ),
        UniqueConstraint("name", "version", name="uq_ml_models_name_version"),
        # At most ONE active version per model name, enforced by the database.
        Index("uq_ml_models_one_active", "name", unique=True, postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    algorithm: Mapped[str] = mapped_column(String(80))
    # Hyper-parameters, or the whole model when it is just numbers (cluster centroids).
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)  # validation results, forecasts
    features: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")  # input order
    file_path: Mapped[str | None] = mapped_column(String(255))  # model file, if any
    data_start: Mapped[date] = mapped_column(Date)
    data_end: Mapped[date] = mapped_column(Date)  # last month of data used
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")


class FundPrediction(Base):
    """The ranker's view of one fund: next-12-month quartile within its peer group."""

    __tablename__ = "fund_predictions"
    __table_args__ = (
        CheckConstraint("predicted_quartile BETWEEN 1 AND 4", name="ck_fund_predictions_quartile"),
        CheckConstraint("prob_top BETWEEN 0 AND 1", name="ck_fund_predictions_prob_top"),
        # The rankings page: one peer group of one model, best first.
        Index("ix_fund_predictions_model_peer", "model_id", "peer_group", "expected_quartile"),
    )

    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="CASCADE"), primary_key=True
    )
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True
    )
    as_of: Mapped[date] = mapped_column(Date)  # month-end the features describe
    peer_group: Mapped[str] = mapped_column(String(30))
    predicted_quartile: Mapped[int] = mapped_column(SmallInteger)  # most likely quartile
    prob_top: Mapped[float] = mapped_column(Float)  # P(top quartile)
    probabilities: Mapped[list[float]] = mapped_column(JSONB)  # P(Q1) .. P(Q4)
    expected_quartile: Mapped[float] = mapped_column(Float)  # sum q x P(q): the ranking score
    peer_rank: Mapped[int] = mapped_column(Integer)  # 1 = best in the peer group
    peer_size: Mapped[int] = mapped_column(Integer)
    # Top SHAP factors for "top quartile": [{feature, label, value, contribution}, ...]
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)


class FundCluster(Base):
    """Which behaviour cluster a fund belongs to, with the two numbers the scatter plot shows."""

    __tablename__ = "fund_clusters"

    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="CASCADE"), primary_key=True
    )
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True
    )
    as_of: Mapped[date] = mapped_column(Date)
    cluster: Mapped[int] = mapped_column(SmallInteger)
    distance: Mapped[float] = mapped_column(Float)  # to the cluster centre (standardised units)
    volatility: Mapped[float] = mapped_column(Float)  # annual, last 3 years (x axis)
    return_3y: Mapped[float] = mapped_column(Float)  # CAGR, last 3 years (y axis)
