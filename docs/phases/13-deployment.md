# Phase 13 – Deployment

| | |
|---|---|
| Branch | `phase-13-deploy` |
| Tag | `v1.0.0` |
| Dates | 2026-10-18 |
| Screenshot | `docs/screenshots/phase-13-waking.png` (the waking-up screen) |
| Merge | Merged into `main` with a merge commit after CI passed (GitHub CLI not installed, so no PR) |
| Synopsis objective(s) covered | A working system available on the internet: React frontend, FastAPI backend and PostgreSQL with pgvector on free cloud services, with the configuration in version control |

## 1. Summary

GoalWise can now be deployed for free, with every setting in the repository:

- **Vercel** serves the React build.
- **Render** runs the API as a Docker container.
- **Neon** hosts PostgreSQL 16 with pgvector.
- **GitHub Actions** refreshes the market data every night.

1. **Container:** `backend/Dockerfile` builds the API from the same `uv.lock` as development and CI.
   - On start, it runs the migrations and then one uvicorn worker.
   - It runs as an unprivileged user.
2. **Blueprints:**
   - `render.yaml` describes the free web service: region, health check, settings and secrets to ask for. Render deploys only after CI passes.
   - `frontend/vercel.json` sets the single-page-app rewrite, caching and security headers.
3. **Data:**
   - `python -m app.deploy copy-data` streams the reference data from the local database to the hosted one (2.58 million rows in 90 s locally).
   - `demo-user [--reset]` builds a complete demo household through the normal services.
4. **Fitting a 512 MB server:** a limit on concurrent Monte Carlo runs and fewer malloc arenas. Both were measured in a memory-capped container (§4).
5. **Sleeping services:**
   - The frontend's `ServerGate` explains the minute-long wake-up.
   - The database connection timeout is configurable.
   - The nightly data refresh moved from the in-process scheduler to GitHub Actions.
6. **Production settings:**
   - `postgres://` URLs are accepted.
   - Exact CORS origins, plus an optional pattern for preview deployments.
   - The development JWT secret is refused in production (since Phase 1).

| Before Phase 13 | After Phase 13 |
|---|---|
| Runs only on the developer's machine | Deployable to Vercel + Render + Neon at no cost, step by step in `docs/deployment.md` |
| Market data and models exist only locally | Copied to any database with one command; refreshed daily by GitHub Actions |
| Demo data typed in by hand | `demo-user --reset` rebuilds the demo household in seconds |
| Two concurrent worst-case simulations would exceed 512 MB | Simulations queue; peak 445 MB with three concurrent worst-case requests |
| A sleeping API would look broken | "Waking up the server…" screen, then the app |

## 2. Why this phase

The examiner must be able to open GoalWise in a browser, and UAT participants must be able to use it from home. Free hosting brings limits that do not exist on a laptop:

- 512 MB of memory and a tenth of a CPU;
- services that sleep;
- no persistent disk and no free cron;
- a free database that expires after 30 days on one provider.

Phase 13 adapts the app to these limits, checks the adaptations under the same limits locally, and writes the steps down. Accounts must be created by the owner, so the deployment itself is a guide, not a script holding stored credentials.

## 3. What was added

### 3.1 Database

No schema changes; still at migration `0012`.

- The production database is migrated by `alembic upgrade head`, which the container runs on every start.
- `copy-data` fills the reference tables. It never copies user data.
- Tests create a second database, `goalwise_test_copy`, to copy into.

### 3.2 Backend

| File | Responsibility |
|---|---|
| `backend/Dockerfile`, `backend/.dockerignore` | `python:3.12-slim` + `libgomp1` (LightGBM) + uv 0.13.0. Dependencies sit in their own layer (`uv sync --frozen --no-dev`). Unprivileged user. `MALLOC_ARENA_MAX=2`. Command: `alembic upgrade head && uvicorn … --port $PORT --proxy-headers` |
| `app/core/config.py` | `database_url` validator (`postgres://`, `postgresql://` → `postgresql+psycopg://`); `database_connect_timeout`; `cors_origin_regex`; `simulation_concurrency` (≥ 1) |
| `app/core/database.py`, `app/main.py` | Connect timeout from the settings; `allow_origin_regex` for CORS |
| `app/simulation/limits.py` | `simulation_slot()`: a process-wide `BoundedSemaphore(SIMULATION_CONCURRENCY)` around `engine.run` (goal simulations, comparisons, the assistant's tool) and the lifetime retirement run |
| `app/deploy/copy_data.py` | `REFERENCE_TABLES` in foreign-key order; `copy_tables(source, target, tables, replace)`. Checks the migration revision and the columns, refuses a filled target unless `replace` (then `DELETE`, which fails if user data still refers to a fund), streams `COPY … TO STDOUT` into `COPY … FROM STDIN`, then moves each id sequence past the copied ids |
| `app/deploy/demo.py` | `create_demo_user(db, email, password, name, reset)`. Password checked by the sign-up schema. Profile, moderate risk profile, education/car/house goals, retirement plan, SIPs and lump sums in four real funds dated relative to today, a recommendation per goal |
| `app/deploy/__main__.py` | `python -m app.deploy copy-data --target URL [--source] [--table …] [--replace]` and `demo-user [--email] [--name] [--reset]` (password from `DEMO_PASSWORD`, else generated and printed once) |
| `app/data_pipeline/__main__.py` | Exits with status 1 when a job fails, so scheduled runs show as failed |
| `render.yaml` | Free Docker web service `goalwise-api`, Singapore, `rootDir: backend`, health check `/api/health`, `autoDeployTrigger: checksPass`. Settings: `ENVIRONMENT=production`, generated `JWT_SECRET_KEY`, `DATABASE_URL`/`CORS_*`/`GEMINI_API_KEY` asked for once, Flash-Lite models, `SIMULATION_CONCURRENCY=1`, `DATABASE_CONNECT_TIMEOUT=15`, scheduler off |
| `.github/workflows/data-refresh.yml` | 18:30 UTC (00:00 IST) and on demand: `daily_nav`, `fund_metrics`, `index_history`, `inflation` (may fail) against `PRODUCTION_DATABASE_URL`. Runs only when the repository variable `DATA_REFRESH` is `on` |

No endpoints were added.

### 3.3 Frontend

| File | Responsibility |
|---|---|
| `src/components/ServerGate.tsx` | Wraps the app. With an API on another origin (`VITE_API_BASE_URL` set), polls `/api/health` (15 s timeout per try, every 3 s) before rendering. After 1.5 s, shows "Waking up the server…" with the reason. After 2 minutes, shows "Try again". With a same-origin API (development, tests), renders at once |
| `src/main.tsx` | `ServerGate` outside the query client, auth provider and router, so no request is made before the API answers |
| `frontend/vercel.json` | Vite build to `dist`. Every path rewritten to `index.html` (deep links survive a refresh). `assets/*` cached for a year (hashed names). `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY` |

### 3.4 Integration and orchestration

```mermaid
sequenceDiagram
    participant U as Browser
    participant V as Vercel
    participant R as Render (sleeping)
    participant N as Neon (sleeping)
    U->>V: GET /
    V-->>U: index.html + assets
    U->>R: GET /api/health
    Note over R: container starts:<br/>alembic upgrade head, uvicorn
    U-->>U: after 1.5 s: "Waking up the server…"
    U->>R: GET /api/health (retry every 3 s)
    R->>N: SELECT 1, pgvector check (wakes Neon)
    N-->>R: ok
    R-->>U: 200 {"status": "ok"}
    U->>R: POST /api/auth/login, GET /api/auth/me … (CORS: Vercel origin only)
```

## 4. Key logic explained

### 4.1 Memory on a 512 MB server

The production image was run with `docker run --memory=512m --memory-swap=512m`. The container's peak memory was read from `/sys/fs/cgroup/memory.peak`.

| Situation | Peak |
|---|---|
| Idle after start-up (fitting libraries preloaded) | ~200 MB (250 MB after the first runs) |
| Goal simulations, all 4 models; model comparison | 269 MB |
| Retirement simulation, retire 58, plan to 100 | 374 MB |
| Worst case the API accepts (retire 55, plan to 105: 69 years × 12 months × 10,000 paths) | 374 MB |
| Two worst-case requests at once, no limit | **killed (out of memory)** |
| Three at once, `SIMULATION_CONCURRENCY=1` | 503 MB |
| Three at once, limit + `MALLOC_ARENA_MAX=2` | **445 MB** (repeatable; back to 244 MB afterwards) |

**Why a semaphore and not fewer paths?** Results stay the same as on a laptop (10,000 paths, same seed, same numbers). A queued request waits about a second; a smaller simulation would be less accurate. The semaphore is process-wide, which is enough because Render runs one uvicorn worker.

**Why malloc arenas?** FastAPI runs synchronous endpoints in a thread pool, and glibc gives threads separate memory pools ("arenas"). Memory freed by one request's thread stays in that thread's pool and is not reused by the next request's thread. With two arenas, freed memory is reused.

### 4.2 Copying reference data

```text
check: target migrated? same alembic revision? same columns?   -> otherwise refuse
for table in funds, nav_history, fund_metrics, index_history, inflation_data,
             ml_models, fund_predictions, fund_clusters, kb_documents, kb_chunks:
    COPY table (cols) TO STDOUT   --stream-->   COPY table (cols) FROM STDIN
    setval(id sequence, max(id) + 1, false)
commit once at the end (all or nothing)
```

- Parents come before children, so foreign keys hold at every step.
- Ids are kept, because predictions refer to funds and models by id.
- The sequence step matters: without it, the next fund added by the pipeline would get id 1 and collide.
- Vectors travel in pgvector's text form. The test checks that a cosine search on the copy finds the right chunk.

### 4.3 Waking-up logic (`ServerGate`)

| State | Shown | Next |
|---|---|---|
| `checking` | nothing (usually lasts milliseconds) | `ready` on a 2xx; `waking` after 1.5 s |
| `waking` | spinner, "Waking up the server…" and why | `ready` on a 2xx; `failed` after 2 minutes |
| `failed` | "The server is not answering" + Try again | `waking` (polling restarts) |
| `ready` | the app | – |

## 5. Design decisions

Full table in ADR-016. In short:

| Decision | Alternatives considered | Why this choice |
|---|---|---|
| Neon for PostgreSQL | Render PostgreSQL, Supabase | Render's free database expires after 30 days; Neon includes pgvector and has no time limit |
| Docker on Render | Native Python runtime | Same lockfile; LightGBM's OpenMP library installed explicitly; the same image was tested locally under the same memory cap |
| Migrations on container start | Manual, paid pre-deploy command | Free plan; a no-op when up to date |
| Copy reference data with COPY | Re-run the pipeline on the server; pg_dump | The server is too small for the 35-minute pipeline and training; no PostgreSQL client tools needed on Windows; safety checks |
| Queue simulations | Fewer paths; paid plan | Same results as locally; measured to fit |
| Explain the cold start | Keep-alive pings | Pings would use the free hours and keep Neon awake |
| GitHub Actions for the nightly jobs | In-process scheduler; paid cron | A sleeping service misses its schedule |
| Deploy after CI passes | Deploy every push | A failing commit never reaches users |

## 6. Testing

| Test | Type | Result |
|---|---|---|
| `test_config.py` (9): Neon/Render URL forms → psycopg; production refuses the development secret; CORS origins trimmed; the regex admits preview deployments and rejects look-alikes; simulations never overlap with one slot; the slot count follows the setting | unit | Pass |
| `test_deploy.py` (7): copy with ids, sequences and vectors; refuse a filled target, `--replace`; refuse unknown tables, mismatched or missing migrations; demo account complete (4 goals, holdings in all funds, more than 50 transactions); `--reset` replaces the account and its data; password rules; no market data | integration (two real databases) | Pass |
| `ServerGate.test.tsx` (3): same-origin = no waiting; waking screen then app after two failures; give up, then retry | component | Pass |
| Production image locally: `docker build`, run with `ENVIRONMENT=production`, a `postgres://` URL, 512 MB cap → migrations 0001–0012 on start, health `ok` | manual | Pass |
| `copy-data` into an empty database: 2,577,781 rows in 90 s; `demo-user` run inside the container | manual | Pass |
| `vite build` with `VITE_API_BASE_URL` + `vite preview`: waking screen while the API was stopped, login page by itself once it started; cross-origin login; dashboard, portfolio, PDF, admin | manual (browser) | Pass |
| Memory: §4.1 | manual | Pass with the limit |
| Whole suite | | 593 backend tests pass (5 min 45 s locally, 92.0% combined coverage; new modules: `copy_data` 97%, `demo` 93%, `limits` and `config` 100%), 55 frontend tests, 7 end-to-end flows |

How to run: `cd backend && uv run pytest --cov` · `cd frontend && npm test`.

## 7. Test totals and coverage

| | Phase 12 | Phase 13 |
|---|---|---|
| Backend tests | 578 | 593 |
| Backend coverage (lines / branches / combined) | 93.3% / 83.1% / 91.9% | 93.4% / 83.4% / 92.0% |
| Frontend tests | 52 | 55 |
| End-to-end flows | 7 | 7 |

## 8. How to run / demo this phase

**The production image locally** (Docker Desktop running, from the repository root):

```bash
docker build -t goalwise-api backend
docker run --rm -p 8080:8000 --memory=512m -e ENVIRONMENT=production -e JWT_SECRET_KEY=<random> -e SIMULATION_CONCURRENCY=1 -e DATABASE_URL=postgres://goalwise:goalwise@host.docker.internal:5432/goalwise -e CORS_ORIGINS=http://localhost:4173 goalwise-api
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8080 npm run build && npm run preview
```

**The real deployment:** follow `docs/deployment.md`, sections 3–9:

- Neon project → `alembic upgrade head` → `copy-data` → `demo-user`;
- Render blueprint;
- Vercel project with `VITE_API_BASE_URL`;
- `CORS_ORIGINS` set to the Vercel address;
- the data-refresh secret and variable.

**For the viva:** open the site a couple of minutes early to wake the API. Run `demo-user --reset` the same morning.

## 9. Problems faced and how they were solved

- **Render's free PostgreSQL expires after 30 days.** Found while checking the current terms, as the plan asked. The database moved to Neon.
- **Two simulations at once killed the container.** Found by load-testing the production image under a 512 MB cap. Fixed with the concurrency limit, plus `MALLOC_ARENA_MAX=2` after the queued peak still reached 503 MB.
- **The first memory reading was misleading (405 MB at idle).** The `demo-user` command had run inside the container, so it counted in the container's peak. After a restart, the API alone measured 258 MB.
- **The demo portfolio first raised rebalancing alerts on almost every goal.** The car goal held equity and a corporate-bond fund, but GoalWise recommends short-term debt (liquid funds) for a 2-year horizon. The demo now follows each goal's recommended mix, except the education goal, kept slightly equity-heavy to show one alert.
- **Hosted URLs use `postgres://`, which SQLAlchemy rejects.** The settings now rewrite it.
- **Pipeline failures were invisible to a scheduler.** The CLI always exited with 0; it now exits with 1 when a job fails.
- **Accounts cannot be created by the assistant.** The deployment is written as a guide for the owner. Everything that can be checked without accounts was checked locally under production settings.

## 10. Viva questions and answers

1. **Q:** Where does each part of GoalWise run, and why there?
   **A:**
   - The React build runs on Vercel: static files on a CDN, with a build on every push.
   - The FastAPI app runs on Render as a Docker container. Render's free plan supports Docker, which lets us install the OpenMP library LightGBM needs.
   - PostgreSQL with pgvector runs on Neon, because Render's free database is deleted after 30 days while Neon's free plan is permanent and includes pgvector.

2. **Q:** How do database migrations reach production?
   **A:** The container's start command runs `alembic upgrade head` before starting uvicorn. Render's free plan has no pre-deploy hook, and running an up-to-date upgrade is a no-op. The first time, I also ran it from my machine against Neon before copying data.

3. **Q:** Why not run the data pipeline on the server instead of copying data?
   **A:** The first full load downloads 1,482 fund histories and index data, about 35 minutes, and then trains the models. A free service with 0.1 CPU and 512 MB would take far longer, could be killed, and loses its files on restart. The data was built once locally, so `copy-data` streams it with PostgreSQL's COPY protocol: 2.58 million rows in 90 seconds locally. Only the small daily increment runs in production, on GitHub Actions.

4. **Q:** What safety checks does `copy-data` make?
   **A:**
   - The target must be migrated, at the same Alembic revision, with the same columns.
   - It refuses a target that already holds reference data unless `--replace` is given. Even then it uses `DELETE`, which fails if user holdings still refer to a fund, rather than silently deleting user data.
   - It never copies user tables.
   - It moves id sequences past the copied ids.
   - It commits once, so a failure leaves nothing half-copied.

5. **Q:** How did you make the API fit in 512 MB?
   **A:** I measured first:
   - The API idles at about 200–250 MB.
   - One worst-case lifetime simulation peaks at 374 MB.
   - Two at once were killed.

   A process-wide semaphore (`SIMULATION_CONCURRENCY=1`) makes simulations queue. `MALLOC_ARENA_MAX=2` makes threads reuse freed memory, bringing three concurrent requests down to a 445 MB peak. Results are unchanged: still 10,000 paths.

6. **Q:** Is a semaphore enough if there are several server processes?
   **A:** No. It limits runs within one process. Render's free plan runs one uvicorn worker (one process), so it is enough here. With several workers or instances, each would need its own budget, or a shared queue such as Redis or a job table.

7. **Q:** What happens when someone opens the site after it has been idle?
   **A:** The API container has been stopped. `ServerGate` pings `/api/health`; if no answer comes within 1.5 seconds, it explains that the free server is waking up and keeps retrying every 3 seconds. When the health check succeeds, the app renders and makes its normal requests. Without this, the first requests would time out and look like errors.

8. **Q:** Why not keep the server awake with pings?
   **A:**
   - It would use most of Render's 750 free hours.
   - The health check also queries the database, so it would keep Neon awake and use its 100 compute-hours.
   - Free plans are meant to sleep. Explaining the delay is honest and costs nothing.

9. **Q:** How are secrets handled?
   **A:**
   - None are in the repository. `render.yaml` marks `DATABASE_URL`, `GEMINI_API_KEY` and the CORS settings `sync: false`, so Render asks for them once; Render generates `JWT_SECRET_KEY`.
   - The data-refresh workflow reads `PRODUCTION_DATABASE_URL` from GitHub's encrypted secrets.
   - In production the app refuses to start with the development JWT secret.
   - The Docker build context excludes `.env`.

10. **Q:** What does CORS protect here, and how is it configured?
    **A:** Browsers block a page on one origin from reading responses from another unless the server allows it. The API allows only the Vercel origin listed in `CORS_ORIGINS`. Optionally, a regular expression admits Vercel preview addresses; it must match the whole origin, and a test checks that `goalwise-x.vercel.app.evil.com` is rejected. CORS does not replace authentication: every data endpoint still requires a JWT.

11. **Q:** Why does Render deploy only after CI passes?
    **A:** `autoDeployTrigger: checksPass` waits for the GitHub checks: lint, 593 backend tests with coverage, frontend tests and build, and end-to-end tests. A commit that breaks anything never replaces the running version.

12. **Q:** Why a direct Neon connection rather than the pooled one?
    **A:** Neon's pooler is PgBouncer in transaction mode, where consecutive statements can run on different server connections. psycopg 3 prepares statements it runs repeatedly, and a prepared statement lives on one server connection, so pooling would break them. One uvicorn worker needs only a few connections, well within Neon's direct limit.

13. **Q:** How would you scale this beyond the free tier?
    **A:**
    - A paid instance with more memory, which allows several workers and more concurrent simulations.
    - Move simulations to a background worker with a queue, returning results by polling or SSE.
    - Use Neon's paid compute so the database stays warm.
    - Add Redis for the rate limits and caches that are now per process.
    - Move model training to a scheduled job on a larger machine, with the model files in object storage instead of the container's disk.

14. **Q:** How did you test the deployment without deploying?
    **A:** I ran the production image locally the way Render runs it:
    - `ENVIRONMENT=production`, a generated secret, a 512 MB memory cap, and a `postgres://` URL to a brand-new empty database.
    - Migrations ran on start; I copied the data, seeded the demo inside the container, and measured memory.
    - I served the production frontend build from another origin and used it in a browser, including the waking screen with the API stopped.

## 11. Report mapping

- **Implementation:** deployment architecture, Docker image, configuration, data migration.
- **Testing:** load and memory test, production-like environment test.
- **Results:** live system for the viva.
- **Appendix:** `docs/deployment.md` (user guide for deployment), `render.yaml`, `Dockerfile`, `vercel.json`.
