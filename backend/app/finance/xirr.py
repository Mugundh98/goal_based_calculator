"""XIRR: the annual return of a series of dated cash flows (Excel's XIRR).

The rate r that makes the net present value of every flow zero:

    sum_i  CF_i / (1 + r) ** ((d_i - d_0) / 365)  =  0

Money put in is negative, money taken out (and today's value, as if sold) positive. Unlike CAGR,
which only knows a start and an end value, XIRR weights every SIP instalment and redemption by
how long it was invested. For a single investment and a final value the two are the same.

Solved with Newton-Raphson (fast, quadratic convergence near the root) starting from 10%, as
Excel does; if Newton leaves the valid range (r <= -100%) or does not converge, bisection on a
bracket that changes sign is used instead (slow but always converges). Pure: no database.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

DAYS_PER_YEAR = 365.0  # Excel's convention: actual days / 365
GUESS = 0.1
TOLERANCE = 1e-9  # on the rate (Excel stops at 0.000001%)
MAX_ITERATIONS = 100
LOWEST = -0.999999  # just above -100% (all money lost)


@dataclass(frozen=True)
class XirrResult:
    rate: float  # fraction a year
    iterations: int
    method: Literal["newton", "bisection"]


def _years(flows: Sequence[tuple[date, float]]) -> list[float]:
    start = min(day for day, _ in flows)
    return [(day - start).days / DAYS_PER_YEAR for day, _ in flows]


def xnpv(rate: float, flows: Sequence[tuple[date, float]]) -> float:
    """Net present value at the first flow's date (Excel's XNPV)."""
    return sum(cf / (1 + rate) ** t for (_, cf), t in zip(flows, _years(flows), strict=True))


def _newton(cash: list[float], years: list[float]) -> XirrResult | None:
    rate = GUESS
    for iteration in range(1, MAX_ITERATIONS + 1):
        value = sum(cf * (1 + rate) ** -t for cf, t in zip(cash, years, strict=True))
        slope = sum(-t * cf * (1 + rate) ** (-t - 1) for cf, t in zip(cash, years, strict=True))
        if slope == 0 or not math.isfinite(slope):
            return None
        step = value / slope
        rate -= step
        if not math.isfinite(rate) or rate <= LOWEST:
            return None  # jumped out of the valid range
        if abs(step) < TOLERANCE:
            return XirrResult(rate, iteration, "newton")
    return None


def _bisection(cash: list[float], years: list[float]) -> XirrResult | None:
    def f(rate: float) -> float:
        return sum(cf * (1 + rate) ** -t for cf, t in zip(cash, years, strict=True))

    low, high = LOWEST, 1.0
    while f(low) * f(high) > 0:  # widen the bracket until the sign changes
        high *= 2
        if high > 1e6:
            return None
    for iteration in range(1, 400):
        middle = (low + high) / 2
        if f(low) * f(middle) <= 0:
            high = middle
        else:
            low = middle
        if high - low < TOLERANCE:
            return XirrResult((low + high) / 2, iteration, "bisection")
    return None


def xirr(flows: Sequence[tuple[date, float]]) -> XirrResult | None:
    """The annual rate, or None when there is none (all flows of one sign, or all zero)."""
    flows = [(day, cf) for day, cf in flows if cf != 0]
    if not any(cf < 0 for _, cf in flows) or not any(cf > 0 for _, cf in flows):
        return None
    years = _years(flows)
    if max(years) == 0:
        return None  # every flow on one day: no time, no rate
    cash = [cf for _, cf in flows]
    return _newton(cash, years) or _bisection(cash, years)
