"""Daily closing levels of NSE indices, from Yahoo Finance via the yfinance library.

NSE's own website blocks automated downloads; Yahoo Finance carries the same closing levels
and yfinance handles its cookies and request format. The indices are the benchmarks that
fund performance is compared with.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Yahoo symbol -> display name. Order = order shown in the app.
INDICES = {
    "^NSEI": "Nifty 50",
    "^CRSLDX": "Nifty 500",
    "NIFTYMIDCAP150.NS": "Nifty Midcap 150",
}
DEFAULT_BENCHMARK = "^NSEI"


@dataclass
class IndexSeries:
    points: list[tuple[date, Decimal]] = field(default_factory=list)  # oldest first
    skipped: Counter = field(default_factory=Counter)


def clean_closes(closes: list[tuple[date, float | None]]) -> IndexSeries:
    """Drop missing (NaN) and non-positive closes and duplicate dates; sort by date."""
    result = IndexSeries()
    by_date: dict[date, Decimal] = {}
    for day, close in closes:
        if close is None or math.isnan(close):
            result.skipped["missing_close"] += 1
            continue
        if close <= 0:
            result.skipped["close_not_positive"] += 1
            continue
        if day in by_date:
            result.skipped["duplicate_date"] += 1
        by_date[day] = Decimal(str(round(close, 4)))
    result.points = sorted(by_date.items())
    return result


def fetch_closes(symbol: str, start: date | None) -> list[tuple[date, float | None]]:
    """Daily closes from `start` (or the whole history). Imported lazily: yfinance pulls in
    pandas, which the API process does not otherwise need."""
    import yfinance

    ticker = yfinance.Ticker(symbol)
    frame = (
        ticker.history(start=start.isoformat(), auto_adjust=False)
        if start
        else ticker.history(period="max", auto_adjust=False)
    )
    return [(stamp.date(), float(close)) for stamp, close in frame["Close"].items()]
