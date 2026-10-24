# Results and Discussion

This chapter brings together what the finished system does and what the work found, and compares the outcome with the objectives set in Chapter 1.

## The system delivered

GoalWise version 1.2.0 is a working, deployed web application with the following capabilities:

- Account management with secure login, password changes and password recovery by security question.
- A financial profile and a two-part risk profile (willingness and capacity).
- Planning of any number of goals with inflation, current savings, SIPs and yearly step-ups.
- Monte Carlo simulation of each goal under four return models, with what-if controls and the SIP for 50%, 75% and 90% certainty.
- A two-phase retirement planner with the chance that the money lasts and a survival curve.
- A market data pipeline covering 14,136 schemes, with full histories and risk metrics for 1,482 funds, refreshed nightly.
- Machine-learning insights: fund rankings with reasons, behaviour clusters and an inflation forecast.
- Recommendations of an asset allocation and funds for each goal, with reasons and an efficient frontier.
- A portfolio tracker with XIRR, plan comparison, rebalancing and off-track alerts, the user's own NAVs, funds added by hand and editable transactions.
- A conversational assistant grounded in the system's calculations and a knowledge base.
- A downloadable PDF plan, an administration dashboard and an append-only audit log.

Table: Size of the delivered system

| Measure | Value |
| --- | --- |
| Backend source (Python) | about 16,200 lines |
| Frontend source (TypeScript, React) | about 11,600 lines |
| Automated tests | 606 backend, 71 frontend, 7 end-to-end |
| Database | 25 tables, 14 migrations |
| API | 74 endpoints |
| Reference data | about 2.58 million rows |
| Documentation | 14 phase documents, 18 architecture decision records |

## A worked example: the demo household

The demonstration account illustrates the results a user sees. The household is a salaried 36-year-old with two children, a moderate risk profile, ₹1.5 lakh monthly income and goals for a child's college education in ten years, a car in two years, a home down payment in six years and retirement at 58. About three years of SIPs and lump sums in four real funds are recorded against the goals.

For this household the system shows:

- **Goal plans:** each target inflated to its year (for example ₹25 lakh of education costs today becomes ₹44.8 lakh in ten years at 6% inflation) and the SIP required.
- **Portfolio:** a current value of about ₹11.7 lakh against ₹11.1 lakh invested, with an XIRR that reflects the actual dates of every instalment.
- **Alerts:** one goal off track (the home down payment needs a higher SIP), and one goal whose equity share has drifted above its recommended level (the education goal).
- **Recommendations:** a mostly liquid and short-debt mix for the car due in two years, and a growth-oriented mix for the ten-year education goal.
- **Simulation:** the chance of reaching each goal at its current SIP, and the SIP for a 90% chance.

The example shows the intended use of the system: rather than one projection, the user sees where each goal stands, how likely it is to succeed, and what action — a higher SIP, a later date or a rebalancing — would change that.

## Achievement of the objectives

Table: Objectives and their achievement

| No. | Objective (Chapter 1) | Achieved by | Status |
| --- | --- | --- | --- |
| 1 | Transparent risk profiling | Questionnaire and capacity scoring; the lower decides | Achieved |
| 2 | Goal planning with inflation and step-up | Goal manager and TVM library, verified to the paisa | Achieved |
| 3 | Probability of success by simulation | Four return models, 10,000 paths, SIP for a chosen certainty | Achieved |
| 4 | Two-phase retirement planning | Retirement planner with lifetime simulation | Achieved |
| 5 | Indian market data pipeline | AMFI, NSE and MOSPI loads, nightly refresh, metrics | Achieved |
| 6 | Validated, explained fund ranking | LightGBM with walk-forward validation and SHAP; matches the momentum baseline | Achieved; accuracy limited by the problem |
| 7 | Allocation and fund recommendations | Glide path with constrained mean-variance optimisation | Achieved |
| 8 | Tracking of real investments | Portfolio tracker with XIRR, plan comparison and alerts | Achieved |
| 9 | Grounded conversational assistant | Tool calling and RAG; evaluated on 102 questions | Achieved |
| 10 | Reports, administration, testing, deployment | PDF plan, admin dashboard, audit log, 684 automated tests, free cloud deployment | Achieved |

## Discussion

Three observations stand out from building and evaluating the system.

**Uncertainty changes the advice.** A deterministic calculator would tell the demo household that a certain SIP is "enough". The simulation shows that this SIP succeeds only about half the time and quantifies what certainty costs. For long horizons the cost is large, which argues for starting early and stepping SIPs up, both of which the system lets the user test immediately.

**Honest evaluation matters more than complex models.** The machine-learning ranker is a sophisticated model, yet it does not beat a one-line momentum rule on next year's outcome. Reporting this, rather than presenting the model as a forecast of winners, is part of the system's design: the rankings are offered as an explained comparison within peers, and the recommendations rely on the allocation, which matters far more for a goal's outcome than the choice between similar funds.

**Language models need structure.** The assistant is useful because it does not compute anything itself: every number comes from a tool, and every explanation is grounded in a source. The evaluation shows the effect directly — without retrieval, more than half of the explanations contained untraceable numbers.
