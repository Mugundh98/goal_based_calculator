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

## Tests

```bash
cd backend && uv run pytest -v
```

```bash
cd frontend && npm run lint && npm run build
```
