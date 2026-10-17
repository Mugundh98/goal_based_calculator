from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SleeveOut(BaseModel):
    sleeve: str
    label: str
    weight: float  # percent of the goal's money


class FundPickOut(BaseModel):
    fund_id: int
    name: str
    amc: str
    sleeve: str
    sleeve_label: str
    peer_group: str
    peer_label: str
    weight: float  # percent of the goal's money
    basis: str  # "model" (Phase 7 ranker) or "sharpe" (fallback)
    reason: str
    predicted_quartile: int | None
    prob_top: float | None


class FrontierPoint(BaseModel):
    volatility: float  # percent
    expected_return: float  # percent


class SleeveMarketOut(BaseModel):
    sleeve: str
    label: str
    expected_return: float  # percent, planning assumption
    volatility: float  # percent, estimated
    funds: int  # funds in the median at the latest month


class CapitalMarketOut(BaseModel):
    sleeves: list[SleeveMarketOut]
    correlation: list[list[float]]
    months: int
    start: date
    end: date


class RecommendationInputs(BaseModel):
    capital_market: CapitalMarketOut
    frontier: list[FrontierPoint]
    base_equity: float  # percent, before the glide
    risk_aversion: float
    mid_small_limit: float  # percent of the equity
    short_debt_minimum: float  # percent of the debt
    goal_return: float | None  # percent the goal assumes now
    fund_model: str | None  # e.g. "fund_ranker v2"; None = Sharpe fallback
    notes: list[str]


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    created_at: datetime
    as_of: date
    risk_category: str | None
    years_to_goal: int
    equity_share: float  # percent
    expected_return: float  # percent
    volatility: float  # percent
    allocation: list[SleeveOut]
    funds: list[FundPickOut]
    reasons: list[str]
    inputs: RecommendationInputs


class RecommendationSummary(BaseModel):
    id: int
    created_at: datetime
    as_of: date
    risk_category: str | None
    years_to_goal: int
    equity_share: float
    expected_return: float
    funds: int
