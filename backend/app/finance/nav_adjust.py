"""Unit changes in NAV histories: a fund re-denominating its units is not a return.

Some funds change the face value of a unit (₹10 -> ₹1,000 for many liquid funds, or a 1:10
split): the NAV jumps by a power of ten overnight while every investor's money is unchanged.
Raw, such a jump looks like a +9,900% or -90% month and ruins every return, volatility and
drawdown that spans it. A real month never moves a fund's value by a factor of ten, so a
monthly ratio within 3% of 10^k (k != 0) is treated as a unit change: the NAVs BEFORE it are
multiplied by 10^k, so the series continues smoothly. Large moves that are not powers of ten
(defaults and recoveries in credit-risk funds, the March 2020 crash) are real and left alone.
"""

import math
from dataclasses import dataclass

import pandas as pd

TOLERANCE = 0.03  # the month's ordinary return rides on top of the factor
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
