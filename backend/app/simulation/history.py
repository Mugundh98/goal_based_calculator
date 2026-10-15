"""Monthly return history of a portfolio, built from equity and debt market data (Phase 4).

* Equity: month-end closes of the Nifty 500 (`^CRSLDX`), a price index.
* Debt: the median monthly return of the bond funds that have NAV history.

A month's return is month-end value / previous month-end value - 1. Only months present in
BOTH series and in one unbroken run are used, so every bootstrap block is a real stretch of
history. The month of the latest data is dropped because it is still incomplete.

Only the SHAPE of these returns is used (their volatility, fat tails, clustering, regimes): the
models centre them on zero and the engine adds the goal's own expected return (ADR-008). That is
also why a price index without dividends is fine here - dividends move the mean, which is
replaced anyway, not the volatility.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import numpy as np

from app.finance.tvm import MONTHS_PER_YEAR

MIN_HISTORY_MONTHS = 60  # five years: fewer is too little to estimate volatility, let alone GARCH


@dataclass(frozen=True)
class MarketHistory:
    """Aligned monthly simple returns (fractions) of equity and debt, oldest first."""

    months: tuple[date, ...]  # first day of each month
    equity: tuple[float, ...]
    debt: tuple[float, ...]
    equity_source: str
    debt_source: str

    @property
    def start(self) -> date:
        return self.months[0]

    @property
    def end(self) -> date:
        return self.months[-1]

    def portfolio_log_returns(self, equity_share: float) -> np.ndarray:
        return portfolio_log_returns(self.equity, self.debt, equity_share)


def _previous_month(month: date) -> date:
    return date(month.year - 1, 12, 1) if month.month == 1 else date(month.year, month.month - 1, 1)


def align(
    equity: Mapping[date, float], debt: Mapping[date, float], latest_month: date
) -> tuple[list[date], list[float], list[float]]:
    """Months found in both series, as the longest unbroken run ending as late as possible.

    `latest_month` (the month of the newest data) and anything after it are left out.
    """
    common = sorted(month for month in equity.keys() & debt.keys() if month < latest_month)
    runs: list[list[date]] = []
    for month in common:
        if runs and runs[-1][-1] == _previous_month(month):
            runs[-1].append(month)
        else:
            runs.append([month])
    if not runs:
        return [], [], []
    # Longest run; among equally long runs the most recent one (max keeps the first maximum).
    best = max(reversed(runs), key=len)
    return best, [equity[m] for m in best], [debt[m] for m in best]


def portfolio_log_returns(
    equity: tuple[float, ...] | list[float],
    debt: tuple[float, ...] | list[float],
    equity_share: float,
) -> np.ndarray:
    """Monthly log returns of a mix rebalanced every month: ln(1 + e x Re + (1 - e) x Rd).

    Log returns add up over time (ln of a product = sum of lns), which is what the models
    simulate; simple returns are mixed first because a portfolio's return is the weighted
    average of its parts' SIMPLE returns.
    """
    if not 0 <= equity_share <= 1:
        raise ValueError("equity share must be between 0 and 1")
    mix = equity_share * np.asarray(equity) + (1 - equity_share) * np.asarray(debt)
    return np.log1p(mix)


def annualised_volatility(log_returns: np.ndarray) -> float:
    """Sample standard deviation of monthly log returns x sqrt(12) (as in fund_metrics)."""
    return float(np.std(log_returns, ddof=1)) * math.sqrt(MONTHS_PER_YEAR)
