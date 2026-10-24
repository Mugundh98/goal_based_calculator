# Source Code

The complete source code of GoalWise is provided in a separate volume, **GoalWise_Source_Code.pdf**, submitted with this report, and in the project's Git repository. The volume contains every source file of the final release (version 1.2.0), each with its path and line numbers, in the following order.

Table: Organisation of the source code

| Part | Folder | Contents |
| --- | --- | --- |
| 1 | `backend/app/core` | Settings, database engine and session, security (JWT, password hashing) |
| 2 | `backend/app/models` | SQLAlchemy models (the database tables) |
| 3 | `backend/app/schemas` | Pydantic request and response models |
| 4 | `backend/app/api` | Routes (HTTP endpoints) and dependencies |
| 5 | `backend/app/services` | Business logic |
| 6 | `backend/app/finance` | Financial mathematics (TVM, risk profile, fund metrics, XIRR, formatting) |
| 7 | `backend/app/simulation` | Monte Carlo engine, return models, retirement simulation, concurrency limit |
| 8 | `backend/app/data_pipeline` | Data sources, parsers, loaders, jobs, scheduler |
| 9 | `backend/app/ml` | Machine-learning dataset, features, ranking, clustering, inflation, registry |
| 10 | `backend/app/recommendation` | Allocation, optimisation and fund selection |
| 11 | `backend/app/portfolio` | Ledger and tracking |
| 12 | `backend/app/chatbot` | Language-model adapter, tools, retrieval, orchestrator, prompts |
| 13 | `backend/app/reports`, `evaluation`, `deploy` | PDF plan, evaluation scripts, deployment commands |
| 14 | `backend/alembic` | Database migrations 0001–0014 |
| 15 | `backend/tests` | Backend tests |
| 16 | `frontend/src` | React application: API client, hooks, components, pages, libraries, tests |
| 17 | `frontend/e2e` | End-to-end tests |
| 18 | Configuration | Docker, Render, Vercel, CI workflows, project files |
