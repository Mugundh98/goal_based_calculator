# Data Sources and Sampling

The project's results depend on data: market data drives the simulations, the fund metrics and the machine-learning models, and test sets drive the evaluation of the models and the assistant. This chapter describes where the data comes from, how it is cleaned, which population each analysis concerns, how samples are drawn from it, and why the sample sizes are adequate.

## Data sources

All data comes from free, public sources that need no API key.

Table: Data sources

| Source | Data | Frequency | Used for |
| --- | --- | --- | --- |
| AMFI (NAVAll.txt) | Latest NAV of every mutual fund scheme, with scheme code, name, fund house, category, plan and option | Every business day | Fund master; daily NAV updates; latest values of holdings |
| mfapi.in (AMFI history) | Complete daily NAV history of a scheme | Once per fund (backfill), cached | Fund metrics; simulation debt series; ML features and targets |
| NSE indices via Yahoo Finance | Daily closes of Nifty 50, Nifty 500 and Nifty Midcap 150 | Every trading day | Simulation equity series; benchmark charts; market features for ML |
| MOSPI CPI API | All-India consumer price index (base 2012) | Monthly | Inflation history and SARIMA forecast |
| Knowledge base (written for the project) | 20 investor-education articles (86 passages) | When articles change | Retrieval for the assistant |

Every load is recorded in a `job_runs` table with the rows read, written and rejected and the reason for each rejection, so the state of the data can always be explained.

## Data cleaning and validation

Raw data is never trusted. The pipeline applies these rules before anything is stored:

- **Parsing.** AMFI's file mixes category headers, fund-house headers and data rows; the parser tracks the current category and fund house and validates each data row (numeric code, positive NAV, valid date).
- **Classification.** Category text is normalised into asset classes (equity, debt, hybrid, index, ETF, fund of funds, solution-oriented, other), plan (direct or regular) and option (growth, IDCW, bonus).
- **Idempotence.** Rows are upserted on natural keys (scheme code; fund and date; index and date), so re-running a load writes nothing new. A partial unique index allows only one run of each job at a time.
- **Rejections.** Non-positive NAVs, impossible dates and malformed rows are rejected and listed in the job log.
- **Unit changes.** Some funds changed their face value (for example from ₹10 to ₹1,000 per unit), which looks like a hundred-fold jump in the NAV. These are detected as exact powers of ten and the series are restated, so returns and holdings stay correct.
- **Inconsistent official data.** MOSPI's API returns two different index values for January to May 2013, at the point where the 2012-base series was linked to the older series. The row that carries MOSPI's own published inflation is kept, and the choice is documented.

## Populations and samples

Different parts of the project study different populations. Table 4.3 summarises them; the sections that follow explain each.

Table: Populations, samples and sizes

| Analysis | Population | Sample used | Size |
| --- | --- | --- | --- |
| Fund master and explorer | All mutual fund schemes listed by AMFI | Census (all schemes) | 14,136 schemes |
| Fund histories and metrics | Open-ended, direct-plan, growth-option funds that are still active | Census of active funds in equity, hybrid, index and debt categories | 1,482 funds; 2,545,178 daily NAVs |
| Return models for simulation | Monthly returns of a diversified equity index and of bond funds | Longest unbroken run of common months | 164 months (about 13.7 years) |
| Monte Carlo outcome distribution | All possible future return paths under a model | Random sample of paths with a fixed seed | 10,000 paths per run |
| ML fund ranker | Fund-months in ranked peer groups with a known 12-month outcome | All labelled fund-months; walk-forward folds by year | 81,007 fund-months (2014–2025; 928 funds, 28 peer groups); 42,435 in the 2021–2025 test years |
| Fund clusters | Funds with three years of history | Census of eligible funds | About 1,000 funds |
| Inflation forecast | Monthly year-on-year CPI inflation | Full available series, walk-forward evaluation | Since 2012 |
| Assistant evaluation | Questions a user might ask about their plan | Purposive, stratified test set over 11 categories | 102 questions |
| User acceptance test | Adults who make their own money decisions | Purposive sample across five user profiles | 5–10 participants |

### Fund universe

The fund master is a census: every scheme AMFI publishes is stored, 14,136 in all. Full histories, however, are loaded only for funds that matter for planning and comparison: open-ended schemes in the direct plan and growth option, in the equity, hybrid, index and debt categories, that are still reporting NAVs. Direct plans are chosen because they carry no distributor commission, so their returns reflect the fund rather than its distribution cost; growth options are chosen because dividend (IDCW) options drop in value at every payout, which would look like a loss. Within this definition the selection is again a census — all 1,482 qualifying funds — so no sampling error arises from choosing funds.

### Market history for the simulation

The simulation needs two monthly return series. The **equity** series is the Nifty 500 index, which covers about 95% of the listed Indian market by capitalisation, sampled at each month-end close. The **debt** series is the median monthly return across all growth-option bond funds (corporate bond, banking and PSU, short and medium duration, gilt and dynamic bond) with data that month, requiring at least three funds; liquid, overnight and money-market funds behave like cash and are excluded, as are credit-risk funds, whose defaults and side pockets would distort the series. The median makes a single fund's accident irrelevant. The two series are aligned on the longest unbroken run of common months — 164 months — and the latest, incomplete month is dropped.

This history is used for the *shape* of risk — volatility, fat tails, clustering and regimes — not for the level of return. The reason is statistical: the standard error of the mean of 13.7 years of equity returns with 16.8% annual volatility is 16.8% / √13.7 ≈ 4.5% a year, so the historical average is far too uncertain to plan with. The expected return is instead an explicit assumption taken from the goal or the user's risk profile.

### Monte Carlo sample size

Each simulation draws 10,000 independent paths. The estimated probability of success p̂ is a proportion, so its standard error is √(p(1 − p)/N). At the least favourable value p = 0.5:

```latex
SE(\hat{p}) = \sqrt{\frac{0.5 \times 0.5}{10\,000}} = 0.005
```

A 95% confidence interval is therefore about ±1 percentage point, which is finer than any decision a user would make on it. Increasing the sample to 100,000 paths would narrow the interval to ±0.3 points but take ten times as long and use ten times the memory, which matters on the deployment server (Chapter 9). A fixed random seed makes every run reproducible, and the comparison of the four models uses the same random numbers for each, so differences between models are not sampling noise.

### Training and validation samples for the fund ranker

The unit of analysis is a fund-month: a fund at a month-end, described by 26 features built only from data up to that month, with a target equal to its quartile within its peer group over the following twelve months. Fund-months are labelled only within peer groups of at least eight funds that month, and quartiles are balanced by construction (19,013, 20,611, 19,867 and 21,516 fund-months from first to fourth quartile, out of 81,007). Index funds are not ranked, because their differences reflect the index they track rather than skill.

Random train–test splits are invalid for this kind of data: the twelve-month targets of adjacent months overlap, so a random split leaks the future into training. The model is therefore validated **walk-forward**. For each test year from 2021 to 2025, the model is trained on all earlier fund-months whose twelve-month outcome was already known before the test year began (a purge gap of twelve months), and evaluated on that year. The five yearly results are pooled (42,435 test fund-months) and also compared year by year with a paired t test against the baseline. A deliberately leaky random split is reported alongside to show the size of the bias it would have introduced.

### Test set for the assistant

The assistant is evaluated on 102 questions written for the purpose. The sample is **purposive and stratified**: it covers every capability the assistant should have and every way it should refuse, in proportions that reflect their importance rather than an unknown natural frequency.

Table: Strata of the assistant test set

| Category | Questions | What is tested |
| --- | --- | --- |
| Goals | 12 | Status of the user's goals |
| Calculator | 15 | Goal arithmetic (target, required SIP) |
| Simulation | 10 | Chance of success and what-if questions |
| Recommendation | 8 | Allocation and funds for a goal |
| Portfolio | 10 | Holdings, returns, alerts |
| Risk profile | 5 | The user's risk category and its reasons |
| Funds | 8 | Metrics and comparison of named funds |
| Explain | 20 | Financial concepts (from the knowledge base) |
| Out of scope | 8 | Requests the assistant must decline |
| Injection | 4 | Attempts to override its instructions |
| Create goal | 2 | Saving a goal only after confirmation |

Each question is asked in a new conversation for a freshly seeded evaluation user with a known profile, goals and portfolio. The reference answers are computed by calling the same tool functions directly, so "correct" means that the assistant reported what GoalWise itself calculates. The 20 explanation questions are asked a second time with retrieval disabled, to measure what retrieval contributes.

### User acceptance test sample

Usability is tested with a small purposive sample of 5 to 10 adults who make their own money decisions, chosen to vary across five profiles: salaried users aged 25–40 with mutual fund experience (the main target user), salaried users new to investing, self-employed users with irregular income, users over 45 thinking about retirement, and students or recent graduates. Small samples are standard in usability testing because most serious problems appear with the first few users; the System Usability Scale used here is known to give reliable scores with samples of this size, and the range is reported alongside the mean. Each participant performs eight tasks (Table 8.x in Chapter 8) with made-up figures and completes the SUS questionnaire.

## Data volumes

Table: Data volumes in the deployed database

| Table | Rows | Size |
| --- | --- | --- |
| nav_history | 2,545,178 | 167 MB with indexes |
| funds | 14,136 | 4 MB |
| index_history | 11,770 | 1.1 MB |
| fund_predictions | 2,048 | 2 MB |
| fund_clusters | 3,012 | 0.35 MB |
| fund_metrics | 1,344 | 0.3 MB |
| inflation_data | 180 | small |
| kb_chunks (with 768-dimension embeddings) | 86 | 0.8 MB |

The whole reference dataset — about 2.58 million rows and 190 MB — fits comfortably in the 1 GB free tier of the hosted database.

## Ethical handling of data

The market data is public. User data is limited to what planning needs and is visible only to its owner. Test participants use made-up figures and are identified only by a short anonymous profile. The evaluation user for the assistant is created for each run and deleted afterwards, and the assistant is instructed never to send names, e-mail addresses or identifiers to the language model provider.
