# Changelog

All notable changes, one entry per phase tag. Format: [Keep a Changelog](https://keepachangelog.com).

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
