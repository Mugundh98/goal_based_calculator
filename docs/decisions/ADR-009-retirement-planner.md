# ADR-009: Retirement planner – corpus as a growing annuity, the plan stored with its savings goal, lifetime Monte Carlo in closed form

**Status:** Accepted · **Date:** 2026-10-16 · **Phase:** 6

## Context

Retirement is the largest goal most households have, and unlike other goals it has two phases: saving until retirement, then living off the money until death, with spending that keeps rising with inflation. Phase 6 adds a planner. Several choices change the numbers users see or how the data is kept:

1. How the corpus needed at retirement is calculated.
2. How the plan relates to the existing goals (Phase 3) and simulations (Phase 5).
3. How the withdrawal phase is simulated, and what "success" means.
4. Which returns are assumed before and after retirement.
5. How the result is compared with the 4% rule.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Corpus needed | A multiple of annual spending (25× = the 4% rule); present value of a level annuity; present value of an annuity that grows with inflation | **Present value of a growing annuity, annuity due, raised once a year:** PV = W₁ × a₁₂ × (1 − qⁿ)/(1 − q), q = (1 + π)/(1 + r) | Spending rises with prices every year; withdrawals are taken at the start of each month, as SIPs are invested (ADR-006); a fixed multiple ignores the user's own horizon, inflation and return. With exactly this corpus the last withdrawal empties the account (tested) |
| Spending input | Replacement ratio (% of income); today's expenses; an amount in retirement-year rupees | **Monthly spending in today's rupees**, defaulting to the profile's current expenses | People know what they spend now; inflation is the system's job, as for goal targets (Phase 3) |
| Inflation after retirement | Same as before; separate | **Same rate for both phases** | One number is easier to understand; a separate rate adds little at this level of precision |
| Where the plan lives | All fields in `retirement_plans`; all fields in `goals`; split | **Split, no duplication:** `retirement_plans` (ages, spending, post-retirement return) + its own `retirement` goal (savings, SIP, step-up, inflation, pre-retirement return; target = corpus in today's money, year = retirement year) | The savings phase *is* a goal, so the Goals page, the Phase 5 simulation and later recommendations (Phase 8) treat it like any other, and each input is stored once. The plan suggested an "assumptions JSON" column; typed, CHECK-constrained columns validate better and every field is always present |
| Keeping the goal consistent | Let users edit it on the Goals page; refuse edits | **The planner writes the goal; `PUT /api/goals/{id}` on it returns `409`**; a new date of birth re-syncs the retirement year; deleting either deletes both | The goal's target and year are derived from the plan; editing them separately would make the two disagree |
| Withdrawal simulation | Python loop per path; NumPy loop over months; closed form | **Closed form:** V_t = D_t × (corpus − Σ_{s<t} W_s / D_s) | The bracket only falls, so the money runs out at the first month it would go negative, and it lasts for life exactly when corpus ≥ C_p (the present value of all withdrawals along path p). Fully vectorised; the SIP and the corpus for a 50/75/90% chance are exact quantiles from one run, as in Phase 5 |
| Success | Value at life expectancy > 0; every withdrawal paid in full | **Every withdrawal until life expectancy paid in full** (half-rupee tolerance) | Running dry at 82 is a failure even if a pension arrives later; partial payments are not modelled |
| Returns | One return for life; separate before and after | **Separate:** before = goal convention (custom or automatic from the risk profile; 7% if retiring within 3 years); after = user input, default 8% | A retiree living off the money usually holds less equity. Both map to an equity share with the Phase 5 blend (8% ≈ 17% equity, 10% = 50%), so each phase has its own volatility |
| Return models and data | New model; Phase 5 models | **Phase 5 models and market history**, fitted per phase's equity share, same seed and median-return convention (ADR-008) | Consistency: zero volatility reproduces the single-return plan exactly (tested) |
| Longevity | Fixed age; mortality tables | **Fixed "plan until" age (default 85), user-chosen** | Simple and explainable; the page advises planning beyond the average. Mortality-weighted planning is a future enhancement |
| 4% rule | Use it; ignore it; compare | **Compare:** show the plan's first-year withdrawal rate and the 4%-rule corpus (25× first-year spending), and test the rule by simulation on Indian data in the phase document | The rule is widely quoted, and comparing it is the viva question; it comes from US data with ~3% inflation |

## Decision

- Pure formulas in `backend/app/finance/retirement.py` (plus `annuity_due_present_factor` and `present_value_growing_annuity` in `tvm.py`); the lifetime simulation in `backend/app/simulation/retirement.py`; data access, goal syncing and API shapes in `backend/app/services/retirement.py`.
- `retirement_plans`: one per user (`user_id` UNIQUE), owning one goal (`goal_id` UNIQUE, ON DELETE CASCADE). Projections and simulations are computed on read and never stored.
- Limits: retire at 30–80 and after the current age; plan until at most 105 and for at most 50 years of retirement (keeps a 10,000-path lifetime in memory).

## Consequences

- The retirement goal on the Goals page reproduces the planner's corpus and required SIP through the ordinary Phase 3 formulas (tested), and can be simulated on the Phase 5 page (accumulation only).
- Results depend strongly on the post-retirement real return: at 6% inflation, 8% gives a sustainable 30-year withdrawal rate of 4.47%, 7% only 3.93%.
- Not modelled: taxes, fund costs, pensions (EPS, NPS annuity), rental income, lump-sum expenses, health-cost inflation above general inflation, mortality probabilities. The Phase 10 chatbot will call `services.retirement.calculate` and `simulate`.
