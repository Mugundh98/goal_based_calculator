# ADR-011: Recommendations – glide rules plus constrained mean-variance, model-ranked funds, stored snapshots

**Status:** Accepted · **Date:** 2026-10-17 · **Phase:** 8

## Context

Phase 8 turns the earlier pieces into advice for each goal: how to split the money between asset classes, which funds to use, and why. It must respect the investor's risk profile (Phase 2) and horizon, use the market data (Phase 4) and fund rankings (Phase 7), be explainable, and be reproducible later.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Asset classes | Equity/debt only; many categories; **four sleeves** | **Large cap, mid & small cap, longer-term bonds, short-term debt**, each represented by the median monthly return of its direct-growth funds | Enough for a real optimisation and distinct fund choices; each sleeve maps to SEBI peer groups that the fund model ranks. Gold and international were not possible: no fund with 5+ years of history was loaded |
| Expected returns | Historical means; analyst forecasts; **planning assumptions** | **12.5% / 13.5% / 7.5% / 6.5%** (equity average 13%, as Phase 5) | 13 years of means are too noisy to optimise on (ADR-008); a 1% mid/small premium avoids a corner solution (below) |
| Risk | Assumed; **estimated** | **Covariance of 164 monthly sleeve returns (Feb 2013 – Sep 2026)** | Second moments are estimated far more precisely than means |
| Equity share | Optimiser alone; **glide rule** | **Base by risk category (30 / 60 / 85%) × linear glide from 10 years to 0 at 1 year** | Unconstrained Markowitz with assumed returns gives extreme, unstable mixes; glide paths are how target-date funds and advisers manage horizon risk, and are explainable |
| Splitting within equity and debt | Fixed ratios; **mean-variance** | **Maximise w·μ − (γ/2) w′Σw**, long-only, with the equity share fixed, mid & small cap ≤ 50% of equity gliding to 0 within 3 years, short-term debt ≥ a share of debt rising to 100% at 1 year | The optimiser decides what it can decide well (trade-offs between correlated sleeves); the rules encode horizon and liquidity, which a one-period model cannot see |
| Risk aversion | One value; **by category** | **γ = 8 / 4 / 2** (conservative / moderate / aggressive) | Close to the γ implied by each base equity share in a two-asset large cap / bond portfolio (7.0 / 3.6 / 2.6) |
| Mid/small premium | 2%; **1%** | **1%** | With a 0.90 correlation to large caps, 2% always pushed mid/small to its cap for every investor and horizon: a corner solution, the classic Markowitz failure; at 1% the split responds to risk aversion |
| Emergency funds | Like any goal; **always liquid** | **100% short-term debt** | Must be available at a day's notice |
| Fund choice | Highest past return; **Phase 7 ranker**; Sharpe | **Lowest expected quartile in the sleeve's peer groups, one fund per fund house, two funds per sleeve ≥ 10%**; 3-year Sharpe if the ranker is not trained | Uses the validated model with its reasons; diversifies across fund houses; still works before ML training |
| Storage | Compute on read; **store snapshots** | **`recommendations` row per request** with the allocation, picks, reasons, capital-market inputs, frontier and model version | A recommendation depends on that day's data, rankings and profile; keeping it gives an audit trail and history ("what was I told in March?") |
| Simulation | New engine; **Phase 5 engine** | **Open the Phase 5 simulation with the recommended equity share** | One simulation model for the whole app; it models the mix as equity + debt with real Indian volatility |

## Decision

- Pure modules `backend/app/recommendation/allocation.py` (sleeves, glide, liquidity, optimiser with SLSQP, efficient frontier) and `selection.py` (fund picks, reasons); data access and storage in `backend/app/services/recommendations.py`; table `recommendations` (migration `0009`); endpoints under `/api/goals/{id}/recommendations`.

## Consequences

- Allocations change smoothly with the horizon and risk profile and can be explained sentence by sentence; the recommended portfolio sits on the efficient frontier when no rule binds.
- The fund picks inherit the Phase 7 model's modest skill (about momentum level); the page says rankings are a weak guide and advises spreading money and reviewing yearly.
- The returns are assumptions; a change of assumptions changes every allocation (stored inputs make each one traceable).
- Not covered: taxes and exit loads, expense ratios, minimum investment amounts, gold and international funds, rebalancing (Phase 9 tracks holdings).
