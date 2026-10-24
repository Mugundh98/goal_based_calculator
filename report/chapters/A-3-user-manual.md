# User Manual

This manual explains how to use GoalWise and how to install it on a computer for development or demonstration.

## Using the deployed system

Open **https://goal-based-calculator-seven.vercel.app** in a browser. If the site has not been used for a while, a "Waking up the server" screen with a 60-second countdown appears while the free server starts; the login page follows automatically.

### Getting started

1. **Create an account.** Click *Create an account* and enter your name, e-mail and a password of at least 8 characters with a letter and a digit. Choose a security question and give its answer; it lets you reset a forgotten password later.
2. **Complete the dashboard steps.** The dashboard lists five steps: financial profile, risk profile, goals, retirement plan and investments. Each step links to its page and is ticked when done.
3. **Financial profile.** Enter your date of birth, employment, monthly income and expenses, loan payments, savings, existing investments and number of dependants. Amounts show digit grouping (1,50,000) as you type.
4. **Risk profile.** Answer the ten questions. The result shows your willingness and capacity to take risk; the lower of the two decides your category (conservative, moderate or aggressive), and the breakdown explains each factor.

### Planning goals

1. On **Goals**, click *Add goal*. Choose a type, give it a name, enter what it would cost today and the target year, and optionally what you have already saved, your monthly SIP and a yearly SIP increase.
2. The panel beside the form shows the cost in the target year, the monthly SIP needed and how far your current plan gets you.
3. Each goal card has three actions: **Simulate**, **Recommendation** and **Progress**.

### Simulating a goal

The simulation page shows the **chance of reaching the goal** across 10,000 simulated market futures, a **fan chart** of how the money could grow, and the **SIP needed for a 50%, 75% or 90% chance**. Use the *What if* panel to change the monthly SIP, the yearly increase, the target year or the share in equity — move a slider or type a value and press Enter — and the simulation re-runs. *Compare models* shows the result under all four return models. Saved runs can be reopened later.

### Retirement

On **Retirement**, enter the age you want to retire, the age to plan until, your monthly spending in today's money and what you have saved. The plan shows the corpus needed, the SIP to build it, the chance that the money lasts, a lifetime fan chart and a survival curve, and the withdrawal rate compared with the "4% rule".

### Funds and insights

**Explore** lists mutual funds with search, filters and sorting; a fund's page shows its NAV against the Nifty 50 and its risk and return metrics. **Insights** shows the model's fund rankings within each category with the reasons behind them, the behaviour clusters, the inflation forecast and how reliable the rankings have been.

### Recommendations

From a goal, open **Recommendation** to see the suggested split across large-cap equity, mid- and small-cap equity, long-duration debt and short-duration debt, the reasons for it, the efficient frontier and the funds chosen for each part. *Simulate this allocation* tests the recommendation.

### Tracking investments

1. On **Portfolio**, click *Add transaction*. Choose a purchase, a monthly SIP (past instalments are added in one go) or a redemption.
2. Search for the fund. If it is not listed, click *Can't find it? Add it yourself* and give its name and type.
3. Assign the transaction to a goal. Optionally tick *Enter the NAV myself* to use the NAV on your statement; for funds you added this is required.
4. The portfolio shows holdings, invested amount, current value, gain and XIRR, each goal's status against its plan, and alerts. Transactions can be **edited** or deleted from the list.
5. A goal's **Progress** page compares its value with the plan over time and shows what to move to rebalance.

### The assistant

On **Assistant**, ask questions such as "Am I on track for my car?", "What if I invest ₹25,000 a month for education?" or "What is a Sharpe ratio?". Answers show which tools were used and any charts. The assistant can create a goal for you, but only after you confirm its preview.

### Your account and reports

Click your **name** in the menu to open the account page: change your name or password, or set your security question. *Download my plan (PDF)* on the dashboard produces a report of your whole plan. If you forget your password, click *Forgot password?* on the login page, enter your e-mail, answer your security question and choose a new password.

### Administration

Administrators see an **Admin** menu: an overview of users and activity, user management (role and active status), the audit log, the status of data jobs, model versions (which can be activated or rolled back) and assistant statistics.

## Installing GoalWise locally

**Prerequisites:** uv (which installs Python 3.12), Node.js 20 or later and Docker Desktop.

1. Start the database from the project folder: `docker compose up -d`.
2. Start the backend in `backend/`: copy `.env.example` to `.env`, then run `uv sync`, `uv run alembic upgrade head` and `uv run uvicorn app.main:app --reload --port 8000`.
3. Start the frontend in `frontend/`: `npm install` and `npm run dev`, then open http://localhost:5173. The API documentation is at http://localhost:8000/docs.
4. Load market data (first time, about half an hour): `uv run python -m app.data_pipeline all`; then train the models (about five minutes): `uv run python -m app.ml train all`.
5. To enable the assistant, put a Google AI Studio key in `backend/.env` as `GEMINI_API_KEY` and run `uv run python -m app.chatbot ingest`.
6. To become an administrator: `uv run python -m app.admin make-admin you@example.com`.
7. To create the demonstration account: `uv run python -m app.deploy demo-user`.

**Running the tests:** `uv run pytest --cov` in `backend/`; `npm test` and `npm run e2e` in `frontend/`.
