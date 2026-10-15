# ADR-008: Monte Carlo simulation – median-return convention, risk shape from market history, saved snapshots

**Status:** Accepted · **Date:** 2026-10-16 · **Phase:** 5

## Context

Phase 3 projects every goal with one assumed return (ADR-006). Real returns vary from month to month, and the order of good and bad years matters for a SIP (sequence-of-returns risk). Phase 5 adds a Monte Carlo engine that simulates thousands of possible futures. Several choices change the numbers the user sees:

1. How the goal's expected return is used when returns are random: as the **mean** or as the **median** growth rate.
2. Where the volatility (and the rest of the shape of risk) comes from.
3. Which return models to offer, and which is the default.
4. How a mix of equity and debt is modelled, and how it relates to the return assumption.
5. Whether runs are stored, and how results stay reproducible.
6. Whether the engine loops in Python or is vectorised.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Meaning of the expected return *r* | Arithmetic mean of yearly returns; median (compound, geometric) growth rate | **Median: monthly log return = ln(1 + r)/12 + a shock with mean 0** | "12% a year" is how people quote a CAGR. With the median convention, zero volatility gives **exactly** the Phase 3 projection (tested), so the deterministic plan is the middle of the fan, and a plan that is exactly 100% funded has a ~50% chance. As a mean, volatility drag would push the median below the Phase 3 line and the two pages would disagree |
| Level of returns | Historical mean of the data; the goal's assumption | **The goal's assumption** (custom, risk profile or allocation) | 164 months of history give a mean with a standard error of ~4.5% a year for equity (σ/√n = 16.8%/√13.7): far too noisy to drive a plan. The user controls the assumption, as in Phase 3 |
| Shape of risk | Fixed volatility assumption; estimated from Phase 4 data | **Estimated from Phase 4 data:** Nifty 500 month-end closes and the median monthly return of ~137 bond funds, aligned (Feb 2013 – Sep 2026); fixed assumptions (equity 18%, debt 3%) only when no data is loaded, for the normal model | Real data carries fat tails (kurtosis 8.8 vs 3 for a normal distribution), the 2020 crash and volatility clustering. Centring each history on zero removes its level, so a price index without dividends is fine |
| Return models | Normal only; + bootstrap; + GARCH; + regime switching | **All four:** normal, block bootstrap (default), GARCH(1,1), 2-state Gaussian HMM | Each captures a different stylised fact, and comparing them on the same random numbers is a result in itself. Bootstrap is the default: no distribution assumed, real crashes included |
| Bootstrap blocks | Single months (i.i.d.); fixed 12-month blocks; stationary bootstrap (random lengths) | **Circular fixed-length blocks of 12 months** | Keeps within-year patterns (crash and rebound, calm years); circular wrapping makes every month equally likely, so the shocks average exactly 0. Simple to explain; the stationary bootstrap is a later refinement |
| Fitting GARCH / HMM | Own maximum-likelihood code; `arch` and `hmmlearn` | **Libraries for fitting, own NumPy code for simulating** | Fitting is numerical optimisation (constraints, EM restarts) that well-tested libraries do better. Simulation must be vectorised over 10,000 paths and seeded with our own generator, so it is ours, and the parameters it uses are plain numbers in the response |
| Starting state of GARCH / HMM | Today's fitted volatility / regime; the long-run (stationary) level | **Long-run level** | A 15-year plan should not swing with this month's market mood; results stay stable from day to day |
| Equity and debt | Separate models with correlation; one portfolio series | **One portfolio series, rebalanced monthly:** ln(1 + e·R_eq + (1 − e)·R_debt) | Univariate models are simpler to fit and explain; monthly rebalancing is the standard planning assumption. Fits are cached per equity share |
| Link between allocation and return | Independent inputs; one derived from the other | **e = (r − 7%) / (13% − 7%), r = 7% + 6%·e** | Maps the Phase 3 table onto mixes (7% → 0%, 8% → 16.7%, 10% → 50%, 12% → 83.3% equity), so moving the equity slider changes both risk and return, as in reality |
| Storage | Never store; store every run; store on request | **Preview endpoints save nothing; `POST …/simulations` saves a snapshot** in `simulations` (question) + `simulation_results` (answer, one-to-one) | A run is random, depends on market data that changes daily and takes ~0.1–1 s, unlike a Phase 3 projection: the stored copy records what the user saw. Slider previews would flood the table, so they are not stored |
| Reproducibility | Fresh randomness each run; fixed default seed | **Fixed default seed (2026), stored with every run** | The same inputs always give the same answer; moving one slider changes only that input, not the random numbers (common random numbers), so the effect of the change is visible and never reverses by chance |
| Implementation | Python loops over paths and months; NumPy over paths, loop over months; fully vectorised | **Fully vectorised wealth recursion** (cumulative sums); the GARCH/HMM shock recursion loops over months only | 10,000 × 180 path-months in ~56 ms instead of ~1.7 s (30× faster, identical results, `benchmark.py`) |
| Paths | 1,000; 10,000; 100,000 | **10,000 (500–10,000 allowed)** | Standard error of a success probability ≤ √(0.25/10,000) = 0.5 percentage points; 100,000 would cost 10× the time for 0.15 points |
| Required SIP for a chosen certainty | Search by re-running; exact from the paths | **Exact:** the value at the goal date is A + SIP × B on every path, so the SIP for probability q is the q-quantile of (target − A)/B | One run gives the answer for every probability, exactly, without iteration |

## Decision

- Pure code in `backend/app/simulation/` (`allocation.py`, `history.py`, `models.py`, `engine.py`, `benchmark.py`); data access, caching and API shapes in `backend/app/services/simulations.py`.
- The expected return is the median growth rate; return models contribute only centred shocks.
- Default model: block bootstrap; 10,000 paths; seed 2026; percentiles P10/P25/P50/P75/P90 per year; success means the value at the goal date reaches the Phase 3 inflated target (half-rupee tolerance, as Phase 3).
- History-based models need at least 60 aligned months; otherwise the API answers `409`.
- Saved runs store the resolved inputs, seed, fitted parameters and data window in `simulations.parameters`, so any run can be explained and reproduced.

## Consequences

- The goal page (Phase 3) and the simulation page always agree at zero volatility; the simulation adds the spread around the plan.
- The four models agree closely on the median (it is pinned by the assumption) and differ in the tails. This is expected and explained to the user.
- Inflation is deterministic, and taxes and fund costs are not modelled (Phase 6/8 may add them).
- The history starts in Feb 2013 (direct plans began in Jan 2013), so the 2008 crash is not in the bootstrap sample; the 2020 crash is (Nifty 500 −24% in March 2020).
- `arch` and `hmmlearn` add SciPy, scikit-learn and statsmodels to the backend; their first import is slow, so the API imports them in a background thread at start-up.
- Phase 8 will replace the 13%/7% blend with an optimised allocation per goal; Phase 10's chatbot will call `run_simulation` directly.
