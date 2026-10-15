"""Return and risk statistics of a fund, computed from its NAV history.

Pure functions only - no database - so each one can be checked by hand. Conventions:

* A NAV series is a list of (date, nav) pairs sorted by date, one per business day. Holidays
  are simply missing, so "the NAV on day d" means the last NAV published ON OR BEFORE d.
* Point-to-point and rolling returns are CAGRs (tvm.cagr) over whole calendar years.
* Risk statistics use MONTHLY returns over the last 3 years (36 returns), the convention of
  fund factsheets: daily returns are noisy and have holiday gaps. A monthly return is the
  change between NAVs one calendar month apart, counted back from the latest NAV.
* Rates are FRACTIONS (0.12 = 12%) and annualised with sqrt(12) for volatility.
"""

import math
import statistics
from bisect import bisect_right
from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.finance.tvm import MONTHS_PER_YEAR, cagr, monthly_rate

NavPoint = tuple[date, float]

RISK_WINDOW_MONTHS = 36  # 3 years of monthly returns for volatility, Sharpe, Sortino, drawdown


# --- Dates ------------------------------------------------------------------------------------


def shift_months(day: date, months: int) -> date:
    """Same day `months` later (negative = earlier); clamped to the month's last day.

    31 March minus one month is 28/29 February; 29 Feb 2024 minus 12 months is 28 Feb 2023.
    """
    month_index = day.year * 12 + day.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def nav_on_or_before(series: Sequence[NavPoint], day: date) -> NavPoint | None:
    """The last NAV published on or before `day` (binary search), or None if none exists."""
    position = bisect_right(series, day, key=lambda point: point[0])
    return series[position - 1] if position else None


# --- Returns ----------------------------------------------------------------------------------


def trailing_return(series: Sequence[NavPoint], years: int) -> float | None:
    """CAGR over the last `years` calendar years, ending at the latest NAV.

    None when the fund is younger than that: a shorter history must not be passed off as a
    5-year return.
    """
    if not series:
        return None
    end_day, end_nav = series[-1]
    start = nav_on_or_before(series, shift_months(end_day, -years * MONTHS_PER_YEAR))
    if start is None:
        return None
    return cagr(start[1], end_nav, years)


@dataclass(frozen=True)
class RollingSummary:
    """Every `years`-long CAGR in the history, one ending on each NAV date."""

    count: int
    average: float
    minimum: float
    maximum: float
    positive_share: float  # fraction of windows with a return above 0


def rolling_returns(series: Sequence[NavPoint], years: int) -> list[float]:
    """CAGR of every window of `years` years, one ending on each date that has enough history.

    Shows consistency: a fund's 3-year return can look good or bad depending only on the day
    you measure it; rolling returns show the whole range.
    """
    if not series:
        return []
    first_day = series[0][0]
    returns = []
    for end_day, end_nav in series:
        start_day = shift_months(end_day, -years * MONTHS_PER_YEAR)
        if start_day < first_day:
            continue
        start = nav_on_or_before(series, start_day)
        assert start is not None  # start_day >= first_day
        returns.append(cagr(start[1], end_nav, years))
    return returns


def summarise_rolling(returns: Sequence[float]) -> RollingSummary | None:
    if not returns:
        return None
    return RollingSummary(
        count=len(returns),
        average=statistics.fmean(returns),
        minimum=min(returns),
        maximum=max(returns),
        positive_share=sum(1 for r in returns if r > 0) / len(returns),
    )


def monthly_returns(series: Sequence[NavPoint], months: int = RISK_WINDOW_MONTHS) -> list[float]:
    """The last `months` monthly returns, oldest first; [] if the history is shorter.

    NAVs are sampled at the latest date and then one calendar month apart going back
    (15 Oct, 15 Sep, 15 Aug, ...), so the current partial month is never cut off.
    """
    if not series:
        return []
    end_day = series[-1][0]
    if shift_months(end_day, -months) < series[0][0]:
        return []
    samples = [nav_on_or_before(series, shift_months(end_day, -k)) for k in range(months, -1, -1)]
    navs = [point[1] for point in samples if point is not None]
    return [navs[k + 1] / navs[k] - 1 for k in range(months)]


# --- Risk -------------------------------------------------------------------------------------


def annualised_volatility(returns: Sequence[float]) -> float | None:
    """Sample standard deviation of monthly returns x sqrt(12).

    Variance grows in proportion to time for independent returns, so the standard deviation
    grows with the square root of time.
    """
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(MONTHS_PER_YEAR)


def sharpe_ratio(returns: Sequence[float], risk_free_rate: float) -> float | None:
    """Reward per unit of total risk: mean monthly excess return / its std dev, x sqrt(12).

    Excess return = fund return - risk-free return for the month (from the annual rate via
    the effective monthly rate, as in tvm.py).
    """
    if len(returns) < 2:
        return None
    rf = monthly_rate(risk_free_rate)
    excess = [r - rf for r in returns]
    spread = statistics.stdev(excess)
    if spread == 0:
        return None
    return statistics.fmean(excess) / spread * math.sqrt(MONTHS_PER_YEAR)


def downside_deviation(returns: Sequence[float], target: float) -> float:
    """Root mean square of the shortfalls below `target` (months above it count as 0)."""
    return math.sqrt(sum(min(0.0, r - target) ** 2 for r in returns) / len(returns))


def sortino_ratio(returns: Sequence[float], risk_free_rate: float) -> float | None:
    """Like Sharpe, but only months below the risk-free return count as risk.

    Investors do not mind upside volatility; Sortino penalises only the downside. None when
    no month fell below the risk-free return (no downside to divide by).
    """
    if len(returns) < 2:
        return None
    rf = monthly_rate(risk_free_rate)
    downside = downside_deviation(returns, rf)
    if downside == 0:
        return None
    mean_excess = statistics.fmean(r - rf for r in returns)
    return mean_excess / downside * math.sqrt(MONTHS_PER_YEAR)


@dataclass(frozen=True)
class Drawdown:
    depth: float  # fraction, negative: -0.35 = fell 35% from the peak
    peak: NavPoint
    trough: NavPoint


def max_drawdown(series: Sequence[NavPoint]) -> Drawdown | None:
    """Largest fall from a previous peak to a later low: min over t of NAV_t / peak_t - 1.

    One pass: remember the highest NAV so far and measure every NAV against it.
    """
    if not series:
        return None
    peak = series[0]
    worst = Drawdown(0.0, series[0], series[0])
    for point in series:
        if point[1] > peak[1]:
            peak = point
        depth = point[1] / peak[1] - 1
        if depth < worst.depth:
            worst = Drawdown(depth, peak, point)
    return worst


# --- Everything for one fund ------------------------------------------------------------------


@dataclass(frozen=True)
class FundStatistics:
    as_of_date: date
    history_start: date
    return_1y: float | None
    return_3y: float | None
    return_5y: float | None
    rolling_1y: RollingSummary | None
    rolling_3y: RollingSummary | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None


def fund_statistics(series: Sequence[NavPoint], risk_free_rate: float) -> FundStatistics:
    """All statistics stored in fund_metrics. Each is None if the history is too short."""
    if not series:
        raise ValueError("a NAV series is needed")
    end_day = series[-1][0]
    monthly = monthly_returns(series)
    risk_start = shift_months(end_day, -RISK_WINDOW_MONTHS)
    drawdown = (
        max_drawdown([point for point in series if point[0] >= risk_start]) if monthly else None
    )
    return FundStatistics(
        as_of_date=end_day,
        history_start=series[0][0],
        return_1y=trailing_return(series, 1),
        return_3y=trailing_return(series, 3),
        return_5y=trailing_return(series, 5),
        rolling_1y=summarise_rolling(rolling_returns(series, 1)),
        rolling_3y=summarise_rolling(rolling_returns(series, 3)),
        volatility=annualised_volatility(monthly),
        sharpe=sharpe_ratio(monthly, risk_free_rate),
        sortino=sortino_ratio(monthly, risk_free_rate),
        max_drawdown=drawdown.depth if drawdown else None,
    )
