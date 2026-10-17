from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.finance.goal_plan import ReturnSource
from app.schemas.goal import PercentIn, check_target_year
from app.schemas.profile import MoneyIn
from app.simulation.engine import DEFAULT_PATHS
from app.simulation.models import ModelName

MIN_PATHS = 500
SimulationReturnSource = ReturnSource | Literal["allocation"]


class SimulationOverrides(BaseModel):
    """What-if changes to a goal for one run; anything left out comes from the saved goal."""

    monthly_sip: MoneyIn | None = None
    # Phase 10: start from a different amount, e.g. the goal's recorded investments.
    current_savings: MoneyIn | None = None
    step_up_rate: PercentIn(50) | None = None
    target_year: int | None = None
    # Share of the goal's money in equity, %; also sets the expected return (13% / 7% blend).
    equity_percent: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] | None = None

    @field_validator("target_year")
    @classmethod
    def in_the_future(cls, value: int | None) -> int | None:
        return None if value is None else check_target_year(value)


class ComparisonRequest(BaseModel):
    paths: int = Field(default=DEFAULT_PATHS, ge=MIN_PATHS, le=DEFAULT_PATHS)
    # None = the default seed, so the same inputs always give the same answer.
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    overrides: SimulationOverrides = SimulationOverrides()


class SimulationRequest(ComparisonRequest):
    model: ModelName = "bootstrap"


class SimulationInputsOut(BaseModel):
    """The inputs the run actually used, after overrides and automatic choices."""

    years: int
    target_year: int
    target_amount: float  # today's rupees
    inflation_rate: float  # percent
    inflated_target: float
    current_savings: float
    monthly_sip: float
    step_up_rate: float  # percent
    expected_return: float  # percent: the median compound growth rate
    expected_return_source: SimulationReturnSource
    equity_percent: float
    equity_source: Literal["implied", "override"]


class DeterministicOut(BaseModel):
    """The Phase 3 projection with the same inputs, for comparison."""

    projected_value: float
    funded_percent: float
    on_track: bool
    required_sip: float | None


class FinalValuesOut(BaseModel):
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    mean: float


class RequiredSipOut(BaseModel):
    probability: int  # percent of paths that reach the target
    monthly_sip: float  # starting SIP, whole rupees


class BandOut(BaseModel):
    year: int  # years from now
    calendar_year: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    deterministic: float


class HistoryOut(BaseModel):
    equity_source: str
    debt_source: str
    start: date
    end: date
    months: int


class SimulationResultOut(BaseModel):
    model: ModelName
    paths: int
    seed: int
    inputs: SimulationInputsOut
    success_probability: float  # percent
    final: FinalValuesOut
    median_shortfall: float | None  # typical gap of the paths that fall short
    required_sip: list[RequiredSipOut]
    deterministic: DeterministicOut
    annual_volatility: float  # percent, of the simulated portfolio
    model_details: dict[str, Any]
    history: HistoryOut | None  # None: volatility from fixed assumptions (no market data)
    bands: list[BandOut]
    elapsed_ms: int


class SimulationRead(SimulationResultOut):
    id: int
    goal_id: int
    run_at: datetime


class SimulationSummary(BaseModel):
    id: int
    goal_id: int
    model: ModelName
    run_at: datetime
    success_probability: float
    median_final: float
    inflated_target: float
    years: int
    monthly_sip: float
    equity_percent: float


class ModelComparisonOut(BaseModel):
    model: ModelName
    success_probability: float
    final: FinalValuesOut
    required_sip_90: float
    annual_volatility: float
    elapsed_ms: int


class ComparisonOut(BaseModel):
    paths: int
    seed: int
    inputs: SimulationInputsOut
    deterministic: DeterministicOut
    history: HistoryOut | None
    models: list[ModelComparisonOut]
