"""Monte Carlo simulation of a goal: inputs from the goal (plus what-if overrides), return
history from the market data, the engine from `app/simulation`.

`run_simulation` is the single entry point: the API, the what-if sliders and (Phase 10) the
chatbot all call it.
"""

import time
from datetime import date
from functools import lru_cache
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.finance.goal_plan import GoalInputs, project_goal, suggested_return
from app.models.goal import Goal
from app.models.market import Fund, IndexHistory
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.simulation import (
    BandOut,
    ComparisonOut,
    ComparisonRequest,
    DeterministicOut,
    FinalValuesOut,
    HistoryOut,
    ModelComparisonOut,
    RequiredSipOut,
    SimulationInputsOut,
    SimulationOverrides,
    SimulationRead,
    SimulationRequest,
    SimulationResultOut,
    SimulationSummary,
)
from app.services.goals import risk_category
from app.simulation import engine
from app.simulation.allocation import equity_share_for_return, return_for_equity_share
from app.simulation.history import MIN_HISTORY_MONTHS, MarketHistory, align
from app.simulation.models import MODEL_NAMES, ModelName, NormalModel, ReturnModel, fit_model

PERCENT = 100

EQUITY_INDEX = "^CRSLDX"  # Nifty 500: the broad market, ~93% of listed market value
# Bond funds (old and new SEBI category names). Liquid, overnight and money market funds are
# left out (they behave like cash), and so are credit risk funds (defaults, side pockets).
DEBT_CATEGORIES = (
    "Corporate Bond Fund",
    "Banking and PSU Fund",
    "Banking and PSU Debt Fund",
    "Short Duration Fund",
    "Short Term Fund",
    "Medium Duration Fund",
    "Medium Term Fund",
    "Medium to Long Duration Fund",
    "Medium to Long Term Fund",
    "Gilt Fund",
    "Dynamic Bond",
    "Dynamic Term Fund",
)
MIN_FUNDS_PER_MONTH = 3


class SimulationUnavailable(Exception):
    """The run cannot be done: the goal is due, or the model needs market data that is missing."""


# --- Market history ---------------------------------------------------------------------------

# Last NAV (close) of each month, and the change from the previous month's. Months with a gap
# in a fund's history are skipped rather than counted as one long "month".
_MONTH_END = """
    SELECT DISTINCT ON ({key}, date_trunc('month', {day}))
           {key} AS series, date_trunc('month', {day})::date AS month, {value} AS value
    FROM {source}
    ORDER BY {key}, date_trunc('month', {day}), {day} DESC
"""
_RETURNS = """
    WITH monthly AS ({month_end}),
    returns AS (
        SELECT month, value / lag(value) OVER w - 1 AS r, lag(month) OVER w AS previous
        FROM monthly WINDOW w AS (PARTITION BY series ORDER BY month)
    )
    SELECT month, percentile_cont(0.5) WITHIN GROUP (ORDER BY r) AS r, count(*) AS n
    FROM returns
    WHERE previous = month - interval '1 month'
    GROUP BY month ORDER BY month
"""
EQUITY_SQL = _RETURNS.format(
    month_end=_MONTH_END.format(
        key="symbol",
        day="trade_date",
        value="close",
        source="index_history WHERE symbol = :symbol",
    )
)
DEBT_SQL = _RETURNS.format(
    month_end=_MONTH_END.format(
        key="n.fund_id",
        day="n.nav_date",
        value="n.nav",
        # Growth options only: an IDCW NAV drops on every payout, which is not a loss.
        source="nav_history n JOIN funds f ON f.id = n.fund_id "
        "WHERE f.asset_class = 'debt' AND f.option = 'growth' AND f.category = ANY(:categories)",
    )
)


def _fingerprint(db: Session) -> tuple:
    """Cheap summary of the data: when it changes, the cached history is rebuilt."""
    equity = db.execute(
        select(func.max(IndexHistory.trade_date), func.count()).where(
            IndexHistory.symbol == EQUITY_INDEX
        )
    ).one()
    debt = db.execute(
        select(func.max(Fund.latest_nav_date), func.count()).where(
            Fund.asset_class == "debt", Fund.category.in_(DEBT_CATEGORIES)
        )
    ).one()
    return (*equity, *debt)


_history_cache: dict[tuple, MarketHistory | None] = {}


def load_history(db: Session) -> MarketHistory | None:
    """Aligned monthly equity and debt returns, or None if there are fewer than 5 years."""
    equity_rows = db.execute(text(EQUITY_SQL), {"symbol": EQUITY_INDEX}).all()
    debt_rows = db.execute(text(DEBT_SQL), {"categories": list(DEBT_CATEGORIES)}).all()
    if not equity_rows or not debt_rows:
        return None
    equity = {row.month: float(row.r) for row in equity_rows}
    debt = {row.month: float(row.r) for row in debt_rows if row.n >= MIN_FUNDS_PER_MONTH}
    latest_month = max(row.month for row in equity_rows)
    months, equity_returns, debt_returns = align(equity, debt, latest_month)
    if len(months) < MIN_HISTORY_MONTHS:
        return None
    funds = max(row.n for row in debt_rows if row.month in set(months))
    return MarketHistory(
        months=tuple(months),
        equity=tuple(equity_returns),
        debt=tuple(debt_returns),
        equity_source=f"Nifty 500 ({EQUITY_INDEX}) month-end closes",
        debt_source=f"median monthly return of up to {funds} bond funds (growth option)",
    )


def market_history(db: Session) -> MarketHistory | None:
    key = _fingerprint(db)
    if key not in _history_cache:
        _history_cache.clear()
        _history_cache[key] = load_history(db)
    return _history_cache[key]


@lru_cache(maxsize=128)
def _fitted(model: ModelName, history: MarketHistory, equity_share: float) -> ReturnModel:
    """Fitting GARCH or the HMM takes up to a second; the sliders re-use the fitted model."""
    return fit_model(model, history.portfolio_log_returns(equity_share))


def return_model(
    model: ModelName, history: MarketHistory | None, equity_share: float
) -> ReturnModel:
    if history is None:
        if model == "normal":
            return NormalModel.assumed(equity_share)
        raise SimulationUnavailable(
            f"The {model} model needs at least {MIN_HISTORY_MONTHS // 12} years of market "
            "history; run the market data pipeline or use the normal model"
        )
    return _fitted(model, history, round(equity_share, 4))


# --- Inputs -----------------------------------------------------------------------------------


def resolve_inputs(
    goal: Goal, overrides: SimulationOverrides, category: str | None, today: date | None = None
) -> tuple[GoalInputs, SimulationInputsOut]:
    """The goal's inputs with what-if overrides applied, as fractions and as the API shows them."""
    target_year = overrides.target_year or goal.target_year
    years = target_year - (today or date.today()).year
    if years < 1:
        raise SimulationUnavailable("The goal is due this year: there is no time left to simulate")

    if overrides.equity_percent is not None:
        equity_share = float(overrides.equity_percent) / PERCENT
        annual_return, source = return_for_equity_share(equity_share), "allocation"
    else:
        if goal.expected_return is None:
            annual_return, source = suggested_return(category, years)
        else:
            annual_return, source = float(goal.expected_return) / PERCENT, "custom"
        equity_share = equity_share_for_return(annual_return)

    sip = overrides.monthly_sip if overrides.monthly_sip is not None else goal.monthly_sip
    step_up = overrides.step_up_rate if overrides.step_up_rate is not None else goal.step_up_rate
    inputs = GoalInputs(
        target_today=float(goal.target_amount),
        years=years,
        inflation_rate=float(goal.inflation_rate) / PERCENT,
        expected_return=annual_return,
        current_savings=float(
            goal.current_savings if overrides.current_savings is None else overrides.current_savings
        ),
        monthly_sip=float(sip),
        step_up_rate=float(step_up) / PERCENT,
    )
    shown = SimulationInputsOut(
        years=years,
        target_year=target_year,
        target_amount=inputs.target_today,
        inflation_rate=float(goal.inflation_rate),
        inflated_target=0.0,  # filled in from the projection below
        current_savings=inputs.current_savings,
        monthly_sip=inputs.monthly_sip,
        step_up_rate=float(step_up),
        expected_return=round(annual_return * PERCENT, 2),
        expected_return_source=source,
        equity_percent=round(equity_share * PERCENT, 1),
        equity_source="override" if overrides.equity_percent is not None else "implied",
    )
    return inputs, shown


def _deterministic(inputs: GoalInputs) -> DeterministicOut:
    projection = project_goal(inputs)
    return DeterministicOut(
        projected_value=projection.projected_value,
        funded_percent=projection.funded_percent,
        on_track=projection.on_track,
        required_sip=projection.required_sip,
    )


def history_out(history: MarketHistory | None) -> HistoryOut | None:
    if history is None:
        return None
    return HistoryOut(
        equity_source=history.equity_source,
        debt_source=history.debt_source,
        start=history.start,
        end=history.end,
        months=len(history.months),
    )


def _final(outcome: engine.SimulationOutcome) -> FinalValuesOut:
    values = {f"p{p}": round(v, 2) for p, v in outcome.final_percentiles.items()}
    return FinalValuesOut(**values, mean=round(outcome.final_mean, 2))


# --- Running ----------------------------------------------------------------------------------


def _run_model(
    model_name: ModelName,
    inputs: GoalInputs,
    history: MarketHistory | None,
    equity_share: float,
    paths: int,
    seed: int,
) -> tuple[engine.SimulationOutcome, ReturnModel, int]:
    started = time.perf_counter()
    model = return_model(model_name, history, equity_share)
    outcome = engine.run(inputs, model, paths=paths, seed=seed)
    return outcome, model, round((time.perf_counter() - started) * 1000)


def run_simulation(
    db: Session, user: User, goal: Goal, request: SimulationRequest, today: date | None = None
) -> SimulationResultOut:
    """Simulate one goal with one return model. Nothing is saved."""
    inputs, shown = resolve_inputs(goal, request.overrides, risk_category(db, user), today)
    history = market_history(db)
    seed = engine.DEFAULT_SEED if request.seed is None else request.seed
    outcome, model, elapsed = _run_model(
        request.model, inputs, history, shown.equity_percent / PERCENT, request.paths, seed
    )
    shown.inflated_target = round(outcome.target, 2)
    this_year = shown.target_year - shown.years
    return SimulationResultOut(
        model=request.model,
        paths=request.paths,
        seed=seed,
        inputs=shown,
        success_probability=round(outcome.success_probability * PERCENT, 1),
        final=_final(outcome),
        median_shortfall=None
        if outcome.median_shortfall is None
        else round(outcome.median_shortfall, 2),
        required_sip=[
            RequiredSipOut(probability=level, monthly_sip=sip)
            for level, sip in outcome.required_sip.items()
        ],
        deterministic=_deterministic(inputs),
        annual_volatility=round(model.annual_volatility * PERCENT, 2),
        model_details=model.details(),
        history=history_out(history),
        bands=[
            BandOut(
                year=band.year,
                calendar_year=this_year + band.year,
                **{f"p{p}": round(v, 2) for p, v in band.percentiles.items()},
                deterministic=round(band.deterministic, 2),
            )
            for band in outcome.bands
        ],
        elapsed_ms=elapsed,
    )


def compare_models(
    db: Session, user: User, goal: Goal, request: ComparisonRequest, today: date | None = None
) -> ComparisonOut:
    """All four models on the same inputs and the same seed."""
    inputs, shown = resolve_inputs(goal, request.overrides, risk_category(db, user), today)
    history = market_history(db)
    seed = engine.DEFAULT_SEED if request.seed is None else request.seed
    names = MODEL_NAMES if history is not None else ("normal",)
    results = []
    for name in names:
        outcome, model, elapsed = _run_model(
            name, inputs, history, shown.equity_percent / PERCENT, request.paths, seed
        )
        shown.inflated_target = round(outcome.target, 2)
        results.append(
            ModelComparisonOut(
                model=name,
                success_probability=round(outcome.success_probability * PERCENT, 1),
                final=_final(outcome),
                required_sip_90=outcome.required_sip[90],
                annual_volatility=round(model.annual_volatility * PERCENT, 2),
                elapsed_ms=elapsed,
            )
        )
    return ComparisonOut(
        paths=request.paths,
        seed=seed,
        inputs=shown,
        deterministic=_deterministic(inputs),
        history=history_out(history),
        models=results,
    )


# --- Saved runs -------------------------------------------------------------------------------

# Fields of SimulationResultOut kept in `simulations.parameters`; the rest live in the result row.
_PARAMETER_FIELDS = (
    "paths",
    "seed",
    "inputs",
    "deterministic",
    "annual_volatility",
    "model_details",
    "history",
)


def save_simulation(db: Session, goal: Goal, result: SimulationResultOut) -> Simulation:
    data = result.model_dump(mode="json")
    simulation = Simulation(
        goal_id=goal.id,
        model=result.model,
        parameters={name: data[name] for name in _PARAMETER_FIELDS},
        result=SimulationResult(
            success_probability=result.success_probability,
            median_final=result.final.p50,
            median_shortfall=result.median_shortfall,
            final_percentiles=data["final"],
            required_sip=data["required_sip"],
            bands=data["bands"],
            elapsed_ms=result.elapsed_ms,
        ),
    )
    db.add(simulation)
    db.commit()
    db.refresh(simulation)
    return simulation


def to_read(simulation: Simulation) -> SimulationRead:
    result = simulation.result
    stored: dict[str, Any] = simulation.parameters
    return SimulationRead(
        id=simulation.id,
        goal_id=simulation.goal_id,
        run_at=simulation.run_at,
        model=simulation.model,
        **{name: stored[name] for name in _PARAMETER_FIELDS},
        success_probability=result.success_probability,
        final=result.final_percentiles,
        median_shortfall=result.median_shortfall,
        required_sip=result.required_sip,
        bands=result.bands,
        elapsed_ms=result.elapsed_ms,
    )


def to_summary(simulation: Simulation) -> SimulationSummary:
    inputs = simulation.parameters["inputs"]
    return SimulationSummary(
        id=simulation.id,
        goal_id=simulation.goal_id,
        model=simulation.model,
        run_at=simulation.run_at,
        success_probability=simulation.result.success_probability,
        median_final=simulation.result.median_final,
        inflated_target=inputs["inflated_target"],
        years=inputs["years"],
        monthly_sip=inputs["monthly_sip"],
        equity_percent=inputs["equity_percent"],
    )


def list_simulations(db: Session, goal: Goal) -> list[Simulation]:
    """Saved runs of a goal, newest first."""
    query = (
        select(Simulation)
        .where(Simulation.goal_id == goal.id)
        .order_by(Simulation.run_at.desc(), Simulation.id.desc())
    )
    return list(db.scalars(query).unique())


def get_simulation(db: Session, user: User, simulation_id: int) -> Simulation | None:
    """None both when the run does not exist and when its goal belongs to someone else."""
    query = (
        select(Simulation)
        .join(Goal, Goal.id == Simulation.goal_id)
        .where(Simulation.id == simulation_id, Goal.user_id == user.id)
    )
    return db.scalars(query).unique().one_or_none()


def delete_simulation(db: Session, simulation: Simulation) -> None:
    db.delete(simulation)
    db.commit()
