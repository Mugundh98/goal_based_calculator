# Changelog

All notable changes, one entry per phase tag. Format: [Keep a Changelog](https://keepachangelog.com).

## [1.2.0] – 2026-10-21 – Account page, forgot password, wake-up countdown

### Added

- **Account page** (click your name in the menu): e-mail (shown, not editable), change your name, change your password (current password needed), set or change your security question.
- **"Forgot password?"** on the login page, without e-mail:
  - enter your e-mail, answer your security question and choose a new password;
  - answers ignore capitals and extra spaces and are stored hashed;
  - five wrong answers in an hour lock resets for that address;
  - unknown addresses get a stand-in question, so accounts cannot be discovered.
- Sign-up asks for a security question and answer.
- The **"Waking up the server" screen counts down** the usual minute with a progress bar, then says it is nearly there.
- Migration `0014` (`users.security_question`, `users.security_answer_hash`); ADR-018; 6 backend tests and 1 frontend test.

## [1.1.0] – 2026-10-21 – First user feedback

### Added

- Portfolio: **enter the NAV yourself** ("Enter the NAV myself (from my statement)"). Without it, the NAV of that day comes from the database as before. Any historic transaction can now be recorded.
- Portfolio: **add a fund that is not in the list** ("Can't find it? Add it yourself": name and type). It is private to you; its transactions need their NAV; it is valued at cost. Endpoints `GET/POST /api/portfolio/funds`.
- Portfolio: **edit a transaction** (`PUT /api/portfolio/transactions/{id}`), atomic and audited. A correction that would leave a later redemption without units changes nothing.
- Simulation: **type the exact value** next to each what-if slider (monthly SIP, yearly increase, target year, equity share), applied on Enter or when leaving the box.
- Risk profile result: **"What next?"** buttons: plan a goal, track investments, ask the assistant.
- Migration `0013` (`funds.owner_user_id`; fund references `NO ACTION`); ADR-017.

### Changed

- **Amounts show Indian digit grouping as you type** (25,00,000) in every ₹ box: goals, profile, retirement, transactions.
- The **Funds** menu item is now **Explore** ("Explore funds").
- The example goal name is "Pisai's college" (form placeholder and demo account).

### Fixed

- A portfolio test failed when the date three years ago fell on a weekend.

## [1.0.1] – 2026-10-21 – Deployment fix

Live at https://goal-based-calculator-seven.vercel.app (API https://goal-based-calculator.onrender.com).

### Fixed

- `copy-data` reported "Copied 0 rows" when `DATABASE_URL` pointed at the target, because it copied a database onto itself. It now prints the source and target, and refuses when they are the same database or when the source has no reference data. The deployment guide passes `--source` explicitly.

## [1.0.0] – 2026-10-18 – Phase 13: Deployment

### Added

- Deployment configuration:
  - `backend/Dockerfile`: Python 3.12 slim, uv 0.13.0, frozen dependencies, LightGBM's OpenMP runtime, unprivileged user, migrations on start, one uvicorn worker on `$PORT`.
  - `render.yaml`: free Docker web service in Singapore, health check, deploys after CI passes, secrets asked for once, generated JWT secret.
  - `frontend/vercel.json`: SPA rewrite, asset caching, security headers.
- `python -m app.deploy copy-data`: streams the reference data (funds, NAVs, metrics, indices, inflation, ML outputs, knowledge base) to another database with `COPY`. It checks migrations and columns, refuses to overwrite without `--replace`, never copies user data, and moves the id sequences forward.
- `python -m app.deploy demo-user [--reset]`: a complete demo household (profile, risk profile, three goals, retirement plan, three years of SIPs in real funds, recommendations), dated relative to today.
- `.github/workflows/data-refresh.yml`: nightly NAVs, metrics, index closes and inflation against the production database. Off until `PRODUCTION_DATABASE_URL` and `DATA_REFRESH=on` are set.
- Settings:
  - `DATABASE_CONNECT_TIMEOUT`;
  - `CORS_ORIGIN_REGEX` (e.g. Vercel previews);
  - `SIMULATION_CONCURRENCY`: Monte Carlo runs queue behind a process-wide semaphore, so the API fits in 512 MB.
- Frontend `ServerGate`: waits for a sleeping API and shows "Waking up the server…", with a retry after two minutes.
- Tests: settings, CORS pattern, simulation slots, data copy between two real databases, demo account, `ServerGate` (18 new: 593 backend, 55 frontend).
- Documentation: `docs/deployment.md` (step-by-step guide), Phase 13 document, ADR-016; updated architecture, database docs, README and project plan.

### Changed

- `DATABASE_URL` accepts `postgres://` and `postgresql://` (as hosting providers give them).
- `python -m app.data_pipeline` exits with status 1 when a job fails.
- CI runners pinned to Ubuntu 24.04 (`ubuntu-latest` moves to Ubuntu 26 on 19 October 2026, and Render deploys only after CI passes).
- Version 1.0.0.

## [0.12.0] – 2026-10-18 – Phase 12: Testing and evaluation

### Added

- Backend branch coverage with pytest-cov (93% of lines, 83% of branches; CI fails below 90% combined).
- Frontend tests with Vitest and React Testing Library (52): formats, chart ticks, goal validation, API errors, the XSS-safe Markdown renderer, alerts, route guards, the login form, the PDF button and the SSE parser.
- Playwright end-to-end tests (7 flows: onboarding, goals, validation, login redirect, admin access, plan PDF, assistant) and a CI job running them on PostgreSQL, the API and Vite.
- `python -m app.evaluation ml | returns | chatbot | uat`: ML walk-forward results against last year's top funds and random with a paired t test; chance of success of 5 sample goals under the 4 return models; a 102-question assistant evaluation (tools, numbers, refusals, confirmation, hallucination with and without RAG, LLM judge); UAT plan, SUS form, response sheet and scorer. Reports in `docs/evaluation/`.
- `run_turn` can offer a subset of tools and another prompt (evaluation without RAG).

### Fixed

- The assistant's simulation tool crashed whenever no equity override was given (since 0.10.0).
- `list_goals` gave the plan from typed-in savings first and the real-holdings status nested, and a smaller model reported the wrong one; the real-holdings status now comes first.
- The grounding check compares magnitudes ("behind by ₹38,483" for −38,483).
- After logging in from a protected page, users were sent to the dashboard instead of that page (GuestRoute race, since Phase 1).
- A portfolio test failed on Sundays and Mondays.

## [0.11.0] – 2026-10-17 – Phase 11: Reports and administration

### Added

- Audit log: `audit_log` table – migration `0012` – made append-only by a trigger; actor kept by id and e-mail without a foreign key; 22 actions recorded after they succeed (sign-up, logins and failed logins, profile, risk, goals, retirement, saved simulations, recommendations, portfolio transactions, assistant-created goals, report downloads, admin changes, job runs, model activation, command-line role changes) with the client's IP address.
- "Download my plan": `GET /api/reports/plan` renders the plan (profile and risk, goals with projections, recommendations, latest simulation and recorded investments, retirement, holdings and alerts, assumptions) as a PDF with ReportLab.
- Administration: `/api/admin/overview`, `/users` (search, update role and active flag, no self-change), `/audit` and `/audit/actions`, `/models` and `/models/{id}/activate`; `python -m app.admin make-admin | revoke-admin <email>`.
- Frontend: "Download my plan (PDF)" on the dashboard and goals page; admin dashboard (overview, users, audit log, data jobs, models) behind an admin-only route and menu link.
- `app/finance/formatting.py` (`inr`, `lakh_crore`) shared by alerts, the assistant and the PDF; dependency `reportlab`, dev dependency `pypdf`.
- 17 new tests (559 total).
- Documentation: Phase 11 document, ADR-014, updated architecture, database, API docs and README.

## [0.10.0] – 2026-10-17 – Phase 10: Conversational assistant

### Added

- `app/chatbot/`: Gemini adapter (`google-genai`, streamed, function calling, fallback model on rate limits, normalised 768-dimension embeddings); 10 tools over the existing services, run for the logged-in user with Pydantic-validated arguments; orchestrator loop (≤ 6 rounds) with an audit trail, grounding check of numbers, fallback answers and interrupted streams; system prompt with scope, tool, knowledge-base, confirmation, injection and privacy rules.
- Knowledge base: 20 investor-education articles chunked into 86 passages, embedded with `gemini-embedding-001` into pgvector (HNSW cosine index), idempotent ingestion; `python -m app.chatbot ingest|search`.
- Tables `chat_sessions`, `chat_messages`, `tool_calls`, `kb_documents`, `kb_chunks` – migration `0011`; endpoints `/api/chat/status`, `/api/chat/sessions` (list, create, read, delete) and `/api/chat/sessions/{id}/messages` (server-sent events); 2,000-character questions, 30 questions an hour per user.
- Simulation what-if override `current_savings`; the assistant simulates and judges goals from their recorded investments.
- Frontend: Assistant page (conversations, suggestion chips, streamed answers, tool chips with timings, fan chart / allocation / fund comparison under answers, grounding warnings, safe Markdown renderer).
- Settings `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `GEMINI_EMBEDDING_MODEL`, `CHAT_MESSAGES_PER_HOUR`; dependencies `google-genai`, `pgvector`.
- 32 new tests (542 total), with a scripted fake model and a stubbed Gemini client.
- Documentation: Phase 10 document, ADR-013, updated architecture, database, API docs and README.

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
