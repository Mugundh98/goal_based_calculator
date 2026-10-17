# GoalWise – Project Plan

**Project:** GoalWise – An ML-Driven Goal-Based Investment and Retirement Planning System with a Conversational AI Assistant
**Programme:** MCA (Online), Andhra University CDOE – 4th Semester Project
**Stack:** React + TypeScript (frontend) · FastAPI (backend) · PostgreSQL + pgvector (database) · scikit-learn / XGBoost / statsmodels (ML) · Google Gemini API (chatbot)

This plan splits the project into **14 phases**. Every phase:

1. is built on its own Git branch,
2. ends with working, tested code,
3. ends with a written **phase document** (`docs/phases/NN-name.md`) explaining what was added to the frontend, backend and database, and how they connect,
4. is merged into `main`, **tagged**, and **pushed to GitHub**.

The phase documents double as **viva preparation** (each has a Q&A section) and as **raw material for the project report** (150–180 pages).

---

## 1. Repository structure (target)

```
goalwise/
├── backend/                     FastAPI application
│   ├── app/
│   │   ├── main.py              App entry point, router registration, CORS
│   │   ├── core/                Settings, database session, security (JWT, hashing)
│   │   ├── models/              SQLAlchemy ORM models  (= database tables)
│   │   ├── schemas/             Pydantic models        (= API request/response shapes)
│   │   ├── api/routes/          HTTP endpoints, thin: validate → call service → return
│   │   ├── services/            Business logic (goals, risk profile, portfolio …)
│   │   ├── finance/             Pure financial math (FV, PV, SIP, XIRR …) – no DB, no HTTP
│   │   ├── simulation/          Monte Carlo engine + return models
│   │   ├── ml/                  Model loading + inference (training lives in /ml)
│   │   ├── data_pipeline/       AMFI / index / CPI ingestion, scheduled jobs
│   │   └── chatbot/             Gemini client, tool registry, RAG, guardrails
│   ├── alembic/                 Database migrations (versioned schema history)
│   ├── tests/                   pytest
│   └── pyproject.toml
├── frontend/                    React + Vite + TypeScript
│   └── src/
│       ├── api/                 Typed API client (one file per backend resource)
│       ├── pages/               Route-level screens
│       ├── components/          Reusable UI pieces
│       ├── hooks/               TanStack Query hooks (data fetching + caching)
│       └── store/               Auth state
├── ml/                          Offline notebooks + training scripts → saved model files
├── docs/
│   ├── PROJECT_PLAN.md          This file
│   ├── architecture.md          Living architecture overview (updated each phase)
│   ├── database.md              Living ER diagram + table dictionary
│   ├── api.md                   Endpoint summary (full spec = FastAPI /docs)
│   ├── decisions/               Architecture Decision Records (ADR-001 …)
│   └── phases/                  One document per phase (template: _TEMPLATE.md)
├── docker-compose.yml           Local PostgreSQL + pgvector
├── .github/workflows/ci.yml     Runs tests + lint on every push
├── CHANGELOG.md
└── README.md
```

**Layering rule (likely viva question):** `routes → services → models`. Routes only handle HTTP; services hold the logic; `finance/` and `simulation/` are pure functions with no database or HTTP code, so they can be unit-tested against hand calculations and reused by both the REST API and the chatbot.

---

## 2. Git and GitHub workflow

| Item | Convention |
|---|---|
| Main branch | `main` – always working, always deployable |
| Phase branch | `phase-NN-short-name`, e.g. `phase-03-risk-profile` |
| Commits | [Conventional Commits](https://www.conventionalcommits.org): `feat(goals): add goal CRUD endpoints`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:` |
| Commit size | Small and frequent – one logical change per commit, push at least daily |
| Merge | Pull Request from phase branch → `main` (PR description = summary of phase doc) |
| Tag | `v0.NN.0` after each phase merge, e.g. `v0.3.0` |
| CI | GitHub Actions runs backend tests, frontend build and lint on every push and PR |
| Secrets | Never committed. `.env` is git-ignored; `.env.example` lists the variable names |

**Per-phase command flow:**

```bash
git checkout main && git pull
git checkout -b phase-03-risk-profile
# … work, commit often …
git push -u origin phase-03-risk-profile
# open PR on GitHub, CI passes, merge
git checkout main && git pull
git tag -a v0.3.0 -m "Phase 3: risk profiling"
git push origin v0.3.0
```

### Definition of Done (every phase)

- [ ] Feature works end-to-end in the browser (frontend ↔ backend ↔ database)
- [ ] Tests written and passing locally and in CI
- [ ] Database changes captured in an Alembic migration
- [ ] `docs/phases/NN-name.md` completed from the template
- [ ] `docs/architecture.md`, `docs/database.md`, `docs/api.md` updated if affected
- [ ] `CHANGELOG.md` entry added
- [ ] Screenshots of new screens saved in `docs/screenshots/` (needed for the report)
- [ ] PR merged, tag pushed

---

## 3. Phase overview

| # | Phase | Frontend adds | Backend adds | Database adds | Est. |
|---|---|---|---|---|---|
| 0 | Setup and foundations | Vite + React + TS scaffold | FastAPI scaffold, health check | PostgreSQL + pgvector running | 1 wk |
| 1 | Authentication | Login, register, protected routes | JWT auth, password hashing | `users` | 1 wk |
| 2 | Financial profile and risk profiling | Profile form, risk questionnaire | Risk scoring service | `financial_profiles`, `risk_assessments` | 1 wk |
| 3 | Financial math library and goal manager | Goals list/create/edit, required SIP | `finance/` module, goal CRUD | `goals` | 1.5 wk |
| 4 | Market data pipeline | Fund explorer, fund detail page | AMFI/NSE/CPI ingestion, scheduler, metrics | `funds`, `nav_history`, `fund_metrics`, `index_history`, `inflation_data`, `job_runs` | 1.5 wk |
| 5 | Monte Carlo simulation engine | Fan chart, success %, what-if sliders | 4 return models, simulation service | `simulations`, `simulation_results` | 1.5 wk |
| 6 | Retirement planner | Retirement wizard, corpus-longevity chart | Accumulation + withdrawal logic | `retirement_plans` | 1 wk |
| 7 | ML: fund intelligence | Fund clusters view, ranking with explanations | Training pipeline, model serving, SHAP | `fund_predictions`, `ml_models` | 2 wk |
| 8 | Recommendations | Per-goal allocation + fund picks | Allocation + recommendation service | `recommendations` | 1 wk |
| 9 | Portfolio tracker | Transactions, holdings, XIRR, alerts | XIRR, on-track logic, rebalancing | `transactions`, `holdings` | 1 wk |
| 10 | Conversational assistant | Chat window with inline charts | Gemini function calling, RAG, guardrails | `chat_sessions`, `chat_messages`, `tool_calls`, `kb_documents`, `kb_chunks` | 2 wk |
| 11 | Reports and administration | PDF export, admin dashboard | PDF generation, admin endpoints, audit log | `audit_log` | 1 wk |
| 12 | Testing and evaluation | UI polish, error states | ML + chatbot evaluation scripts | — | 1 wk |
| 13 | Deployment | Production build on Vercel | Deploy API on Render | Managed Postgres | 0.5 wk |
| 14 | Report and presentation | Screenshots | — | Final ER diagram | 2 wk |

Total ≈ 19 weeks. Phases 12–14 can overlap with earlier ones (write report chapters as phases finish).

---

## 4. Phase details

Each phase lists what is added to each layer, how the layers connect, and the questions an examiner is likely to ask about it.

### Phase 0 – Setup and foundations  · branch `phase-00-setup` · tag `v0.0.1`

**Goal:** an empty but correctly wired project: frontend talks to backend, backend talks to database, CI runs.

- **Tooling:** Python 3.12, `uv` (package manager), Node 20+, Docker Desktop (for PostgreSQL), Git, VS Code.
- **Backend:** FastAPI app, settings loaded from `.env` via `pydantic-settings`, SQLAlchemy engine + session, Alembic initialised, `GET /api/health` returning app + DB status, ruff (lint), pytest.
- **Frontend:** Vite + React + TypeScript, Tailwind CSS, React Router, TanStack Query, axios client with base URL from env, a page calling `/api/health`.
- **Database:** `docker-compose.yml` with image `pgvector/pgvector:pg16`; `CREATE EXTENSION vector`.
- **Integration:** CORS configured; Vite dev proxy `/api → localhost:8000`.
- **CI:** GitHub Actions: backend lint + tests, frontend lint + build.
- **Docs:** README (how to run), `architecture.md` v1, ADR-001 (why FastAPI + React), ADR-002 (why PostgreSQL).
- **Viva focus:** Why FastAPI over Django/Flask? What is ASGI? What is CORS and why is it needed? What does Alembic do? Why Docker for the database?

### Phase 1 – Authentication  · `phase-01-auth` · `v0.1.0`

- **Database:** `users` (id, email unique, password_hash, full_name, role, created_at). First Alembic migration.
- **Backend:** `POST /auth/register`, `POST /auth/login` (returns JWT access token), `GET /auth/me`; passwords hashed with Argon2id (pwdlib – replaced the original bcrypt/passlib plan, see ADR-004); `get_current_user` dependency protecting routes; role field for admin.
- **Frontend:** Register and login pages, form validation (react-hook-form + zod), token + expiry in localStorage (survives reload, auto-logout at expiry), `ProtectedRoute` component, logout.
- **Integration:** axios interceptor attaches `Authorization: Bearer <token>`; 401 → redirect to login.
- **Tests:** register/login/me happy paths, duplicate email, wrong password, expired token.
- **Viva focus:** How does JWT work (header.payload.signature)? Why hash, not encrypt, passwords? What is a salt? Where is the token stored and what are XSS/CSRF trade-offs? What is FastAPI dependency injection?

### Phase 2 – Financial profile and risk profiling  · `phase-02-risk-profile` · `v0.2.0`

- **Database:** `financial_profiles` (1-to-1 with user: age, income, expenses, savings, dependants, employment type); `risk_assessments` (answers JSON, tolerance score, capacity score, final category, timestamp – history kept).
- **Backend:** profile GET/PUT; questionnaire definition endpoint; scoring service (weighted tolerance + capacity → conservative/moderate/aggressive); rule documented in code and docs.
- **Frontend:** onboarding flow: profile form → questionnaire stepper → result card explaining the category.
- **Viva focus:** Difference between risk tolerance and risk capacity; why rule-based instead of ML (no labelled data); 1-to-1 vs 1-to-many relationships; why store answers as JSON.

### Phase 3 – Financial math library and goal manager  · `phase-03-goals` · `v0.3.0`

- **Backend `finance/`:** pure functions – FV/PV, SIP future value, required SIP for a target, step-up SIP, inflation adjustment, real return, CAGR. **Each tested against hand-calculated examples** (tables of these go straight into the report).
- **Database:** `goals` (user_id FK, type enum, name, target_today, target_year, inflation_rate, priority, current_savings, monthly_sip). *As built:* `target_today` is named `target_amount`; added `expected_return` (NULL = automatic from the risk profile) and `step_up_rate`; projections are computed on read (ADR-006).
- **Backend API:** goals CRUD; each goal response includes inflation-adjusted target and required SIP.
- **Frontend:** goals dashboard (cards with progress), create/edit dialog, live "required SIP" as the user types.
- **Viva focus:** Derive the SIP FV formula; annuity due vs ordinary annuity; why separate pure math from services; enum columns vs lookup tables.

### Phase 4 – Market data pipeline  · `phase-04-market-data` · `v0.4.0`

- **Database:** `funds` (scheme code, name, AMC, SEBI category, plan, expense ratio), `nav_history` (fund_id, date, nav – indexed, largest table), `fund_metrics` (CAGR 1/3/5y, rolling returns, std dev, Sharpe, Sortino, max drawdown, computed_at), `index_history`, `inflation_data`, `job_runs` (pipeline log).
- **Backend `data_pipeline/`:** AMFI daily NAV parser, historical backfill (cached locally), Nifty index history via yfinance, CPI loader; APScheduler daily job; metrics recomputation; idempotent upserts.
- **Frontend:** fund explorer (search, filter by category, sortable table), fund detail page with NAV chart and metrics.
- **Viva focus:** ETL vs ELT; idempotency and upserts; indexing a time-series table (composite index on fund_id + date); bulk inserts; how Sharpe/Sortino/drawdown are computed; data-quality checks (gaps, duplicates).

### Phase 5 – Monte Carlo simulation engine  · `phase-05-simulation` · `v0.5.0`

- **Backend `simulation/`:** vectorised NumPy engine (10,000 paths × months); return models: normal, block bootstrap, GARCH(1,1) (`arch`), 2-state HMM (`hmmlearn`); success probability, percentile bands (P10/P50/P90).
- **Database:** `simulations` (goal_id, model, parameters JSON, run_at), `simulation_results` (success_prob, percentile paths JSON).
- **Backend API:** run simulation for a goal with optional overrides (SIP, years, allocation) – the same function the chatbot will call later.
- **Frontend:** fan chart (Plotly), success gauge, what-if sliders that re-run the simulation (debounced), model comparison view.
- **Viva focus:** Why Monte Carlo; law of large numbers and number of paths; sequence-of-returns risk; why bootstrap in blocks; what GARCH and HMM capture; vectorisation vs loops (show timing).

### Phase 6 – Retirement planner  · `phase-06-retirement` · `v0.6.0`

- **Backend:** accumulation phase (corpus needed at retirement from expenses, inflation, life expectancy) and withdrawal phase (corpus longevity simulation, safe withdrawal rate).
- **Database:** `retirement_plans` (linked to the retirement goal; assumptions JSON). *As built:* typed columns instead of JSON (retirement age, plan-until age, spending, post-retirement return); savings inputs stay on the linked goal (ADR-009).
- **Frontend:** step-by-step retirement wizard; chart of corpus over the full lifetime, with probability of not running out of money.
- **Viva focus:** 4% rule (Bengen) and why it may not suit India; present value of a growing annuity; longevity risk.

### Phase 7 – ML: fund intelligence  · `phase-07-ml` · `v0.7.0`

- **`ml/` (offline):** feature engineering from `nav_history`/`fund_metrics`; K-Means/GMM clustering; XGBoost/LightGBM classifier for next-12-month return quartile; **walk-forward validation** (no look-ahead bias); SHAP; SARIMA/Prophet CPI forecast; experiment results saved for the report.
- **Database:** `ml_models` (name, version, metrics JSON, file path, trained_at, is_active), `fund_predictions` (fund_id, model_id, predicted quartile, probability, top SHAP factors JSON). *As built:* also `fund_clusters`; LightGBM rather than XGBoost; SARIMA rather than Prophet; training lives in `backend/app/ml` (no top-level `ml/` folder) so training and serving share the feature code (ADR-010).
- **Backend `ml/`:** loads the active model at startup; batch scoring job writes predictions; endpoints for clusters and predictions.
- **Frontend:** cluster scatter plot, fund ranking table with "why" explanations (SHAP bars).
- **Viva focus:** Why walk-forward instead of random split; class imbalance; choice of metrics; silhouette score; what SHAP values mean; model versioning; training offline vs serving online.

### Phase 8 – Recommendations  · `phase-08-recommendations` · `v0.8.0`

- **Backend:** allocation per goal from risk category + years to goal (glide rule) and mean-variance optimisation; fund picks from the predicted top quartile within the right categories; reasons attached.
- **Database:** `recommendations` (goal_id, allocation JSON, funds JSON, reasons, created_at). *As built:* also `as_of`, risk category, horizon, expected return and volatility as columns and an `inputs` JSON (capital market, frontier, rules, model version); four sleeves, no gold/international (no long fund history) (ADR-011).
- **Frontend:** per-goal recommendation panel; simulation re-run with the recommended allocation.
- **Viva focus:** Markowitz efficient frontier; constraints in optimisation; why recommendations are stored (audit, history).

### Phase 9 – Portfolio tracker  · `phase-09-portfolio` · `v0.9.0`

- **Database:** `transactions` (user, fund, goal, date, amount, units, type), `holdings` (derived/materialised per user–fund). *As built:* holdings per user, goal and fund (unique with NULLS NOT DISTINCT; NULL goal = unassigned), with FIFO cost and realised gain; transactions also store the NAV used; deleting a goal keeps its transactions as unassigned (ADR-012).
- **Backend:** XIRR via Newton-Raphson (tested against Excel's XIRR), on-track/off-track per goal, rebalancing alerts when allocation drifts beyond a threshold.
- **Frontend:** add-transaction form, holdings table, goal progress vs plan chart, alerts banner.
- **Viva focus:** XIRR vs CAGR; Newton-Raphson convergence; derived vs stored data (why/when to materialise holdings); transactions and consistency.

### Phase 10 – Conversational assistant  · `phase-10-chatbot` · `v0.10.0`

- **Backend `chatbot/`:**
  - Gemini client (`google-genai`), API key from env.
  - **Tool registry:** each tool = name, description, JSON parameter schema, Python function that calls existing services (`run_simulation`, `list_goals`, `create_goal`, `get_fund_metrics`, `compare_funds`, `get_recommendations`, `get_portfolio_status`, `explain_term`).
  - **Orchestration loop:** user message → Gemini (with tools) → tool call → execute with the logged-in user's permissions → result back to Gemini → final answer (+ chart payload).
  - **RAG:** investor-education documents chunked, embedded, stored in pgvector; similarity search for `explain_term`.
  - **Guardrails:** system prompt limits scope; no personally identifying data sent; numbers only from tool results; fallback message if the API fails or rate-limits.
- **Database:** `chat_sessions`, `chat_messages`, `tool_calls` (tool, arguments, result, latency – audit trail), `kb_documents`, `kb_chunks` (embedding `vector` column). *As built:* 10 tools (`get_fund_metrics` searches by name; added `goal_calculator`, `get_risk_profile`); `create_goal` saves only after a confirmed preview (enforced in code); a grounding check records numbers not found in tool results; `gemini-3.5-flash` with `gemini-2.5-flash` as fallback, `gemini-embedding-001` (768 dims) with an HNSW cosine index; answers streamed as server-sent events; 20 knowledge articles written for the project (ADR-013).
- **Frontend:** chat panel with streaming responses, suggestion chips, inline charts when a tool returns simulation data.
- **Viva focus:** What is function calling; why the LLM must not do arithmetic; RAG vs fine-tuning; embeddings and cosine similarity; prompt injection and how scope is limited; rate limits and graceful degradation; privacy.

### Phase 11 – Reports and administration  · `phase-11-reports-admin` · `v0.11.0`

- **Backend:** PDF plan export (WeasyPrint or ReportLab); admin endpoints (users, pipeline runs, model versions); `audit_log` written for key actions. *As built:* ReportLab (no system libraries; "Rs" instead of ₹); `audit_log` append-only through a database trigger, actor kept without a foreign key; administrators created with `python -m app.admin make-admin`; admin model rollback and assistant statistics (ADR-014).
- **Frontend:** "Download my plan" button; admin dashboard (role-protected).
- **Viva focus:** Role-based access control; audit logging; server-side PDF generation.

### Phase 12 – Testing and evaluation  · `phase-12-evaluation` · `v0.12.0`

- Backend coverage report; frontend component tests (Vitest + Testing Library); a few end-to-end tests (Playwright) for the main flows.
- **ML evaluation report:** walk-forward results, comparison with a naive baseline ("last year's top funds").
- **Return-model comparison:** success probabilities under the 4 models for sample goals.
- **Chatbot evaluation:** ~100-question test set → correct-tool rate, numeric accuracy, out-of-scope refusal rate, hallucination rate with/without RAG.
- **UAT:** 5–10 users, feedback form, results table.

### Phase 13 – Deployment  · `phase-13-deploy` · `v1.0.0`

- Frontend → Vercel; backend → Render; database → a free managed PostgreSQL with pgvector (e.g. Neon). Check current free-tier terms when deploying.
- Environment variables set in each platform; CORS restricted to the frontend domain; database migrations run on deploy; seed demo user + data for the viva.

### Phase 14 – Report and presentation

- Assemble the 150–180 page report from the phase documents, ADRs, test results and screenshots.
- PowerPoint presentation; demo script for the viva; full code appendix.

---

## 5. Living documents (updated every phase)

| Document | Contents |
|---|---|
| `docs/architecture.md` | Component diagram, request flow, folder responsibilities |
| `docs/database.md` | Mermaid ER diagram, table dictionary (column, type, constraint, meaning), migration list |
| `docs/api.md` | Endpoint table (method, path, auth, purpose); FastAPI serves the full interactive spec at `/docs` |
| `docs/decisions/ADR-NNN-*.md` | One page per major decision: context, options considered, decision, consequences |
| `CHANGELOG.md` | One entry per tag |

---

## 6. Open items

- [ ] Submission deadline for the synopsis and the final report (adjust the estimates above)
- [ ] GitHub repository name and visibility (private recommended until evaluation)
- [ ] Install: Python 3.12, `uv`, Docker Desktop, GitHub CLI (`gh`)
- [ ] Gemini API key from Google AI Studio (needed only from Phase 10)
