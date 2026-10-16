"""Load the data the models learn from: month-end NAVs of every fund and the market index.

Only direct-plan, growth-option funds are used: one share class per scheme (regular plans are
the same portfolio with a higher fee) and no IDCW payouts that look like losses. These are the
funds whose full history the pipeline backfills (Phase 4).

The month of the newest NAV is dropped because it is incomplete: a "month-end" NAV from the
15th would make that month look shorter than the others.
"""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ml.peers import peer_group

MARKET_INDEX = "^CRSLDX"  # Nifty 500, as in the simulations (Phase 5)

_FUND_MONTH_ENDS = """
    SELECT DISTINCT ON (n.fund_id, date_trunc('month', n.nav_date))
           n.fund_id, date_trunc('month', n.nav_date)::date AS month, n.nav
    FROM nav_history n JOIN funds f ON f.id = n.fund_id
    WHERE f.plan = 'direct' AND f.option = 'growth'
    ORDER BY n.fund_id, date_trunc('month', n.nav_date), n.nav_date DESC
"""
_MARKET_MONTH_ENDS = """
    SELECT DISTINCT ON (date_trunc('month', trade_date))
           date_trunc('month', trade_date)::date AS month, close
    FROM index_history WHERE symbol = :symbol
    ORDER BY date_trunc('month', trade_date), trade_date DESC
"""
_FUNDS = """
    SELECT id, name, amc, category, asset_class FROM funds
    WHERE plan = 'direct' AND option = 'growth'
"""


@dataclass(frozen=True)
class MonthlyData:
    navs: pd.DataFrame  # index: month (first day), columns: fund_id; NaN where no NAV
    market: pd.Series  # index: month, month-end index level
    funds: pd.DataFrame  # index: fund_id; name, amc, category, asset_class, peer_group

    @property
    def last_month(self) -> pd.Timestamp:
        return self.navs.index[-1]


def monthly_frame(rows, key: str, value: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=[key, "month", value])
    frame["month"] = pd.to_datetime(frame["month"])
    frame[value] = frame[value].astype(float)
    return frame


def complete_months(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Every month from the first to the last, so a missing NAV shows up as a gap (NaN)."""
    return pd.date_range(index.min(), index.max(), freq="MS")


def load(db: Session) -> MonthlyData:
    nav_rows = db.execute(text(_FUND_MONTH_ENDS)).all()
    market_rows = db.execute(text(_MARKET_MONTH_ENDS), {"symbol": MARKET_INDEX}).all()
    fund_rows = db.execute(text(_FUNDS)).all()
    if not nav_rows or not market_rows:
        raise ValueError("No NAV or index history: run the market data pipeline first")

    long = monthly_frame(nav_rows, "fund_id", "nav")
    navs = long.pivot(index="month", columns="fund_id", values="nav")
    newest = navs.index.max()
    navs = navs.reindex(complete_months(navs.index))
    navs = navs[navs.index < newest]  # the newest month is incomplete

    market = pd.DataFrame(market_rows, columns=["month", "close"])
    market = market.set_index(pd.to_datetime(market["month"]))["close"].astype(float)
    market = market.reindex(navs.index)

    funds = pd.DataFrame(fund_rows, columns=["fund_id", "name", "amc", "category", "asset_class"])
    funds = funds.set_index("fund_id")
    funds["peer_group"] = funds["category"].map(peer_group)
    funds = funds.loc[funds.index.intersection(navs.columns)]
    return MonthlyData(navs=navs[funds.index], market=market, funds=funds)
