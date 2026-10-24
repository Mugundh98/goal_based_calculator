# Synopsis

The synopsis submitted with the project proposal is reproduced below.

**GoalWise: An ML-Driven Goal-Based Investment and Retirement Planning System with a Conversational AI Assistant**

## Abstract

GoalWise is a web application that helps an Indian household plan each life goal and its retirement, choose mutual funds for them, and track whether the money actually invested is on course. Instead of one portfolio and one number, it works goal by goal: a child's education in 10 years, a car in 2, a house in 6, retirement at 58. For every goal it inflates the cost to the target year, works out the monthly SIP needed, and tests the plan with a Monte Carlo simulation of 10,000 market paths under four return models. A machine-learning model ranks about 1,500 mutual funds within their peer groups, and a mean-variance optimiser with an age-based glide path recommends an asset mix and funds for each goal. A portfolio tracker values real transactions (XIRR, FIFO cost) and raises drift and off-track alerts, and a conversational assistant answers questions in plain language using the same calculations, grounded in a knowledge base through retrieval-augmented generation. The system is built with React and TypeScript, FastAPI (Python) and PostgreSQL with pgvector, tested with 606 backend, 71 frontend and 7 end-to-end tests, and runs on free cloud services.

## Introduction and significance

Most Indian households save for several goals at once, yet the tools they use answer only one question at a time. SIP calculators assume the market returns the same rate every year; fund-rating sites rank funds on past returns without saying which fund suits which goal; brokerage apps show holdings without linking them to a goal. The resulting plans hide inflation (₹25 lakh of education today costs about ₹44.8 lakh in 10 years at 6% inflation), uncertainty (investing exactly the "required" SIP gives only about a 50% chance of success) and drift (invested money slowly moves away from the plan).

The project builds a system that plans each goal separately, measures the chance of success under realistic market behaviour, recommends a suitable mix of funds using real data and machine learning, tracks actual investments against the plan, and explains all of it in plain language. It is significant for users, who gain a transparent planning tool, and academically, as it brings together financial mathematics, statistics, machine learning, optimisation and generative AI in one tested, deployed system.

## Objectives

1. Profile each user's finances and risk tolerance with a transparent, rule-based questionnaire.
2. Plan any number of goals: inflate each target, project savings and step-up SIPs, and compute the SIP required.
3. Estimate the probability of reaching each goal by Monte Carlo simulation under four return models, and the SIP needed for 50%, 75% or 90% certainty.
4. Plan retirement in two phases, with the chance that the money lasts.
5. Build a market-data pipeline for Indian mutual funds and compute risk-return metrics.
6. Rank funds within peer groups with a machine-learning model validated walk-forward against naive baselines, and explain each ranking.
7. Recommend an asset allocation and funds for each goal.
8. Track actual transactions: holdings, XIRR, goal progress, rebalancing and off-track alerts.
9. Provide a conversational assistant that uses the system's own calculations and a curated knowledge base, without inventing numbers.
10. Provide reports, administration with an audit log, and an online deployment.

## Scope

In scope: individual Indian investors planning with mutual funds; goals in rupees with Indian inflation; direct-plan, growth-option funds for recommendations; 14,136 schemes in the fund list, about 1,500 with full NAV history; an English-language assistant. Out of scope: buying or selling units, other asset classes as separate classes, tax computation, and personalised advice under SEBI regulations.

## Methodology and mathematical techniques

The system is built incrementally in 14 phases, each a Git branch with its own tests, design record and continuous-integration run before it is merged. The principal techniques are:

- **Goal mathematics:** inflated target and SIP future value with monthly rate i = (1 + r)^(1/12) − 1.

```latex
T = C\,(1+\pi)^{n} \qquad FV_{SIP} = P\,\frac{(1+i)^{m}-1}{i}\,(1+i)
```

- **Risk profiling:** willingness and capacity each scored 0–100; the lower decides the category.
- **Monte Carlo simulation:** 10,000 paths from a normal model, a 12-month block bootstrap of real history, GARCH(1,1) and a two-state hidden Markov model.

```latex
\sigma_t^{2} = \omega + \alpha\,\varepsilon_{t-1}^{2} + \beta\,\sigma_{t-1}^{2}
```

- **Fund metrics:** CAGR, rolling returns, volatility, maximum drawdown, Sharpe and Sortino ratios.
- **Machine learning:** LightGBM ranking within peer groups with SHAP explanations, K-Means clustering, SARIMA inflation forecasting, walk-forward validation.
- **Recommendation:** mean-variance optimisation within glide-path bounds.

```latex
\max_{w}\; w^{\top}\mu - \tfrac{\lambda}{2}\,w^{\top}\Sigma\,w \quad \text{subject to}\; \textstyle\sum w = 1,\; l \le w \le u
```

- **Portfolio return:** XIRR solved by Newton–Raphson with a bisection fallback.

```latex
\sum_{k} \frac{CF_k}{(1+x)^{(d_k-d_0)/365}} = 0
```

- **Assistant:** a large language model calling 10 typed tools, with explanations grounded by retrieving the closest of 86 knowledge-base passages by cosine similarity of 768-dimension embeddings in pgvector.

## Computer skills: software and hardware

Front end: React 19, TypeScript, Vite, Tailwind CSS. Back end: Python 3.12, FastAPI, SQLAlchemy, Alembic, JWT with Argon2. Database: PostgreSQL 16 with pgvector. Data science: NumPy, pandas, SciPy, statsmodels, arch, hmmlearn, scikit-learn, LightGBM, SHAP. AI: Google Gemini API. Testing: pytest, Vitest, Playwright. Tools: Git, GitHub Actions, Docker. Hosting: Vercel, Render, Neon. Hardware: a 64-bit PC with 8 GB RAM for development; the server runs within 512 MB; users need only a browser.

## Testing and evaluation

606 backend tests (92% coverage), 71 frontend tests and 7 end-to-end flows run on every change. The fund ranker's rank correlation (0.248) matches the momentum baseline (0.254) and beats random (−0.006). The plan's "required" SIP succeeds in about 49–53% of simulated futures under all four models. The assistant chose the correct tool for 97.1% of 102 test questions, reported all 50 reference numbers correctly and refused all 11 out-of-scope requests; with retrieval, no explanation contained untraceable numbers (11 of 20 without).

## Limitations and future research directions

Limitations: simulations learn from about 14 years of history; the ranker only matches a momentum baseline; only mutual funds are covered and taxes are not computed; the assistant depends on an external model; free hosting suits demonstration rather than many users. Future directions: more asset classes and tax-aware planning; automatic import of consolidated account statements; richer fund data; household-level simulation of correlated goals; Indian-language support; and user studies of whether probabilities change saving behaviour.
