"""Recommendations: an allocation and fund picks for one goal, stored as a snapshot.

Data: each sleeve's monthly return is the median month-on-month return of its direct-growth
funds (the same SQL pattern as the Phase 5 debt series), aligned on common months; the result is
cached until the market data changes. Picks come from the ACTIVE Phase 7 ranker, or from the
Phase 4 Sharpe ratios when no ranker has been trained.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ml.peers import LABELS as PEER_LABELS
from app.ml.peers import peer_group
from app.ml.registry import active
from app.models.goal import Goal
from app.models.market import Fund, FundMetrics
from app.models.ml import FundPrediction
from app.models.recommendation import Recommendation
from app.models.user import User
from app.recommendation import allocation as alloc
from app.recommendation.selection import (
    SLEEVE_PEERS,
    Candidate,
    allocation_reasons,
    pick_funds,
)
from app.schemas.recommendation import (
    CapitalMarketOut,
    FrontierPoint,
    FundPickOut,
    RecommendationInputs,
    RecommendationRead,
    RecommendationSummary,
    SleeveMarketOut,
    SleeveOut,
)
from app.services.funds import active_since
from app.services.goals import calculate, risk_category
from app.services.simulations import _MONTH_END
from app.simulation.history import MIN_HISTORY_MONTHS

PERCENT = 100
MIN_FUNDS_PER_MONTH = 3

_SLEEVE_SQL = """
    WITH monthly AS ({month_end}),
    returns AS (
        SELECT month, value / lag(value) OVER w - 1 AS r, lag(month) OVER w AS previous
        FROM monthly WINDOW w AS (PARTITION BY series ORDER BY month)
    )
    SELECT month, percentile_cont(0.5) WITHIN GROUP (ORDER BY r) AS r, count(*) AS n
    FROM returns WHERE previous = month - interval '1 month'
    GROUP BY month ORDER BY month
""".format(
    month_end=_MONTH_END.format(
        key="n.fund_id",
        day="n.nav_date",
        value="n.nav",
        source="nav_history n JOIN funds f ON f.id = n.fund_id WHERE f.plan = 'direct' "
        "AND f.option = 'growth' AND f.category = ANY(:categories)",
    )
)


class RecommendationUnavailable(Exception):
    """Not enough market data to estimate risk (run the market data pipeline)."""


@dataclass(frozen=True)
class SleeveHistory:
    market: alloc.CapitalMarket
    months: tuple[date, ...]
    funds: dict[str, int]  # funds in each sleeve's median at the latest month


def sleeve_categories(db: Session) -> dict[str, list[str]]:
    """AMFI category labels of each sleeve, through the Phase 7 peer groups."""
    categories = db.scalars(select(Fund.category).distinct()).all()
    return {
        sleeve: [c for c in categories if peer_group(c) in peers]
        for sleeve, peers in SLEEVE_PEERS.items()
    }


def load_history(db: Session) -> SleeveHistory | None:
    series: dict[str, dict[date, float]] = {}
    counts: dict[str, dict[date, int]] = {}
    for sleeve, categories in sleeve_categories(db).items():
        rows = db.execute(text(_SLEEVE_SQL), {"categories": categories}).all()
        series[sleeve] = {r.month: float(r.r) for r in rows if r.n >= MIN_FUNDS_PER_MONTH}
        counts[sleeve] = {r.month: int(r.n) for r in rows}
    common = sorted(set.intersection(*(set(s) for s in series.values())))
    if not common:
        return None
    common = common[:-1]  # the newest month is incomplete
    if len(common) < MIN_HISTORY_MONTHS:
        return None
    returns = np.array([[series[s][m] for s in alloc.SLEEVES] for m in common])
    return SleeveHistory(
        market=alloc.capital_market(returns),
        months=tuple(common),
        funds={s: counts[s][common[-1]] for s in alloc.SLEEVES},
    )


_cache: dict[tuple, SleeveHistory | None] = {}


def sleeve_history(db: Session) -> SleeveHistory | None:
    """Cached until the market data changes (newest NAV date, number of funds)."""
    key = tuple(db.execute(select(func.max(Fund.latest_nav_date), func.count(Fund.id))).one())
    if key not in _cache:
        _cache.clear()
        _cache[key] = load_history(db)
    return _cache[key]


# --- Candidates -------------------------------------------------------------------------------


def _top_factor(factors: list[dict]) -> str | None:
    """The strongest reason that RAISES the chance of a top-quartile year."""
    positive = [f for f in factors if f["contribution"] > 0]
    return max(positive, key=lambda f: f["contribution"])["label"] if positive else None


def candidates(db: Session) -> tuple[dict[str, list[Candidate]], str | None]:
    """Eligible funds per sleeve (active direct-growth funds), and the ranker used if any."""
    since = active_since(db)
    by_peer = {p: s for s, peers in SLEEVE_PEERS.items() for p in peers}
    out: dict[str, list[Candidate]] = {s: [] for s in alloc.SLEEVES}
    ranker = active(db, "fund_ranker")
    if ranker is not None:
        rows = db.execute(
            select(FundPrediction, Fund)
            .join(Fund, Fund.id == FundPrediction.fund_id)
            .where(
                FundPrediction.model_id == ranker.id,
                FundPrediction.peer_group.in_(by_peer),
                Fund.latest_nav_date >= since,
            )
        ).all()
        for p, f in rows:
            out[by_peer[p.peer_group]].append(
                Candidate(
                    fund_id=f.id,
                    name=f.name,
                    amc=f.amc,
                    peer_group=p.peer_group,
                    expected_quartile=p.expected_quartile,
                    prob_top=p.prob_top,
                    predicted_quartile=p.predicted_quartile,
                    peer_rank=p.peer_rank,
                    peer_size=p.peer_size,
                    top_factor=_top_factor(p.factors),
                )
            )
        if any(out.values()):
            return out, f"fund_ranker v{ranker.version}"
    rows = db.execute(
        select(Fund, FundMetrics.sharpe)
        .join(FundMetrics, FundMetrics.fund_id == Fund.id)
        .where(
            Fund.plan == "direct",
            Fund.option == "growth",
            Fund.latest_nav_date >= since,
            FundMetrics.sharpe.is_not(None),
            FundMetrics.return_3y.is_not(None),  # a full three years behind the Sharpe ratio
        )
    ).all()
    for f, sharpe in rows:
        group = peer_group(f.category)
        if group in by_peer:
            out[by_peer[group]].append(
                Candidate(f.id, f.name, f.amc, group, sharpe_3y=float(sharpe))
            )
    return out, None


# --- Recommending -----------------------------------------------------------------------------


def _goal_return(goal: Goal, category: str | None) -> float:
    return calculate(goal, category).expected_return_used / PERCENT


def recommend(db: Session, user: User, goal: Goal, today: date | None = None) -> Recommendation:
    history = sleeve_history(db)
    if history is None:
        raise RecommendationUnavailable(
            f"Recommendations need at least {MIN_HISTORY_MONTHS // 12} years of fund history: "
            "run the market data pipeline"
        )
    market = history.market
    category = risk_category(db, user)
    years = max(goal.target_year - (today or date.today()).year, 0)
    allocation = alloc.allocate(market, category, years, goal.goal_type)
    picks, fund_model = candidates(db)
    selection = pick_funds(allocation.weights, picks)
    base = alloc.BASE_EQUITY.get(category or "", alloc.BASE_EQUITY[alloc.DEFAULT_CATEGORY])
    goal_return = _goal_return(goal, category)
    emergency = goal.goal_type == "emergency_fund"
    reasons = allocation_reasons(
        allocation, market, category, base, years, goal_return, alloc.mid_small_limit(years)
    )
    if emergency:
        reasons[0] = (
            "An emergency fund must be available at a day's notice, so it is kept entirely in "
            "short-term debt, whatever the risk profile."
        )

    vol = market.volatility
    corr = market.correlation()
    inputs = RecommendationInputs(
        capital_market=CapitalMarketOut(
            sleeves=[
                SleeveMarketOut(
                    sleeve=s,
                    label=alloc.LABELS[s],
                    expected_return=round(alloc.EXPECTED_RETURN[s] * PERCENT, 2),
                    volatility=round(float(vol[i]) * PERCENT, 2),
                    funds=history.funds[s],
                )
                for i, s in enumerate(alloc.SLEEVES)
            ],
            correlation=[[round(float(x), 3) for x in row] for row in corr],
            months=len(history.months),
            start=history.months[0],
            end=history.months[-1],
        ),
        frontier=[
            FrontierPoint(volatility=round(v * PERCENT, 2), expected_return=round(r * PERCENT, 2))
            for v, r in alloc.efficient_frontier(market)
        ],
        base_equity=0.0 if emergency else round(base * PERCENT, 1),
        risk_aversion=allocation.risk_aversion,
        mid_small_limit=0.0 if emergency else round(alloc.mid_small_limit(years) * PERCENT, 1),
        short_debt_minimum=100.0
        if emergency
        else round(alloc.short_debt_minimum(years) * PERCENT, 1),
        goal_return=round(goal_return * PERCENT, 2),
        fund_model=fund_model,
        notes=selection.notes,
    )
    recommendation = Recommendation(
        goal_id=goal.id,
        as_of=history.months[-1],
        risk_category=category,
        years_to_goal=years,
        equity_share=allocation.equity_share,
        expected_return=allocation.expected_return,
        volatility=allocation.volatility,
        allocation=[
            SleeveOut(
                sleeve=s, label=alloc.LABELS[s], weight=round(allocation.weights[s] * PERCENT, 2)
            ).model_dump()
            for s in alloc.SLEEVES
        ],
        funds=[
            FundPickOut(
                fund_id=p.fund_id,
                name=p.name,
                amc=p.amc,
                sleeve=p.sleeve,
                sleeve_label=alloc.LABELS[p.sleeve],
                peer_group=p.peer_group,
                peer_label=PEER_LABELS.get(p.peer_group, p.peer_group),
                weight=round(p.weight * PERCENT, 2),
                basis=p.basis,
                reason=p.reason,
                predicted_quartile=p.predicted_quartile,
                prob_top=p.prob_top,
            ).model_dump()
            for p in selection.picks
        ],
        reasons=reasons,
        inputs=inputs.model_dump(mode="json"),
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


def to_read(recommendation: Recommendation) -> RecommendationRead:
    return RecommendationRead(
        id=recommendation.id,
        goal_id=recommendation.goal_id,
        created_at=recommendation.created_at,
        as_of=recommendation.as_of,
        risk_category=recommendation.risk_category,
        years_to_goal=recommendation.years_to_goal,
        equity_share=round(recommendation.equity_share * PERCENT, 2),
        expected_return=round(recommendation.expected_return * PERCENT, 2),
        volatility=round(recommendation.volatility * PERCENT, 2),
        allocation=recommendation.allocation,
        funds=recommendation.funds,
        reasons=recommendation.reasons,
        inputs=recommendation.inputs,
    )


def history_for(db: Session, goal: Goal) -> list[Recommendation]:
    """Newest first."""
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.goal_id == goal.id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        )
    )


def to_summary(r: Recommendation) -> RecommendationSummary:
    return RecommendationSummary(
        id=r.id,
        created_at=r.created_at,
        as_of=r.as_of,
        risk_category=r.risk_category,
        years_to_goal=r.years_to_goal,
        equity_share=round(r.equity_share * PERCENT, 2),
        expected_return=round(r.expected_return * PERCENT, 2),
        funds=len(r.funds),
    )
