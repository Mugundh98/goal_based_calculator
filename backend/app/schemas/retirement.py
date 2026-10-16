from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.finance.goal_plan import ReturnSource
from app.schemas.goal import PercentIn
from app.schemas.profile import MoneyIn
from app.schemas.simulation import MIN_PATHS, HistoryOut
from app.simulation.engine import DEFAULT_PATHS
from app.simulation.models import ModelName

MAX_RETIREMENT_YEARS = 50  # keeps a lifetime simulation within a few hundred MB


class RetirementInput(BaseModel):
    """Everything the planner asks. Ages are checked against the profile's date of birth too."""

    retirement_age: int = Field(default=60, ge=30, le=80)
    life_expectancy: int = Field(default=85, ge=50, le=105)  # plan until this age
    # Household spending in retirement, per month, in today's rupees.
    monthly_expense: Annotated[Decimal, Field(gt=0, lt=Decimal("1e10"), decimal_places=2)]
    inflation_rate: PercentIn(20) = Decimal(6)
    # None = automatic: from the latest risk profile and the years to retirement (as goals).
    pre_retirement_return: PercentIn(30) | None = None
    post_retirement_return: PercentIn(30) = Decimal(8)
    current_savings: MoneyIn = Decimal(0)  # already set aside for retirement (EPF, PPF, NPS, MF)
    monthly_sip: MoneyIn = Decimal(0)
    step_up_rate: PercentIn(50) = Decimal(0)

    @model_validator(mode="after")
    def plausible_horizon(self) -> "RetirementInput":
        if self.life_expectancy <= self.retirement_age:
            raise ValueError("Life expectancy must be above the retirement age")
        if self.life_expectancy - self.retirement_age > MAX_RETIREMENT_YEARS:
            raise ValueError(f"Plan for at most {MAX_RETIREMENT_YEARS} years of retirement")
        return self


class RetirementSimulationRequest(RetirementInput):
    model: ModelName = "bootstrap"
    paths: int = Field(default=DEFAULT_PATHS, ge=MIN_PATHS, le=DEFAULT_PATHS)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)  # None = the default seed


class AccumulationOut(BaseModel):
    """The savings phase: a goal whose target is the corpus (Phase 3 projection)."""

    savings_value: float
    sip_value: float
    projected_value: float  # corpus the current plan reaches at retirement
    shortfall: float
    required_sip: float | None
    funded_percent: float
    on_track: bool


class LifetimeYearOut(BaseModel):
    year: int  # years from now
    calendar_year: int
    age: int  # age at the end of that year
    balance: float
    phase: Literal["accumulation", "retirement"]


class RetirementProjectionOut(BaseModel):
    current_age: int
    years_to_retirement: int
    retirement_year: int
    retirement_years: int
    pre_retirement_return_used: float  # percent
    pre_retirement_return_source: ReturnSource
    post_retirement_return: float  # percent
    real_post_return: float  # percent, after inflation
    first_monthly_withdrawal: float  # first month of retirement, in rupees of that year
    corpus_needed: float  # at retirement
    corpus_needed_today: float  # the same corpus in today's money
    corpus_multiple: float  # corpus / first year's spending
    withdrawal_rate: float  # percent: first year's spending / corpus
    bengen_corpus: float  # what the 4% rule would ask for: 25 x first year's spending
    accumulation: AccumulationOut
    money_lasts_until: float | None  # age the current plan runs out (None: lasts)
    lifetime: list[LifetimeYearOut]


class RetirementPlanRead(BaseModel):
    """The saved inputs (stored as exact NUMERIC, sent as JSON numbers) and the projection."""

    retirement_age: int
    life_expectancy: int
    monthly_expense: float
    inflation_rate: float
    pre_retirement_return: float | None
    post_retirement_return: float
    current_savings: float
    monthly_sip: float
    step_up_rate: float
    goal_id: int
    created_at: datetime
    updated_at: datetime
    projection: RetirementProjectionOut


class ReturnPhaseOut(BaseModel):
    expected_return: float  # percent (median growth, ADR-008)
    equity_percent: float  # implied by the return (13% / 7% blend)
    annual_volatility: float  # percent, of the fitted model


class SurvivalOut(BaseModel):
    age: int
    probability: float  # percent of paths with money left at that age


class LevelSipOut(BaseModel):
    probability: int
    monthly_sip: float


class LevelCorpusOut(BaseModel):
    probability: int
    corpus: float


class LifetimeBandOut(BaseModel):
    year: int
    calendar_year: int
    age: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    deterministic: float


class CorpusPercentilesOut(BaseModel):
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


class RetirementSimulationOut(BaseModel):
    model: ModelName
    paths: int
    seed: int
    success_probability: float  # percent: money lasts until life expectancy
    corpus_at_retirement: CorpusPercentilesOut
    corpus_target: float  # single-return corpus needed
    survival: list[SurvivalOut]
    depletion_age_p10: float  # 1 in 10 paths have run out by this age (= life expectancy: never)
    median_depletion_age: float | None  # among paths that run out
    required_sip: list[LevelSipOut]
    corpus_needed: list[LevelCorpusOut]
    before_retirement: ReturnPhaseOut
    after_retirement: ReturnPhaseOut
    history: HistoryOut | None
    bands: list[LifetimeBandOut]
    as_of: date
    elapsed_ms: int
