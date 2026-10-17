# User acceptance testing (UAT) plan

**Goal:** check with real people that GoalWise is usable and useful for planning goals, and that they understand and trust what it shows.

## Participants

5 to 10 people who make their own money decisions, as varied as possible:

| Kind | Why |
|---|---|
| Salaried, 25-40, some mutual fund experience | The main target user |
| Salaried, new to investing | Is it understandable without jargon? |
| Self-employed or with irregular income | Different risk capacity |
| 45+, thinking about retirement | Retirement planner |
| A student or recent graduate | First goals, small SIPs |

Record a short profile for each (e.g. "salaried, 34, invests via SIPs"); no names in the results.

## Setup

- GoalWise running locally (or the deployed site after Phase 13) with market data loaded and the models trained.
- Each participant creates their **own account** and uses made-up or rough figures. Tell them not to enter real account numbers, PAN or other identifiers.
- Session: 30-40 minutes, one participant at a time, you observing and taking notes. Do not help unless they are stuck for more than about a minute. Note it as "with help" (0.5).
- Consent: explain that the test is for an MCA project, that only anonymous scores and comments are kept, and that they can stop at any time.

## Tasks

Read each task aloud; do not say where to click. Score: **1** completed alone, **0.5** completed with a hint, **0** not completed.

| # | Task | Done when |
|---|---|---|
| T1 | Create an account and complete your financial profile | Profile saved |
| T2 | Find out your risk profile | Risk category shown |
| T3 | Add a goal you care about (e.g. a child's education) and find out the monthly SIP it needs | They can state the required SIP |
| T4 | Find out how likely the goal is to succeed, and what SIP would give a 90% chance | They can state both numbers |
| T5 | Get a recommendation: how should the money be invested, and why? | They can explain the split in their words |
| T6 | Record that you invested ₹50,000 in a fund for that goal last year, then see how it is doing | Holding visible with value and gain |
| T7 | Ask the assistant a question about your plan and one about a term you do not know | They read both answers |
| T8 | Download your plan as a PDF | PDF opened |

Also note the total time and anything that confused them (where they hesitated, what they misread).

## Questionnaire (after the tasks)

Use `feedback-form.md`: the 10 System Usability Scale statements, 4 GoalWise statements and two open questions.

## Recording and results

1. Copy each participant's scores into `responses.csv` (one row each; columns described in the form).
2. Run `uv run python -m app.evaluation uat` in `backend/`. It writes `docs/evaluation/uat-results.md` with the SUS score per participant and on average, task completion rates and the comments.
3. In the report, summarise the problems observed (most frequent first) and what was changed in response.

**Interpreting SUS:** 68 is average; above about 71 is "good" and above about 85 "excellent" (Bangor, Kortum and Miller, 2009). With 5-10 participants, report the range as well as the mean.
