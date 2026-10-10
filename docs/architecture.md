# Architecture

_Living document – updated at the end of every phase. Last updated: Phase 0._

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
    APIC -- "REST / JSON over HTTP" --> RT
    MD -- "SQLAlchemy + psycopg" --> PG
```

## Components built so far

| Component | Phase | Status |
|---|---|---|
| React shell, router, API client, status page | 0 | Done |
| FastAPI app, settings, DB session, health endpoint | 0 | Done |
| PostgreSQL + pgvector, Alembic migrations | 0 | Done |
| CI pipeline | 0 | Done |

## Backend layering

| Layer | Folder | Responsibility |
|---|---|---|
| Route | `app/api/routes/` | HTTP in/out only |
| Schema | `app/schemas/` | Pydantic request/response models |
| Service | `app/services/` | Business logic |
| Model | `app/models/` | SQLAlchemy ORM tables |
| Core | `app/core/` | Settings, DB engine/session, security |
| Pure engines (later) | `app/finance/`, `app/simulation/`, `app/ml/`, `app/chatbot/` | No HTTP code; reusable by routes and the chatbot |

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
| `CORS_ORIGINS` | backend | `http://localhost:5173` |
| `ENVIRONMENT` | backend | `development` |
| `VITE_API_BASE_URL` | frontend | empty in development |
