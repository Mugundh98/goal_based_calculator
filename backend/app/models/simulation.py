"""Saved Monte Carlo runs (Phase 5).

Unlike goal projections (computed on every read), a simulation run is stored as a snapshot: it
is random (reproducible only with its seed), depends on market data that changes every day and
takes a noticeable fraction of a second. Saving it records exactly what the user was shown.

`simulations` holds what was asked (model, inputs, seed, fitted parameters) and is small;
`simulation_results` holds the bulky output (percentile bands as JSON). One-to-one, sharing the
primary key, so a list of runs never has to load the bands.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

SIMULATION_MODELS = ("normal", "bootstrap", "garch", "hmm")


class Simulation(Base):
    """One run of the Monte Carlo engine for a goal: the question."""

    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "model IN ('normal', 'bootstrap', 'garch', 'hmm')", name="ck_simulations_model"
        ),
        # Serves the only query: the runs of one goal, newest first.
        Index("ix_simulations_goal_id_run_at", "goal_id", "run_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(20))
    # Resolved inputs (after what-if overrides), paths, seed, fitted model and data window.
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    result: Mapped["SimulationResult"] = relationship(
        back_populates="simulation", cascade="all, delete-orphan", lazy="joined"
    )


class SimulationResult(Base):
    """The answer to one run: success probability and percentile bands."""

    __tablename__ = "simulation_results"
    __table_args__ = (
        CheckConstraint(
            "success_probability BETWEEN 0 AND 100", name="ck_simulation_results_probability"
        ),
    )

    # Shared primary key = one-to-one with `simulations`.
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True
    )
    success_probability: Mapped[float] = mapped_column(Float)  # percent of paths that succeed
    median_final: Mapped[float] = mapped_column(Float)  # P50 of the value at the goal date
    median_shortfall: Mapped[float | None] = mapped_column(Float)
    final_percentiles: Mapped[dict[str, float]] = mapped_column(JSONB)
    required_sip: Mapped[list[dict[str, float]]] = mapped_column(JSONB)
    bands: Mapped[list[dict[str, float]]] = mapped_column(JSONB)  # one entry per year
    elapsed_ms: Mapped[int] = mapped_column(Integer)

    simulation: Mapped[Simulation] = relationship(back_populates="result")
