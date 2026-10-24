# Introduction

## Background

Personal financial planning in India has changed rapidly over the last decade. Mutual fund assets under management have grown several-fold, and the systematic investment plan (SIP), a fixed amount invested every month, has become the most common way for salaried households to invest. At the same time, the responsibility for long-term goals has moved from employers and the state to individuals: a family that wants to educate its children, buy a home and retire comfortably must save for each of these itself, often for decades, in a market whose returns vary widely from year to year.

Professional financial planners approach this problem goal by goal. They ask what each goal will cost in the year it falls due, how much has already been set aside for it, how much risk the family can bear, and what monthly saving would be enough. They then choose a mix of assets whose risk suits the time left, and review the plan as markets and circumstances change. This advice is valuable but expensive, and SEBI-registered investment advisers serve only a small part of the population. Most households instead rely on online calculators, fund-rating websites and the applications of their brokers or banks.

These tools are useful, but each answers only a narrow question. A SIP calculator projects a single number using one assumed rate of return. A rating website ranks funds by their past returns without saying which fund suits which goal. A brokerage application shows what is held and how it has performed, but not whether each goal is on course. None of them tells a family the one thing it most needs to know: *how likely is it that we will have the money, and what would it take to be more certain?*

This project builds a system that answers that question, end to end, for Indian households investing through mutual funds.

## Problem statement

The tools commonly available to an individual investor hide three facts that decide whether a plan succeeds:

1. **Inflation.** A goal is usually stated in today's rupees. At 6% inflation, an education that costs ₹25 lakh today will cost about ₹44.8 lakh in ten years. A plan that targets ₹25 lakh is short by almost half before any market risk is considered.
2. **Uncertainty of returns.** Markets do not return the same rate every year. Even with the same average return, the order in which good and bad years arrive changes the outcome of a SIP. A plan that invests exactly the "required" SIP computed at a single expected rate reaches its goal in only about half of the possible futures, as Chapter 8 of this report demonstrates.
3. **Drift.** The money actually invested slowly moves away from the plan: contributions are missed, markets move one asset class ahead of another, and the share of equity grows or shrinks. Without tracking each goal against its plan, the gap is noticed only when it is too late to close.

The problem addressed by this project is therefore to **design and build a system that plans each goal separately, measures the chance of reaching it under realistic market behaviour, recommends a suitable mix of mutual funds using real data and machine learning, tracks actual investments against the plan, and explains all of this in plain language** — while being transparent about its assumptions and honest about the accuracy of its models.

## Significance of the project

The project is significant at three levels.

**For individual investors.** GoalWise turns a vague intention ("save for the children's education") into a concrete, testable plan: a target in the year it falls due, a monthly SIP, a probability of success and the cost of more certainty. Because every number is derived from a formula or a model shown in the application, a user can see *why* a recommendation is made rather than accepting a black-box verdict. The portfolio tracker closes the loop by comparing real investments with the plan and warning when a goal falls behind or its mix drifts.

**For the practice of financial technology.** The project shows how several techniques that are usually studied separately can be combined into one coherent product: financial mathematics (time value of money, XIRR), statistics (Monte Carlo simulation, GARCH and hidden Markov models), machine learning (gradient-boosted ranking, clustering, time-series forecasting), optimisation (mean-variance portfolio construction) and generative artificial intelligence (tool-calling language models and retrieval-augmented generation). It also shows how to evaluate each of them honestly against naive baselines, which is often missing from consumer finance tools.

**Academically.** The work exercises most of the subjects of the MCA programme in a single, realistic system: software engineering (requirements, design, version control, continuous integration), database design (a normalised relational schema of 25 tables with migrations), web technologies (a REST API and a single-page application), data structures and algorithms (vectorised simulation, FIFO lot accounting, root finding), statistics and machine learning, and deployment on cloud infrastructure. Every phase of the work is documented with its design decisions and tests, so the reasoning behind the system can be examined as well as its results.

## Objectives

The objectives of the project are:

1. To profile each user's finances and risk tolerance with a transparent, rule-based questionnaire that separates the willingness to take risk from the capacity to bear it.
2. To plan any number of financial goals: inflate each target to its year, project current savings and SIPs (with an optional yearly step-up), and compute the SIP required to reach the target.
3. To estimate the probability of reaching each goal by Monte Carlo simulation under four return models fitted to Indian market data, and to compute the SIP needed for a chosen level of certainty.
4. To plan retirement in two phases — accumulating a corpus and drawing it down until a chosen age — and estimate the chance that the money lasts.
5. To build a data pipeline for Indian mutual funds (AMFI net asset values, NSE index histories and MOSPI inflation data) and compute standard risk and return metrics for each fund.
6. To rank funds within their peer groups with a machine-learning model, validated walk-forward against naive baselines, and to explain each ranking.
7. To recommend an asset allocation and specific funds for each goal from its horizon and the user's risk profile.
8. To track actual transactions: holdings, returns (XIRR), each goal's progress against its plan, rebalancing needs and off-track alerts.
9. To provide a conversational assistant that answers questions using the system's own calculations and a curated knowledge base, without inventing numbers.
10. To provide reports, administration with an audit log, comprehensive automated testing, and an online deployment suitable for demonstration.

## Scope of the project

The project covers individual Indian investors who plan with mutual funds. Goals are stated in rupees and adjusted for Indian inflation. Recommendations are drawn from direct-plan, growth-option schemes, which carry no distributor commission and reinvest all gains. The fund master contains all 14,136 schemes published by AMFI; full daily histories are loaded for about 1,500 active direct-plan growth funds across equity, debt, hybrid and index categories. The assistant works in English.

The following are outside the scope of the project: buying or selling units (the system plans and tracks; it does not transact); direct equities, bonds, gold, real estate and international funds as separate asset classes; computation of income tax and capital gains; and personalised investment advice in the regulatory sense. The application states on every page that it is an educational tool and not investment advice.

## Methodology in brief

The system was built incrementally in fourteen phases, each adding one capability on top of the previous ones: project setup; authentication; risk profiling; goal planning; the market data pipeline; Monte Carlo simulation; retirement planning; machine-learning fund intelligence; recommendations; the portfolio tracker; the conversational assistant; reports and administration; testing and evaluation; and deployment. Each phase was developed on its own Git branch, documented with a phase report and an architecture decision record, verified by automated tests in a continuous-integration pipeline, and merged and tagged only when all tests passed. Chapter 5 describes the development method and the mathematical techniques in detail.

## Organisation of the report

The rest of this report is organised as follows.

- **Chapter 2** reviews the literature on goal-based investing, portfolio theory, Monte Carlo methods in financial planning, models of market returns, fund performance and machine learning, robo-advisory systems and retrieval-augmented language models, and surveys the existing tools.
- **Chapter 3** analyses the existing and proposed systems, the feasibility of the project and its functional and non-functional requirements, and lists the hardware and software used.
- **Chapter 4** describes the data sources, the populations and samples used for analysis, model training and evaluation, and the sample sizes chosen.
- **Chapter 5** explains the development methodology and the mathematical and statistical techniques: financial formulas, risk scoring, fund metrics, simulation models, machine learning, optimisation, portfolio accounting and the assistant.
- **Chapter 6** presents the system design: architecture, data flow, database schema, API and security.
- **Chapter 7** describes the implementation of each module with screenshots.
- **Chapter 8** covers testing and the evaluation of the models and the assistant.
- **Chapter 9** describes the deployment of the system on cloud services.
- **Chapter 10** discusses the results.
- **Chapter 11** concludes with the limitations of the work and guidelines for future research.

The appendices contain the project proforma, the synopsis, a user manual, the complete data dictionary and the presentation outline. The complete source code is provided in a separate appendix volume.
