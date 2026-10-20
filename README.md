# GoalWise

An ML-driven goal-based investment and retirement planning system with a conversational AI assistant.
MCA 4th-semester project, Andhra University CDOE.

**Stack:** React + TypeScript · FastAPI · PostgreSQL + pgvector · scikit-learn / XGBoost / statsmodels · Google Gemini API

## Documentation

| Document | Contents |
|---|---|
| [Project plan](docs/PROJECT_PLAN.md) | Phases, Git workflow, definition of done |
| [Phase documents](docs/phases/) | What each phase added, how it works, viva Q&A |
| [Architecture](docs/architecture.md) | Components and how they connect |
| [Database](docs/database.md) | ER diagram, table dictionary, migrations |
| [API](docs/api.md) | Endpoint list (full spec at `/docs` when running) |
| [Deployment](docs/deployment.md) | Vercel + Render + Neon, step by step |
| [Decisions](docs/decisions/) | Architecture decision records |
| [Changelog](CHANGELOG.md) | Changes per release |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically)
- Node.js 20+
- Docker Desktop

## Run locally

1. Start the database (project root):

   ```bash
   docker compose up -d
   ```

2. Start the backend (in `backend/`):

   ```bash
   cp .env.example .env
   uv sync
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload --reload-dir app --port 8000
   ```

3. Start the frontend (in `frontend/`):

   ```bash
   npm install
   npm run dev
   ```

4. Open http://localhost:5173. API docs: http://localhost:8000/docs

5. Load market data (in `backend/`, first time only; the backfill downloads the NAV history of
   about 1,500 funds and takes roughly half an hour):

   ```bash
   uv run python -m app.data_pipeline all
   ```

   Afterwards set `SCHEDULER_ENABLED=true` in `.env` to refresh it every evening, or run single
   jobs (`daily_nav`, `index_history`, `inflation`, `fund_metrics`) by hand.

   Then train the ML models (Phase 7, ~5 minutes; they need this data):

   ```bash
   uv run python -m app.ml train all
   ```

   The Monte Carlo simulations (Phase 5) take their volatility from this data. Without it, only
   the normal model runs, with assumed volatilities. To time the vectorised engine against plain
   Python loops: `uv run python -m app.simulation.benchmark`.

6. Switch on the assistant (Phase 10): put a Google AI Studio key in `backend/.env` as
   `GEMINI_API_KEY=...` (never commit it), restart the API and build the knowledge base once
   (about 30 seconds; it is also built automatically the first time a term is explained):

   ```bash
   uv run python -m app.chatbot ingest
   ```

   Without a key the rest of GoalWise works and the Assistant page says it is switched off.

7. Make yourself an administrator (Phase 11) to see the Admin dashboard, then log in again:

   ```bash
   uv run python -m app.admin make-admin you@example.com
   ```

## Tests

Backend (pytest, with branch coverage; CI fails below 90%):

```bash
cd backend && uv run pytest --cov
```

Frontend unit and component tests (Vitest), lint and build:

```bash
cd frontend && npm test && npm run lint && npm run build
```

End-to-end tests (Playwright drives Chromium through the real app; it starts the API and the
dev server if they are not running; first time: `npx playwright install chromium`):

```bash
cd frontend && npm run e2e
```

## Evaluation

Reports go to `docs/evaluation/` (Markdown for the report, JSON with the raw numbers):

```bash
cd backend
uv run python -m app.evaluation ml        # ML models against naive baselines
uv run python -m app.evaluation returns   # chance of success under the 4 return models
uv run python -m app.evaluation chatbot   # 102 questions against the live assistant (Gemini key)
uv run python -m app.evaluation uat       # results table from the UAT feedback forms
```

## Deployment

**Live:** https://goal-based-calculator-seven.vercel.app. The API is at https://goal-based-calculator.onrender.com, with interactive docs at `/docs`. The free API sleeps after 15 idle minutes, so the first visit after a break shows "Waking up the server…" for up to a minute.

The frontend is deployed to Vercel, the API to Render (Docker, free plan) and the database to Neon (PostgreSQL 16 + pgvector). All three are free. The configuration is in the repository: `render.yaml`, `backend/Dockerfile`, `frontend/vercel.json` and `.github/workflows/data-refresh.yml`. Step-by-step guide: [docs/deployment.md](docs/deployment.md).

```bash
cd backend
uv run python -m app.deploy copy-data --target "<Neon URL>"   # reference data, once
uv run python -m app.deploy demo-user --reset                 # demo account (DATABASE_URL = Neon)
```

To try the production image locally:

```bash
docker build -t goalwise-api backend
```
