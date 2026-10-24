# Deployment

GoalWise is deployed on the internet at no cost, so that it can be demonstrated and used from any browser. This chapter describes the target environment, the changes made to fit free hosting, the deployment procedure and its verification.

## Deployment architecture

<!-- include: docs/phases/13-deployment.md sections="Summary" level=3 heading="none" -->

Table: Deployed components

| Component | Service | Plan and limits | Address |
| --- | --- | --- | --- |
| Website (React build) | Vercel | Hobby (free): static hosting, build on deploy | goal-based-calculator-seven.vercel.app |
| API (FastAPI in Docker) | Render | Free web service: 512 MB memory, 0.1 CPU; sleeps after 15 idle minutes | goal-based-calculator.onrender.com |
| Database (PostgreSQL 16 + pgvector) | Neon | Free: 1 GB storage, sleeps after 5 idle minutes | Singapore region |
| Nightly data refresh | GitHub Actions | Scheduled workflow | Runs at 00:00 India time |
| Language model | Google Gemini API | Free tier, Flash-Lite models | — |

## Adapting the system to free hosting

<!-- include: docs/phases/13-deployment.md sections="Key logic explained" level=3 heading="none" -->

## Deployment procedure

The deployment is described by files kept in the repository: a `Dockerfile` for the API, a `render.yaml` blueprint for the Render service, a `vercel.json` for the website and a GitHub Actions workflow for the nightly refresh. The steps were:

1. **Database.** Create a Neon project with PostgreSQL 16 in Singapore, apply all migrations with `alembic upgrade head`, and copy the reference data (funds, NAVs, metrics, indices, inflation, model outputs and the knowledge base — 2,577,781 rows) from the local database with the project's `copy-data` command, which streams rows with PostgreSQL's COPY protocol and refuses to overwrite data or copy a database onto itself.
2. **Demo account.** Create the demonstration account with the `demo-user` command, which builds a complete household — profile, risk profile, goals, retirement plan, three years of investments in real funds and recommendations — through the same services as the application.
3. **API.** Create a Render web service from the repository's `backend` folder using its Dockerfile, with the environment variables for the database address, the JWT secret, the allowed website origin, the Gemini key and the production settings. On every start the container applies any pending migrations and starts one Uvicorn worker.
4. **Website.** Create a Vercel project from the `frontend` folder with `VITE_API_BASE_URL` set to the API's address, and redeploy so the address is built into the site.
5. **Connect them.** Set the API's allowed origin (CORS) to the website's address.
6. **Verify.** Check the API's health endpoint, open the website, log in to the demo account and exercise the main features.

## Verification

After deployment the live system was checked end to end: the health endpoint reported version 1.2.0, a connected database and pgvector; the website's build contained the correct API address; the API accepted requests from the website's origin and refused others; and the demo account's portfolio, simulations, retirement plan, PDF report and assistant all worked against the hosted database. Later releases (1.1.0 and 1.2.0) were deployed the same way after their tests passed, with the database migrations applied automatically when the API restarted.

## Problems faced during deployment

<!-- include: docs/phases/13-deployment.md sections="Problems faced and how they were solved" level=3 heading="none" -->
