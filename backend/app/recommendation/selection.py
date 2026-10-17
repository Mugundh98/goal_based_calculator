"""Fund picks for each sleeve of an allocation, and the reasons shown to the user.

Within a sleeve, funds are ranked by the Phase 7 model (lowest expected quartile first, then the
highest chance of a top-quartile year). If the model has not been trained, the 3-year Sharpe
ratio from the Phase 4 metrics is used instead, and the reason says so. Two funds from the same
fund house are not picked for one sleeve: if a fund house has a bad year, both picks would.

Pure: no database.
"""

from dataclasses import dataclass, field

from app.ml.peers import LABELS as PEER_LABELS
from app.recommendation.allocation import EQUITY, LABELS, SLEEVES, Allocation, CapitalMarket

SLEEVE_PEERS: dict[str, tuple[str, ...]] = {
    "large_cap": ("large_cap",),
    "mid_small_cap": ("mid_cap", "small_cap"),
    "long_debt": ("corporate_bond", "banking_psu", "gilt", "dynamic_bond", "short_duration"),
    "short_debt": ("liquid", "money_market", "ultra_short", "low_duration"),
}
MIN_SLEEVE_WEIGHT = 0.02  # smaller sleeves are folded into the largest one
SPLIT_FROM = 0.10  # sleeves of at least 10% get two funds, smaller ones one
FUNDS_PER_SLEEVE = 2


@dataclass(frozen=True)
class Candidate:
    fund_id: int
    name: str
    amc: str
    peer_group: str
    expected_quartile: float | None = None  # Phase 7 ranker
    prob_top: float | None = None
    predicted_quartile: int | None = None
    peer_rank: int | None = None
    peer_size: int | None = None
    top_factor: str | None = None  # label of the strongest positive SHAP factor
    sharpe_3y: float | None = None  # Phase 4 metrics (fallback)


@dataclass(frozen=True)
class Pick:
    fund_id: int
    name: str
    amc: str
    sleeve: str
    peer_group: str
    weight: float  # share of the goal's money
    basis: str  # "model" or "sharpe"
    reason: str
    predicted_quartile: int | None = None
    prob_top: float | None = None


@dataclass
class Selection:
    picks: list[Pick] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _rank(candidates: list[Candidate]) -> tuple[list[Candidate], str]:
    predicted = [c for c in candidates if c.expected_quartile is not None]
    if predicted:
        return sorted(predicted, key=lambda c: (c.expected_quartile, -(c.prob_top or 0))), "model"
    with_sharpe = [c for c in candidates if c.sharpe_3y is not None]
    return sorted(with_sharpe, key=lambda c: -c.sharpe_3y), "sharpe"


def _reason(c: Candidate, basis: str, sleeve: str) -> str:
    group = PEER_LABELS.get(c.peer_group, c.peer_group).lower()
    if basis == "model":
        text = (
            f"Ranked {c.peer_rank} of {c.peer_size} {group} funds by the fund model: "
            f"{round((c.prob_top or 0) * 100)}% chance of a top-quartile year"
        )
        if c.top_factor:
            text += f"; strongest reason: {c.top_factor.lower()}"
        return text + "."
    return (
        f"Best 3-year Sharpe ratio ({c.sharpe_3y:.2f}) among the {LABELS[sleeve].lower()} funds "
        "(the fund model has not been trained, so past risk-adjusted return is used)."
    )


def fold_small_sleeves(weights: dict[str, float]) -> dict[str, float]:
    """Sleeves under MIN_SLEEVE_WEIGHT are added to the largest sleeve of the same kind."""
    out = dict(weights)
    for sleeve, weight in weights.items():
        if 0 < weight < MIN_SLEEVE_WEIGHT:
            same_kind = [s for s in SLEEVES if (s in EQUITY) == (sleeve in EQUITY) and s != sleeve]
            target = max(same_kind, key=lambda s: out[s]) if same_kind else sleeve
            if out[target] >= MIN_SLEEVE_WEIGHT:
                out[target] += out[sleeve]
                out[sleeve] = 0.0
    return out


def pick_funds(weights: dict[str, float], candidates: dict[str, list[Candidate]]) -> Selection:
    selection = Selection()
    for sleeve, weight in fold_small_sleeves(weights).items():
        if weight <= 0:
            continue
        ranked, basis = _rank(candidates.get(sleeve, []))
        wanted = FUNDS_PER_SLEEVE if weight >= SPLIT_FROM else 1
        chosen: list[Candidate] = []
        for c in ranked:
            if c.amc in {x.amc for x in chosen}:
                continue
            chosen.append(c)
            if len(chosen) == wanted:
                break
        if not chosen:
            selection.notes.append(f"No eligible {LABELS[sleeve].lower()} fund found.")
            continue
        for c in chosen:
            selection.picks.append(
                Pick(
                    fund_id=c.fund_id,
                    name=c.name,
                    amc=c.amc,
                    sleeve=sleeve,
                    peer_group=c.peer_group,
                    weight=round(weight / len(chosen), 4),
                    basis=basis,
                    reason=_reason(c, basis, sleeve),
                    predicted_quartile=c.predicted_quartile,
                    prob_top=c.prob_top,
                )
            )
    return selection


def allocation_reasons(
    allocation: Allocation,
    market: CapitalMarket,
    category: str | None,
    base_equity: float,
    years: int,
    goal_return: float | None,
) -> list[str]:
    """Why the money is split this way, in plain sentences (percentages rounded for reading)."""
    w = allocation.weights
    profile = category or "moderate (no risk profile yet)"
    reasons = []
    if allocation.equity_share == 0:
        plural = "s" if years != 1 else ""
        reasons.append(
            f"The goal is {years} year{plural} away: money needed this soon is kept out of the "
            "stock market, so all of it goes to debt."
        )
    else:
        reasons.append(
            f"Your {profile} risk profile allows {base_equity:.0%} in equity for goals ten or "
            f"more years away; with {years} years to go, the glide rule sets "
            f"{allocation.equity_share:.0%}."
        )
        equity = allocation.equity_share
        mid_share = w["mid_small_cap"] / equity if equity else 0
        reasons.append(
            f"Within equity, {mid_share:.0%} goes to mid & small caps: they are expected to earn "
            "more but swing harder; the optimiser balances the two for your risk profile "
            "(at most half of the equity)."
        )
    debt = 1 - allocation.equity_share
    if debt > 0:
        long_share = w["long_debt"] / debt
        reasons.append(
            f"Within debt, {long_share:.0%} goes to longer-term bonds for a little more return, "
            "the rest to short-term debt that barely moves."
        )
    text = (
        f"Expected return {allocation.expected_return:.1%} a year with {allocation.volatility:.1%} "
        f"volatility: returns are planning assumptions, risk is measured on {market.months} months "
        "of Indian fund data."
    )
    if goal_return is not None:
        text += f" The goal currently assumes {goal_return:.1%}."
    reasons.append(text)
    return reasons
