# Changelog

All notable changes, one entry per phase tag. Format: [Keep a Changelog](https://keepachangelog.com).

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
