# Architecture

_Living document – updated at the end of every phase. Last updated: Phase 11._

## Overview

GoalWise is a three-tier web application.

```mermaid
flowchart TB
    subgraph Presentation["Presentation tier – frontend/ (React + TypeScript)"]
        UI[Pages and components]
        APIC[API client – axios]
        UI --> APIC
    end
    subgraph Application["Application tier – backend/app/ (FastAPI)"]
        RT[Routes – api/routes]
        SV[Services – services]
        MD[Models – models]
        RT --> SV --> MD
    end
    subgraph Data["Data tier"]
        PG[(PostgreSQL 16 + pgvector)]
    end
    subgraph Pipeline["Data pipeline – backend/app/data_pipeline/"]
        SCH[APScheduler / CLI] --> JOB[Jobs: extract → transform → load]
    end
    subgraph Sources["Public data sources (free, no API key)"]
        AMFI[AMFI NAVAll.txt]
        MFAPI[mfapi.in history]
        YF[Yahoo Finance via yfinance]
        MOSPI[MOSPI CPI API]
    end
    APIC -- "REST / JSON over HTTP" --> RT
    MD -- "SQLAlchemy + psycopg" --> PG
    Sources --> JOB
    JOB -- "idempotent upserts, job_runs log" --> PG
```

### Market data pipeline (Phase 4)

| Job | Source | Schedule (India time) | Writes |
|---|---|---|---|
| `daily_nav` | AMFI `NAVAll.txt` | daily 23:30, then `fund_metrics` | `funds`, `nav_history` |
| `backfill_nav` | mfapi.in (cached in `backend/data/cache/`) | by hand (CLI), resumable | `nav_history` |
| `index_history` | Yahoo Finance (`yfinance`) | Mon–Fri 18:30 | `index_history` |
| `inflation` | MOSPI CPI API | 13th of each month, 10:00 | `inflation_data` |
| `fund_metrics` | `nav_history` | after `daily_nav` | `fund_metrics` |

Every run is recorded in `job_runs` (status, rows read/written, data-quality counts, error). A partial unique index allows only one running row per job, so two processes cannot run the same job at once. The scheduler runs inside the API process when `SCHEDULER_ENABLED=true`; jobs can also be run with `uv run python -m app.data_pipeline <job>` or, by an admin, with `POST /api/market/jobs/{job}/run`. Details: `docs/phases/04-market-data.md`, ADR-007.

### Monte Carlo simulation (Phase 5)

```mermaid
flowchart LR
    UI[GoalSimulationPage<br/>sliders, debounced 400 ms] -->|POST /api/goals/id/simulate| RT[simulations routes]
    RT --> SV[services/simulations.py<br/>run_simulation]
    SV -->|goal + overrides| IN[resolve inputs<br/>return, equity share]
    SV -->|cached by data fingerprint| H[(index_history<br/>nav_history)]
    H --> HI[simulation/history.py<br/>portfolio log returns]
    HI --> M[simulation/models.py<br/>normal, bootstrap, GARCH, HMM<br/>fits cached per equity share]
    M --> E[simulation/engine.py<br/>10,000 paths, vectorised]
    E --> SV
    SV -->|save| DB[(simulations,<br/>simulation_results)]
```

The engine follows the Phase 3 conventions (effective monthly rate, annuity-due SIPs, yearly step-up); the expected return is the median growth rate, so zero volatility reproduces the Phase 3 projection exactly. History-based models need at least 5 years of aligned equity and debt months; without market data only the normal model runs, with assumed volatilities. Fitting `arch`/`hmmlearn` models imports pandas and SciPy (seconds), so the API imports them in a background thread at start-up. Details: `docs/phases/05-simulation.md`, ADR-008.

### Retirement planner (Phase 6)

```mermaid
flowchart LR
    UI[RetirementWizard / RetirementPage] -->|PUT, GET, POST calculate, simulate| RT[retirement routes]
    RT --> SV[services/retirement.py]
    SV -->|age| PR[(financial_profiles)]
    SV --> F[finance/retirement.py<br/>growing-annuity corpus, drawdown]
    SV --> MC[simulation/retirement.py<br/>lifetime Monte Carlo, closed form]
    MC --> E[simulation/engine.py + Phase 5 models]
    SV -->|plan + synced goal| DB[(retirement_plans, goals)]
```

The savings phase is stored as a `retirement` goal (target = corpus in today's money), so the Goals page and the Phase 5 simulation use it unchanged; the planner owns it and the goals API refuses direct edits. The withdrawal phase has a closed form (balance = growth × (corpus − PV of withdrawals so far)), so success, depletion ages and the SIP and corpus for a chosen certainty come from one vectorised run. Details: `docs/phases/06-retirement.md`, ADR-009.

### ML fund intelligence (Phase 7)

```mermaid
flowchart LR
    CLI[python -m app.ml train] --> D[ml/dataset + features]
    D --> R[ranking: LightGBM, walk-forward, SHAP]
    D --> C[clustering: K-Means]
    I[inflation: SARIMA] --> REG
    R & C --> REG[registry: ml_models + model files]
    JOB[ml_score job, daily] --> S[scoring] --> P[(fund_predictions, fund_clusters)]
    REG --> S
    UI[InsightsPage, FundDetailPage] --> API[/api/ml] --> P
```

Training is offline and versioned (one active version per model, enforced by a partial unique index); a daily job scores the latest month; the API only reads stored predictions. Features use only data up to each month-end (tested), validation is purged walk-forward against momentum and random baselines, explanations are exact tree SHAP values. Face-value changes in NAV histories are adjusted out (`app/finance/nav_adjust.py`). Details: `docs/phases/07-ml.md`, ADR-010.

### Recommendations (Phase 8)

```mermaid
flowchart LR
    UI[RecommendationPage] -->|POST /api/goals/id/recommendations| SV[services/recommendations.py]
    SV -->|sleeve medians, cached| H[(nav_history)]
    SV --> AL[recommendation/allocation.py<br/>glide, liquidity, mean-variance, frontier]
    SV -->|ranked candidates| P[(fund_predictions)]
    SV --> SE[recommendation/selection.py]
    SV --> DB[(recommendations)]
    UI -->|?equity=| SIM[Phase 5 simulation]
```

Rules set the equity share (risk category × glide from 10 years to 1), the mid/small limit and the short-term minimum; a constrained mean-variance optimisation (SLSQP) splits four sleeves using assumed returns and measured covariances; funds come from the Phase 7 ranker. Every recommendation is stored with its inputs. Details: `docs/phases/08-recommendations.md`, ADR-011.

### Portfolio tracker (Phase 9)

```mermaid
flowchart LR
    UI[PortfolioPage, GoalProgressPage] -->|/api/portfolio| SV[services/portfolio.py]
    SV -->|insert or delete + rebuild, one DB transaction, advisory lock| TX[(transactions, holdings)]
    SV --> LD[portfolio/ledger.py<br/>FIFO]
    SV --> XR[finance/xirr.py<br/>Newton-Raphson]
    SV --> TR[portfolio/tracking.py<br/>sleeves, drift]
    SV -->|NAV on a date| NH[(nav_history)]
    SV -->|latest| RC[(recommendations)]
```

Transactions are the source of truth; holdings are derived (FIFO, units restated across face-value changes) and materialised, rebuilt in the same database transaction as each change. Values, XIRR, goal status (Phase 3 projection from today's value) and drift from the latest recommendation (5-point band) are computed on read. Details: `docs/phases/09-portfolio.md`, ADR-012.

### Conversational assistant (Phase 10)

```mermaid
flowchart LR
    UI[AssistantPage] -->|POST question, SSE stream back| RT[routes/chat.py]
    RT --> OR[chatbot/orchestrator.py<br/>loop, audit, grounding]
    OR <-->|declarations, function calls, text| GM[Gemini<br/>llm.py]
    OR --> TL[chatbot/tools.py<br/>10 tools, this user only]
    TL --> SV[goals, simulations, recommendations,<br/>portfolio, funds, risk services]
    TL --> RG[chatbot/rag.py] -->|cosine search| KB[(kb_chunks<br/>vector 768, HNSW)]
    OR --> DB[(chat_messages, tool_calls)]
```

The model chooses tools; the server runs them with the logged-in user's permissions and logs every call; explanations come from the pgvector knowledge base; a grounding check flags numbers not found in tool results; creating a goal needs a confirmed preview; a fallback model and fallback messages handle rate limits. Details: `docs/phases/10-chatbot.md`, ADR-013.

### Reports and administration (Phase 11)

```mermaid
flowchart LR
    U[Dashboard / Goals] -->|Download my plan| RP[routes/reports.py] --> RS[services/reports.py] --> PDF[reports/plan_pdf.py<br/>ReportLab]
    AP[AdminPage, AdminRoute] -->|require_admin| AD[routes/admin.py] --> AS[services/admin.py]
    R[Routes] -->|Audit dependency, after success| AL[(audit_log<br/>append-only trigger)]
    CLI[python -m app.admin] --> AL
```

The PDF is rendered on the server from the same services as the pages. Admin routes check the role from the database on every request; administrators are created from the command line. Key actions are recorded with user, entity, details and IP in an append-only table. Details: `docs/phases/11-reports-admin.md`, ADR-014.

## Components built so far

| Component | Phase | Status |
|---|---|---|
| React shell, router, API client, status page | 0 | Done |
| FastAPI app, settings, DB session, health endpoint | 0 | Done |
| PostgreSQL + pgvector, Alembic migrations | 0 | Done |
| CI pipeline | 0 | Done |
| Auth: `users` table, Argon2id hashing, JWT login, `get_current_user`, `require_admin` | 1 | Done |
| Frontend auth: AuthProvider, axios interceptors, route guards, login/register/dashboard | 1 | Done |
| `finance/risk_profile.py` pure scoring rules; profile and risk services/routes | 2 | Done |
| Profile form, risk questionnaire, results page, onboarding dashboard | 2 | Done |
| `finance/tvm.py` time-value-of-money formulas, `finance/goal_plan.py` projections; goals service/routes | 3 | Done |
| Goals page, goal dialog with live projection, dashboard goals step | 3 | Done |
| `finance/fund_metrics.py` (returns, rolling returns, volatility, Sharpe, Sortino, drawdown) | 4 | Done |
| `data_pipeline/`: AMFI, mfapi.in, Yahoo Finance and MOSPI ingestion, upserts, job log, scheduler, CLI | 4 | Done |
| Fund explorer (search, filters, sortable paged table), fund detail page with NAV vs Nifty 50 chart | 4 | Done |
| `simulation/`: vectorised Monte Carlo engine, normal / block bootstrap / GARCH(1,1) / 2-state HMM return models; simulations service and routes | 5 | Done |
| Goal simulation page: fan chart, chance of success, what-if sliders, SIP for a chosen certainty, model comparison, saved runs | 5 | Done |
| `finance/retirement.py` (corpus, drawdown, withdrawal rates), `simulation/retirement.py` (lifetime Monte Carlo); retirement service and routes; `retirement_plans` | 6 | Done |
| Retirement wizard, plan page (chance the money lasts, lifetime fan chart, survival chart, certainty, 4% rule), dashboard step | 6 | Done |
| `ml/`: peer groups, past-only features, LightGBM ranker with walk-forward validation and SHAP, K-Means clusters, SARIMA CPI forecast, registry, scoring job; `ml_models`, `fund_predictions`, `fund_clusters` | 7 | Done |
| Insights page (rankings with reasons, cluster scatter, inflation outlook, reliability), fund-page model card | 7 | Done |
| `recommendation/`: glide-path allocation, constrained mean-variance optimiser, efficient frontier, fund selection with reasons; `recommendations` | 8 | Done |
| Recommendation page (allocation, reasons, frontier, funds, history, simulate this allocation) | 8 | Done |
| `finance/xirr.py`, `portfolio/` (FIFO ledger, sleeves, drift); portfolio service and routes; `transactions`, `holdings` | 9 | Done |
| Portfolio page (summary, alerts, goal status, holdings, transactions), transaction form, goal progress page (value vs plan, projection, rebalancing), dashboard step | 9 | Done |
| `chatbot/`: Gemini adapter with fallback, 10 tools over the services, RAG over pgvector (20 articles), orchestrator with audit and grounding check, SSE endpoints; chat and knowledge-base tables | 10 | Done |
| Assistant page (conversations, suggestions, streamed answers, tool chips, inline charts, safe Markdown) | 10 | Done |
| Audit log (append-only table, `Audit` dependency, 22 actions); plan PDF (`reports/`, ReportLab); admin API and `make-admin` command | 11 | Done |
| Download my plan button; admin dashboard (overview, users, audit log, data jobs, models) behind `AdminRoute` | 11 | Done |

## Authentication flow

1. `POST /api/auth/login` (form) → signed JWT (`sub` = user id, `role`, `exp` = +60 min).
2. The browser keeps the token in `localStorage`; an axios interceptor sends it as `Authorization: Bearer …`.
3. Every protected route depends on `get_current_user`, which verifies the signature and expiry, then loads the active user from the database.
4. A `401` response makes the frontend log out. Details: `docs/phases/01-auth.md`, ADR-004.

## Frontend structure

| Folder | Responsibility |
|---|---|
| `src/api/` | Typed functions calling the backend; `client.ts` holds the axios instance and interceptors |
| `src/store/` | Auth context and provider (session state) |
| `src/components/` | Layout, route guards, form controls, UI pieces, SVG `LineChart` and `FanChart` |
| `src/pages/` | One component per route |
| `src/lib/` | Token storage, validation schemas, error formatting, number formats, chart ticks |
| `src/hooks/` | TanStack Query hooks |

## Backend layering

| Layer | Folder | Responsibility |
|---|---|---|
| Route | `app/api/routes/` | HTTP in/out only |
| Schema | `app/schemas/` | Pydantic request/response models |
| Service | `app/services/` | Business logic |
| Model | `app/models/` | SQLAlchemy ORM tables |
| Core | `app/core/` | Settings, DB engine/session, security |
| Pipeline | `app/data_pipeline/` | Source parsers, bulk upserts, jobs, scheduler, CLI (Phase 4) |
| Pure logic | `app/finance/` (risk rules from Phase 2, TVM formulas and goal projections from Phase 3, fund metrics from Phase 4), `app/simulation/` (Phase 5), `app/ml/` (Phase 7: pure modules plus `dataset`, `registry`, `scoring` for data access), `app/recommendation/` (Phase 8), `app/portfolio/` (Phase 9), `app/chatbot/` (Phase 10: pure `grounding`, `prompts`, chunking; `llm` wraps Gemini; `tools`, `rag`, `orchestrator` use services and the database) | No database or HTTP code; unit-tested directly; reusable by routes and the chatbot |

## Environments

| Environment | Frontend | Backend | Database |
|---|---|---|---|
| Development | Vite dev server `127.0.0.1:5173` (proxies `/api`) | Uvicorn `127.0.0.1:8000` | Docker `pgvector/pgvector:pg16` on port 5432 |
| CI | `npm ci` + lint + build | `uv sync` + ruff + migrations + pytest | GitHub Actions service container, same image |
| Production (Phase 13) | Vercel | Render | Managed PostgreSQL with pgvector |

## Configuration

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | backend | `postgresql+psycopg://goalwise:goalwise@127.0.0.1:5432/goalwise` |
| `CORS_ORIGINS` | backend | `http://localhost:5173,http://127.0.0.1:5173` (comma-separated) |
| `ENVIRONMENT` | backend | `development` |
| `JWT_SECRET_KEY` | backend | random 48+ byte string (required in production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | backend | `60` |
| `SCHEDULER_ENABLED` | backend | `false`; `true` runs the pipeline timetable in the API process (one process only) |
| `DATA_CACHE_DIR` | backend | `data/cache` (downloaded NAV histories, git-ignored) |
| `RISK_FREE_RATE` | backend | `0.06` (fraction a year, for Sharpe and Sortino) |
| `VITE_API_BASE_URL` | frontend | empty in development |
| `API_PROXY_TARGET` | Vite dev server | `http://127.0.0.1:8000` by default; another backend port when 8000 is busy |
