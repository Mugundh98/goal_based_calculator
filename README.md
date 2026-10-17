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

## Tests

```bash
cd backend && uv run pytest -v
```

```bash
cd frontend && npm run lint && npm run build
```
