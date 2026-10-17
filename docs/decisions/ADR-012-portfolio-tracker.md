# ADR-012: Portfolio tracker – transactions as the source of truth, materialised FIFO holdings, XIRR, drift alerts

**Status:** Accepted · **Date:** 2026-10-17 · **Phase:** 9

## Context

Phase 9 lets users record what they actually invested and compares it with the plan. It must give a correct return for irregular cash flows (SIPs, lump sums, redemptions), keep the units held exactly consistent with the transactions, say whether each goal is on track, and warn when a goal's mix drifts from its Phase 8 recommendation.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Source of truth | Holdings edited directly; **transactions** | **`transactions` (insert and delete only)** | Every number can be traced to dated cash flows; holdings, gains and XIRR are all functions of them |
| Holdings | Computed on every read (view); **materialised table**; materialised view | **`holdings` table rebuilt for the affected (user, goal, fund) in the same database transaction as each insert/delete** | Every page needs the units and cost of all positions; replaying FIFO lots and unit changes on every read repeats work. Rebuilding in the same transaction keeps it consistent (a materialised view would need a full refresh). Market value is *not* stored: it changes daily |
| Holding key | Per user and fund (plan); **per user, goal and fund** | **(user, goal, fund)**, goal NULL = unassigned, unique with `NULLS NOT DISTINCT` | Goal progress and drift need the money per goal; the same fund may serve two goals |
| Cost of redemptions | Average cost; **FIFO** | **FIFO lots** | The method registrars use for mutual fund capital gains; gives the cost of what is still held and the gain booked |
| Units of a purchase | Amount ÷ NAV; **after stamp duty, 3 decimals** | **(amount × (1 − 0.005%)) ÷ NAV, rounded down to 0.001** from 1 July 2020 | Matches account statements; the cash flow stays the full amount, so XIRR includes the cost |
| NAV for a date | Exact date only; **latest within a week** | **Latest NAV on or before the date, at most 7 days earlier** | Weekends and holidays; refuses dates the data does not cover |
| Face-value changes | Ignore; **restate** | **Units restated into today's units** with the Phase 4 rule (`nav_adjust`) | A 1:100 change would otherwise multiply the value by 100 |
| Concurrency | None; row lock; **advisory lock per user** | **`pg_advisory_xact_lock(9, user_id)`** for every write | Two requests can never both redeem the same units; works even when no holdings row exists yet; no contention between users |
| Return measure | Absolute; CAGR; **XIRR** | **XIRR (Newton-Raphson from 10%, bisection fallback), absolute return beside it, XIRR hidden under a year** | The only measure that weights each SIP by how long it was invested; annualising a few weeks exaggerates |
| On track | Compare with a planned path from goal creation; **re-project from today** | **Today's value + the goal's SIP at the plan's return vs the inflated target** (Phase 3 formula), plus "plan value" = money put in grown at the plan's return | Uses the Phase 3 maths unchanged; answers both "will I make it?" and "are my funds doing what the plan assumed?" |
| Rebalancing rule | Calendar; 5/25 relative; **absolute band** | **Alert when the equity share or any sleeve is more than 5 percentage points from the latest recommendation**; trades to restore it; advice to redirect new SIPs to avoid tax | Simple, common and explainable; equity share is the risk that matters most |

## Decision

- Pure modules `backend/app/finance/xirr.py` and `backend/app/portfolio/` (`ledger.py`: FIFO replay; `tracking.py`: sleeve mapping, drift, plan value); data access in `backend/app/services/portfolio.py`; tables `transactions` and `holdings` (migration `0010`); endpoints under `/api/portfolio`.
- Deleting a goal keeps its transactions (`goal_id` set to NULL) and rebuilds the user's holdings in the same transaction.

## Consequences

- Holdings can always be rebuilt from transactions; a test checks the stored rows equal a full rebuild.
- Returns and status are recomputed from the latest NAV on every read; nothing goes stale except a unit change that happens after the last write (rebuild fixes it).
- Not covered: exit loads, taxes, dividends (IDCW payouts), switches between funds (enter as a redemption and a purchase), importing statements (CAS).
