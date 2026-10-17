# Changelog

All notable changes, one entry per phase tag. Format: [Keep a Changelog](https://keepachangelog.com).

## [0.9.0] – 2026-10-17 – Phase 9: Portfolio tracker

### Added

- `app/finance/xirr.py`: XIRR by Newton-Raphson from 10% with a bisection fallback; matches the example in Excel's documentation (0.373362535).
- `app/portfolio/`: FIFO replay of transactions into holdings (cost, realised gain, stamp duty, three-decimal units); fund → rebalancing row (sleeves via peer groups, index funds by name); drift from the recommendation with a 5-point band and amounts to move; plan value.
- `transactions` and `holdings` tables – migration `0010`; holdings rebuilt in the same database transaction as each change under a per-user advisory lock; units restated across face-value changes; deleting a goal keeps its transactions as unassigned.
- `GET /api/portfolio`, `GET/POST /api/portfolio/transactions`, `POST /api/portfolio/transactions/sip`, `DELETE /api/portfolio/transactions/{id}`, `GET /api/portfolio/goals/{id}`: valuation, XIRR, goal status (on/off track, plan value, projection), rebalancing and alerts.
- Frontend: portfolio page (summary, alerts, goal cards, holdings, transactions), transaction form (purchase, SIP history, redemption; fund search with plan and option), goal progress page (value against plan, projection against target, rebalancing), "Progress" on goal cards, dashboard step 5 and warnings.
- 46 new tests (510 total).
- Documentation: Phase 9 document, ADR-012, updated architecture, database and API docs.

## [0.8.0] – 2026-10-17 – Phase 8: Recommendations

### Added

- `app/recommendation/allocation.py`: four sleeves (large cap, mid & small cap, longer-term bonds, short-term debt) from median direct-growth fund returns; assumed returns (12.5 / 13.5 / 7.5 / 6.5%) with measured covariances (164 months); glide rule for the equity share by risk category and years to the goal; gliding mid/small-cap limit; liquidity rule for short-term debt; emergency funds kept liquid; mean-variance utility maximisation with SLSQP (risk aversion 8 / 4 / 2); efficient frontier.
- `app/recommendation/selection.py`: fund picks per sleeve from the Phase 7 ranker (one per fund house, Sharpe fallback) and plain-language reasons.
- `recommendations` table – migration `0009`; `POST/GET /api/goals/{id}/recommendations`, `GET …/latest`, `GET …/{id}`.
- Frontend: recommendation page (allocation bar and reasons, efficient frontier with labelled sleeves, funds with reasons, assumptions, history) and "Simulate this allocation" into the Phase 5 simulation; "Recommend" on goal cards.
- 28 new tests (464 total), including the closed-form two-asset check and constraints for every profile and horizon.
- Documentation: Phase 8 document, ADR-011, updated architecture, database and API docs.

## [0.7.1] – 2026-10-17 – Fund metrics and NAV charts ignore face-value changes

### Fixed

- Fund metrics (Phase 4) treated a fund's change of unit face value (a NAV that jumps by a power of ten, e.g. UTI Liquid Fund's 1:10 change on 20 June 2026) as a return: −89% one-year return, 52% volatility. The `fund_metrics` job now restates earlier NAVs in today's units first (`app/finance/nav_adjust.adjust_series`, the rule used for the ML data in 0.7.0); 19 such changes in the loaded data. Stored NAVs are unchanged.
- `GET /api/funds/{id}/nav` returns NAVs in today's units and a new `unit_changes` list; the fund page explains the adjustment under the chart.

## [0.7.0] – 2026-10-17 – Phase 7: ML fund intelligence

### Added

- `app/ml/`: canonical SEBI peer groups from AMFI labels; month-end NAV dataset (direct growth funds); 26 features computed only from past data (tested for look-ahead); target = next-12-month return quartile within the peer group.
- Fund ranker: LightGBM (very shallow trees, chosen on the 2018–2020 tuning years), purged walk-forward validation on 2021–2025 against momentum and random baselines and a shuffled split; rank correlation 0.248 (momentum 0.254), top picks in the top quartile 36% (chance 25%); exact tree SHAP explanations.
- Behaviour clusters: K-Means on 3-year risk and return (k = 8 by silhouette among k ≥ 4), Gaussian mixture by BIC for comparison, plain-language names.
- Inflation forecast: SARIMA(0,1,1)(0,1,1)₁₂ on log CPI, walk-forward error 1.31 pp a year ahead (naive 1.74, RBI target 1.86), 12-month forecast with an exact 80% band.
- Model registry `ml_models` (one active version per name), `fund_predictions`, `fund_clusters` – migration `0008`; training CLI `python -m app.ml`; daily `ml_score` pipeline job; experiment records in `docs/ml/`.
- `GET /api/ml/models`, `/api/ml/rankings`, `/api/ml/clusters`, `/api/ml/funds/{id}`, `/api/ml/inflation`.
- Frontend: Insights page (rankings with SHAP "Why?" bars, cluster scatter with highlight and table, inflation outlook, reliability card) and a "What the models say" card on fund pages.
- 43 new tests (429 total).
- Documentation: Phase 7 document, ADR-010, updated architecture, database and API docs and README.

### Fixed

- NAV face-value changes (a jump by a power of ten, 14 funds) are adjusted out of the ML data (`app/finance/nav_adjust.py`).

## [0.6.0] – 2026-10-16 – Phase 6: Retirement planner

### Added

- `tvm.annuity_due_present_factor` and `tvm.present_value_growing_annuity`; `app/finance/retirement.py`: corpus needed (present value of monthly withdrawals rising with inflation, annuity due), savings phase as a Phase 3 goal, month-by-month drawdown and depletion age, corpus multiple, withdrawal rate and sustainable withdrawal rate.
- `app/simulation/retirement.py`: lifetime Monte Carlo (Phase 5 engine until retirement, closed-form withdrawal phase): chance the money lasts, survival by age, depletion ages, exact SIP and corpus for a 50/75/90% chance; zero volatility reproduces the single-return plan.
- `retirement_plans` table – migration `0007`; one per user, owning one `retirement` goal whose target and year the planner keeps in sync.
- `GET/PUT/DELETE /api/retirement`, `POST /api/retirement/calculate`, `POST /api/retirement/simulate`; `PUT /api/goals/{id}` on the retirement goal returns `409`; saving the profile re-syncs the retirement year.
- Frontend: five-step retirement wizard with live preview, retirement page (chance the money lasts, lifetime fan chart with a retirement marker, chance-by-age chart, certainty table, 4% rule comparison), "Open planner" on the retirement goal, dashboard step 4, "Retirement" in the navigation.
- 61 new tests (386 total), including payment-by-payment and plain-loop cross-checks and the worked example.
- Documentation: Phase 6 document (with a simulation of the 4% rule on Indian data), ADR-009, updated architecture, database and API docs.

### Changed

- `FanChart` is generic over its band type and accepts age labels, a marker and a target label; end labels stay above the axis. The chance verdict moved to `src/lib/verdict.ts`. `services.simulations.history_out` is public.

## [0.5.0] – 2026-10-16 – Phase 5: Monte Carlo simulation engine

### Added

- `app/simulation/`: vectorised NumPy Monte Carlo engine (10,000 paths; Phase 3 conventions: effective monthly rate, annuity-due SIPs, yearly step-up; expected return = median growth rate, so zero volatility reproduces the Phase 3 projection exactly); success probability, P10–P90 bands per year, median shortfall, exact SIP for a 50/75/90% chance; plain-loop reference and `python -m app.simulation.benchmark` (30× faster vectorised).
- Four return models: normal, circular 12-month block bootstrap (default), GARCH(1,1) fitted with `arch`, 2-state Gaussian HMM fitted with `hmmlearn`; volatility from Phase 4 data (Nifty 500 and the median of bond funds, Feb 2013 – Sep 2026), assumed volatilities when no data is loaded.
- Equity share ↔ return link (13% equity, 7% debt) consistent with the Phase 3 return table.
- `simulations` and `simulation_results` tables – migration `0006`.
- `POST /api/goals/{id}/simulate`, `POST /api/goals/{id}/simulate/compare`, `POST/GET /api/goals/{id}/simulations`, `GET/DELETE /api/simulations/{id}`.
- Frontend: goal simulation page with chance of success, SVG fan chart (tooltip, keyboard, table view), debounced what-if sliders (SIP, step-up, target year, equity share), SIP for a chosen certainty, four-model comparison and saved runs; "Simulate" on each goal card.
- 70 new tests (325 total): zero-volatility identity, hand-calculated cases, loop cross-check, statistical sanity (median, mean, √N error, model fits recover known parameters), API.
- Documentation: Phase 5 document, ADR-008, updated architecture, database and API docs and README.

### Changed

- Target-year validation shared between goals and what-if overrides; `niceTicks` moved to `src/lib/chart.ts`; `arch`/`hmmlearn` imported in the background at API start-up.

## [0.4.0] – 2026-10-15 – Phase 4: Market data pipeline

### Added

- Market data tables – migration `0005`: `funds`, `nav_history` (composite primary key fund + date), `fund_metrics`, `index_history`, `inflation_data`, `job_runs` (partial unique index: one running row per job).
- `app/data_pipeline/`: parsers for AMFI `NAVAll.txt` (state machine, columns by header name, mixed encodings), mfapi.in NAV history (disk cache), Yahoo Finance index closes (`yfinance`) and the MOSPI CPI API; data-quality counts for every rejected row; idempotent chunked upserts; job runner writing `job_runs`; APScheduler timetable (`SCHEDULER_ENABLED`); command line `python -m app.data_pipeline`.
- `app/finance/fund_metrics.py`: trailing and rolling CAGR (reusing `tvm.cagr`), monthly returns, annualised volatility, Sharpe, Sortino and maximum drawdown.
- `GET /api/funds`, `/api/funds/categories`, `/api/funds/{id}`, `/api/funds/{id}/nav`; `GET /api/market/summary`, `/api/market/indices/{symbol}/history`, `/api/market/inflation`, `/api/market/jobs`; admin-only `POST /api/market/jobs/{job}/run`.
- Frontend: fund explorer (market strip, search, filters in the URL, sortable paged table, data-source freshness) and fund detail page (SVG NAV chart compared with Nifty 50, crosshair tooltip, keyboard access, table view; returns, rolling returns and risk).
- 90 new tests (255 total): hand-checked metrics, parsers on real-format samples, upsert idempotency, job log, API.
- Documentation: Phase 4 document, ADR-007, updated architecture, database, API docs and README.

### Changed

- `useDebounced` moved to its own hook; the Vite dev proxy target can be set with `API_PROXY_TARGET`.

## [0.3.0] – 2026-10-15 – Phase 3: Financial math library and goal manager

### Added

- Pure time-value-of-money module `app/finance/tvm.py`: FV/PV, inflation, real return (Fisher), CAGR, SIP future value (annuity due, effective monthly rate), step-up SIP, required SIP and required step-up SIP.
- `app/finance/goal_plan.py`: goal projection (inflated target, projected value, shortfall, required SIP rounded up to the rupee, funded %, on-track) and the expected-return assumption table.
- `goals` table – migration `0004`; `expected_return` NULL means automatic (latest risk category, cautious 7% under 3 years).
- `GET/POST /api/goals`, `GET/PUT/DELETE /api/goals/{id}`, `POST /api/goals/calculate` (no save).
- Frontend: goals page with monthly summary and goal cards, create/edit dialog (native `<dialog>`) with a debounced live projection, dashboard goals step, lakh/crore formatting.
- 70 new tests (165 total), including month-by-month simulation cross-checks and the documented worked example.
- Documentation: Phase 3 document, ADR-006, updated architecture, database and API docs.

### Fixed

- Dashboard steps no longer flash as "to do" while loading.
- Header navigation wraps on narrow screens.

## [0.2.0] – 2026-10-11 – Phase 2: Financial profile and risk profiling

### Added

- `financial_profiles` (one per user) and `risk_assessments` (history, JSONB answers and breakdown) tables – migration `0003`.
- `GET/PUT /api/profile`; `GET /api/risk/questionnaire`; `POST/GET /api/risk/assessments`; `GET /api/risk/assessments/latest`.
- Pure scoring module `app/finance/risk_profile.py`: 7-question tolerance score, 6-factor capacity score, final = lower of the two.
- `TimestampMixin` shared by models.
- Frontend: financial profile form with live surplus preview, step-by-step questionnaire, results page with score bars and capacity breakdown, assessment history, onboarding dashboard.
- 67 new tests (95 total), including every scoring boundary and a documented worked example.
- Documentation: Phase 2 document, ADR-005, updated architecture, database and API docs.

## [0.1.0] – 2026-10-11 – Phase 1: Authentication

### Added

- `users` table (migration `0002`) with unique lower-case email, role check constraint and `is_active` flag.
- `POST /api/auth/register`, `POST /api/auth/login` (OAuth2 password flow, JWT), `GET /api/auth/me`.
- Argon2id password hashing (pwdlib), HS256 JWT tokens (PyJWT) with 60-minute expiry.
- `get_current_user` and `require_admin` dependencies for protecting endpoints.
- Frontend: login and registration pages (react-hook-form + zod), AuthProvider with session restore and auto-logout, axios auth interceptors, protected and guest routes, dashboard; status page moved to `/status`.
- Test suite runs against a dedicated `goalwise_test` database built from migrations, with per-test rollback (28 tests).
- Documentation: Phase 1 document, ADR-004, updated architecture, database and API docs.

## [0.0.1] – 2026-10-10 – Phase 0: Setup and foundations

### Added

- FastAPI backend skeleton with settings, database session and `GET /api/health`.
- PostgreSQL 16 + pgvector via Docker Compose; Alembic with migration `0001` enabling `vector`.
- React 19 + TypeScript + Vite frontend with Tailwind CSS, React Router, TanStack Query and a system status page.
- Vite dev proxy and backend CORS configuration.
- GitHub Actions CI: backend lint, migrations and tests against a real database; frontend lint and build.
- Documentation: project plan, phase template, Phase 0 document, architecture, database, API, ADR-001 to ADR-003.
