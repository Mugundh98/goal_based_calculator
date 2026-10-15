# Architecture

_Living document – updated at the end of every phase. Last updated: Phase 5._

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
| Pure logic | `app/finance/` (risk rules from Phase 2, TVM formulas and goal projections from Phase 3, fund metrics from Phase 4), `app/simulation/` (Phase 5); later `app/ml/`, `app/chatbot/` | No database or HTTP code; unit-tested directly; reusable by routes and the chatbot |

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
