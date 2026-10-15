"""How much of a goal's money is in equity, and what return that buys.

A two-asset view: equity (a broad Indian index) and debt (bond funds). The long-run returns
below are planning assumptions, roughly the Nifty 500 total return and the return of bond funds
over the last 15-20 years. They are chosen so that the Phase 3 return table maps onto sensible
mixes:

| Assumed return (Phase 3)       | Equity share = (r - 7%) / (13% - 7%) |
|--------------------------------|--------------------------------------|
| 7%  (goal < 3 years away)      | 0%                                   |
| 8%  (conservative)             | 16.7%                                |
| 10% (moderate / no profile)    | 50%                                  |
| 12% (aggressive)               | 83.3%                                |

So a goal's return assumption and its allocation can never disagree: either one is derived from
the other. Phase 8 replaces this with a proper allocation per goal.
"""

EQUITY_RETURN = 0.13
DEBT_RETURN = 0.07


def equity_share_for_return(annual_return: float) -> float:
    """The equity share whose blended return equals `annual_return`, clamped to 0..1.

    Returns above 13% need more than 100% equity, which is not possible without borrowing,
    so they are treated as all-equity (the return assumption itself is kept).
    """
    share = (annual_return - DEBT_RETURN) / (EQUITY_RETURN - DEBT_RETURN)
    return min(max(share, 0.0), 1.0)


def return_for_equity_share(equity_share: float) -> float:
    """Blended long-run return of a mix: e x 13% + (1 - e) x 7%."""
    if not 0 <= equity_share <= 1:
        raise ValueError("equity share must be between 0 and 1")
    return equity_share * EQUITY_RETURN + (1 - equity_share) * DEBT_RETURN
