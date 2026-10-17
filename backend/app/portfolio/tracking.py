"""Goal tracking: which sleeve a fund belongs to, drift from the recommended mix, plan value.

Rebalancing rule: a goal needs rebalancing when its equity share, or any sleeve, is more than
5 percentage points away from the latest recommendation (a common threshold; calendar
rebalancing and the "5/25" relative rule are the alternatives, see ADR-012). Pure: no database.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from app.ml.peers import peer_group
from app.recommendation.allocation import EQUITY, LABELS, SLEEVES
from app.recommendation.selection import SLEEVE_PEERS

DRIFT_THRESHOLD = 0.05  # fraction of the goal's money
OTHER_EQUITY = "other_equity"  # flexi cap, ELSS, sectoral ...: equity, but no sleeve of its own
OTHER = "other"  # hybrid, gold, international ...
ROWS = (*SLEEVES, OTHER_EQUITY, OTHER)
ROW_LABELS = {**LABELS, OTHER_EQUITY: "Other equity funds", OTHER: "Other funds"}
EQUITY_ROWS = (*EQUITY, OTHER_EQUITY)
DAYS_PER_YEAR = 365.0

# Index funds and ETFs are one peer group whatever they track, so the index is read from the
# name. Checked in order; a keyword must start a word and not run on into more digits, so
# "nifty 50" matches "Nifty 50 Index" but not "Nifty 500".
_INDEX_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (OTHER, ("gold", "silver", "nasdaq", "s&p 500", "hang seng", "global", "international")),
    ("long_debt", ("gilt", "g-sec", "gsec", "sdl", "bond", "psu", "crisil", "debt")),
    ("short_debt", ("liquid", "overnight", "money market")),
    ("mid_small_cap", ("midcap", "mid cap", "smallcap", "small cap")),
    ("large_cap", ("nifty 50", "nifty next 50", "nifty 100", "sensex", "bse 100", "top 100")),
)


def sleeve_of(category: str, name: str = "", asset_class: str = "") -> str:
    """The rebalancing row a fund counts in."""
    group = peer_group(category)
    for sleeve, peers in SLEEVE_PEERS.items():
        if group in peers:
            return sleeve
    if group == "index":
        lower = name.lower()
        for row, keywords in _INDEX_RULES:
            if any(re.search(rf"\b{re.escape(k)}(?!\d)", lower) for k in keywords):
                return row
        return OTHER_EQUITY  # broad indices: Nifty 500, sector indices ...
    return OTHER_EQUITY if asset_class == "equity" else OTHER


@dataclass(frozen=True)
class DriftRow:
    row: str
    label: str
    value: float  # rupees in this row now
    actual: float  # fraction of the goal's holdings
    target: float  # fraction recommended
    drift: float  # actual - target
    trade: float  # rupees to buy (+) or sell (-) to get back to the target


@dataclass(frozen=True)
class Rebalance:
    rows: list[DriftRow]
    equity_actual: float
    equity_target: float
    equity_drift: float
    needed: bool  # some drift beyond the threshold


def rebalance(values: Mapping[str, float], target: Mapping[str, float]) -> Rebalance:
    """Compare the rupees in each row with the recommended fractions (sleeves only)."""
    total = sum(values.values())
    rows: list[DriftRow] = []
    for row in ROWS:
        value = values.get(row, 0.0)
        wanted = target.get(row, 0.0)
        if value == 0 and wanted == 0:
            continue
        actual = value / total if total else 0.0
        rows.append(
            DriftRow(
                row=row,
                label=ROW_LABELS[row],
                value=value,
                actual=actual,
                target=wanted,
                drift=actual - wanted,
                trade=wanted * total - value,
            )
        )
    equity_actual = sum(r.actual for r in rows if r.row in EQUITY_ROWS)
    equity_target = sum(target.get(row, 0.0) for row in EQUITY_ROWS)
    equity_drift = equity_actual - equity_target
    # The tiny epsilon keeps a drift of exactly 5.0 points (in floating point) from alerting.
    needed = total > 0 and (
        abs(equity_drift) > DRIFT_THRESHOLD + 1e-9
        or any(abs(r.drift) > DRIFT_THRESHOLD + 1e-9 for r in rows)
    )
    return Rebalance(rows, equity_actual, equity_target, equity_drift, needed)


def grown_contributions(flows: Iterable[tuple[date, float]], rate: float, on: date) -> float:
    """What the money put in would be worth on `on` had it earned `rate` a year (the plan).

    Flows are investor cash flows: purchases negative, redemptions positive.
    """
    return sum(
        -cf * (1 + rate) ** ((on - day).days / DAYS_PER_YEAR) for day, cf in flows if day <= on
    )
