"""Unit changes in NAV histories: a fund re-denominating its units is not a return.

Some funds change the face value of a unit (₹10 -> ₹1,000 for many liquid funds, or a 1:10
split): the NAV jumps by a power of ten overnight while every investor's money is unchanged.
Raw, such a jump looks like a +9,900% or -90% month and ruins every return, volatility and
drawdown that spans it. A real month never moves a fund's value by a factor of ten, so a
monthly ratio within 3% of 10^k (k != 0) is treated as a unit change: the NAVs BEFORE it are
multiplied by 10^k, so the series continues smoothly. Used for the ML data (monthly, Phase 7)
and for fund metrics and NAV charts (daily, Phase 4). Large moves that are not powers of ten
(defaults and recoveries in credit-risk funds, the March 2020 crash) are real and left alone.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

TOLERANCE = 0.03  # the period's ordinary return rides on top of the factor
POWERS = (-3, -2, -1, 1, 2, 3)


@dataclass(frozen=True)
class UnitChange:
    series: object  # fund id
    month: pd.Timestamp
    factor: float  # power of ten the NAV jumped by


def unit_factor(ratio: float) -> int | None:
    """k if `ratio` is within TOLERANCE of 10^k (k != 0), else None."""
    if not ratio > 0:
        return None
    for k in POWERS:
        if abs(math.log(ratio / 10.0**k)) < math.log1p(TOLERANCE):
            return k
    return None


def adjust_unit_changes(navs: pd.DataFrame) -> tuple[pd.DataFrame, list[UnitChange]]:
    """Rescale history before every unit change (columns = series, rows = dates, oldest first)."""
    adjusted = navs.copy()
    changes: list[UnitChange] = []
    ratios = navs / navs.ffill().shift(1)  # vs the last known NAV, across gaps
    for column in navs.columns:
        jumps = ratios[column].dropna()
        for when, ratio in jumps[(jumps > 5) | (jumps < 0.2)].items():
            k = unit_factor(float(ratio))
            if k is None:
                continue
            adjusted.loc[adjusted.index < when, column] *= 10.0**k
            changes.append(UnitChange(column, when, 10.0**k))
    return adjusted, changes


@dataclass(frozen=True)
class SeriesUnitChange:
    day: date  # first NAV in the new units
    factor: float  # power of ten the NAV jumped by


def adjust_series(
    series: Sequence[tuple[date, float]],
) -> tuple[list[tuple[date, float]], list[SeriesUnitChange]]:
    """The same rule for one fund's (date, NAV) list, oldest first (daily NAVs in Phase 4).

    Earlier NAVs are restated in the units of the LATEST NAV, so the newest value is exactly
    what AMFI publishes today and every return across the change is the real one.
    """
    changes: list[tuple[int, int]] = []  # (index of the first new-unit NAV, k)
    for i in range(1, len(series)):
        previous = series[i - 1][1]
        k = unit_factor(series[i][1] / previous) if previous > 0 else None
        if k is not None:
            changes.append((i, k))
    if not changes:
        return list(series), []
    adjusted: list[tuple[date, float]] = []
    multiplier = 1.0
    pending = list(changes)
    for i in range(len(series) - 1, -1, -1):  # newest first: changes accumulate going back
        while pending and pending[-1][0] > i:
            multiplier *= 10.0 ** pending.pop()[1]
        day, nav = series[i]
        adjusted.append((day, nav * multiplier))
    adjusted.reverse()
    return adjusted, [SeriesUnitChange(series[i][0], 10.0**k) for i, k in changes]
