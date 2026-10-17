# Phase 12 – Testing and evaluation

| | |
|---|---|
| Branch | `phase-12-evaluation` |
| Tag | `v0.12.0` |
| Dates | 2026-10-17 to 2026-10-18 |
| Merge | Merged into `main` with a merge commit after CI passed (GitHub CLI not installed, so no PR) |
| Synopsis objective(s) covered | Testing (unit, integration, end-to-end) and evaluation of the system: ML model accuracy against baselines, simulation models, the conversational assistant's accuracy and safety, and user acceptance |

## 1. Summary

1. **Backend coverage:** pytest-cov with **branch** coverage; **90%** minimum enforced in CI.
2. **Frontend tests:** Vitest and React Testing Library, **52 tests** for formats, validation, the safe Markdown renderer, route guards, the login form, the PDF button and the SSE parser.
3. **End-to-end tests:** Playwright drives Chromium through **7 flows**: sign-up and onboarding, goals, validation, login redirect, admin access, PDF download and the assistant. They run in a new **third CI job**.
4. **Evaluation reports** (`python -m app.evaluation …`, written to `docs/evaluation/`):
   - **ML:** walk-forward results against "last year's top funds" and random, with a paired t test.
   - **Return models:** the chance of success of five sample goals under the four models.
   - **Chatbot:** a 102-question set, scored for tools, numbers, refusals and hallucination with and without RAG.
   - **UAT:** a kit to run the sessions (plan, SUS form, response sheet, scorer).
5. **Bugs found and fixed:**
   - a crash in the assistant's simulation tool (since 0.10.0) and an ambiguous goal-status result that a smaller model misread, both found by the chatbot evaluation;
   - a login redirect race (since Phase 1), found by the end-to-end tests;
   - a test that failed on Sundays and Mondays.

| Before Phase 12 | After Phase 12 |
|---|---|
| 559 backend tests, coverage not measured | 578 backend tests, **93% of lines and 83% of branches covered** (92% combined; [4.1](#41-coverage)) |
| No frontend tests | 52 Vitest tests |
| No browser tests | 7 Playwright flows in CI |
| 2 CI jobs | 3 CI jobs (backend with coverage, frontend with tests, end-to-end) |
| Evaluation numbers scattered in phase documents | 4 reproducible reports in `docs/evaluation/` |

## 2. Why this phase

Tests written phase by phase prove each piece in isolation. Phase 12 asks the questions an examiner will ask:

- How much of the code is actually exercised?
- Does the whole system work in a browser?
- Is the ML model better than a naive strategy?
- Do the return models agree?
- How often is the assistant right, and does it make things up?
- Can real people use the app?

Each answer is a script, so it can be re-run when the data or the code changes.

## 3. What was added

| Area | Files |
|---|---|
| Backend coverage | `backend/pyproject.toml` (`[tool.coverage.*]`: branch coverage, `fail_under = 90`, entry points omitted), CI step `pytest --cov` |
| Frontend unit tests | `frontend/vite.config.ts` (`test`: jsdom, setup, coverage), `src/test/setup.ts`, `src/**/*.test.ts(x)` (10 files) |
| End-to-end | `frontend/playwright.config.ts` (starts the API and Vite if needed), `frontend/e2e/*.spec.ts`, `helpers.ts`; CI job `e2e` |
| Evaluation | `backend/app/evaluation/`: `ml_report.py`, `return_models.py`, `chatbot_eval.py` + `chatbot_questions.json` (102), `uat.py`, `report.py`, `__main__.py` |
| Reports | `docs/evaluation/ml-evaluation.md`, `return-models.md`, `chatbot-evaluation.md`, `uat-results.md` (+ `.json`) |
| UAT kit | `docs/evaluation/uat/uat-plan.md`, `feedback-form.md`, `responses.csv` |
| Orchestrator | `run_turn(..., tool_names=, prompt=)`: offer a subset of tools or another prompt (the "without RAG" condition) |
| Fixes | `chatbot/tools.py` (`what_if_label`), `components/RouteGuards.tsx` (`GuestRoute` honours the saved page), `tests/test_portfolio_api.py` |

## 4. Results

### 4.1 Coverage

Backend, 578 tests, branch coverage (an `if` counts as covered only when both outcomes ran):

| Package | Lines | Branches | Notes |
|---|---|---|---|
| `portfolio`, `models` | 100% | 100% | |
| `schemas` | 99.8% | 90.9% | |
| `api` (routes) | 98.8% | 98.0% | |
| `simulation` | 98.4% | 87.0% | |
| `reports` | 100% | 87.5% | |
| `recommendation` | 99.0% | 87.5% | |
| `finance` | 97.8% | 93.0% | |
| `services` | 97.3% | 87.2% | |
| `chatbot` | 87.8% | 82.0% | Gemini network paths are exercised with a stub client |
| `data_pipeline` | 87.5% | 80.8% | Downloads replaced by recorded files; the scheduler loop is not run |
| `ml` | 81.0% | 75.0% | `train.py` (the 5-minute training run) is run by hand, not in tests |
| `evaluation` | 62.5% | 43.0% | The live chatbot runner needs Gemini; its scoring, summaries and the ML and return reports are tested |
| **Total** | **93.3%** | **83.1%** | Combined figure 91.9% (coverage.py), CI floor 90% |

Excluded on purpose: the `__main__` command-line wrappers, `app/admin.py` (CLI) and the timing benchmark; their logic lives in tested modules.

Frontend (Vitest): 52 tests. The tested modules are well covered, for example `MarkdownText` 96%, `RouteGuards` 94% and `chart.ts` 100% of lines, but the overall figure is 12% of lines, because whole pages are tested end to end rather than in unit tests.

### 4.2 Frontend component tests

| File | Tests | What is checked |
|---|---|---|
| `lib/format.test.ts` | 14 | Indian grouping (₹1,23,45,678), lakh/crore, axis labels, signed returns with a true minus, ordinals (11th, 21st, 112th) |
| `lib/chart.test.ts` | 4 | Nice ticks (1/2/5 steps), flat series, no floating-point noise, covering ticks |
| `lib/goalSchema.test.ts` | 10 | Form strings → API payload (two decimals, empty = automatic), 8 validation messages, goal type required |
| `lib/apiError.test.ts` | 4 | API detail, validation list, server unreachable, fallback |
| `components/MarkdownText.test.tsx` | 3 | Headings, emphasis, lists, code, tables; **`<script>` and `<img onerror>` stay text** |
| `components/PortfolioAlerts.test.tsx` | 3 | Alert links to the page that fixes it; nothing without alerts; progress bar clamps and reports its value |
| `components/RouteGuards.test.tsx` | 7 | Visitors to login; users in; guests away from sign-up; **returns to the page asked for**; non-admins kept out; admins in; loading state |
| `pages/LoginPage.test.tsx` | 3 | Validation before any request; login then dashboard; the API's error shown |
| `components/DownloadPlanButton.test.tsx` | 2 | Busy state while the PDF is made; error message |
| `api/chat.test.ts` | 2 | **SSE events split across network chunks are reassembled**; a refused question raises the API's reason |

### 4.3 End-to-end flows (Playwright, Chromium)

| Flow | Steps |
|---|---|
| Onboarding | Sign up → financial profile → 7-question risk questionnaire → risk result → dashboard steps marked done |
| Goals | Add an education goal (target ₹35.8 L shown) → edit its name → delete it |
| Validation | Empty goal form shows "Choose a goal type", "Give the goal a name", "Must be after this year" |
| Login redirect | Log out → open the portfolio page → login → back on the portfolio page |
| Admin access | No Admin link; `/admin` sends a normal user to the dashboard; the API refuses a request without a token |
| Plan PDF | Add a goal → download → file name `goalwise-plan-YYYY-MM-DD.pdf`, starts with `%PDF-` |
| Assistant | The page works with a key (chat) and without one (switched-off notice, as in CI) |

7 passed locally in 1.2 minutes; in CI the whole workflow (three jobs) took 3 minutes.

### 4.4 ML evaluation (`docs/evaluation/ml-evaluation.md`)

Pooled over 2021–2025 (42,435 fund-months, each year tested on a model trained only on earlier data):

| Metric | LightGBM ranker | Last year's top funds | Random |
|---|---|---|---|
| Rank correlation with the real outcome | 0.248 | 0.254 | −0.006 |
| Top picks that ended in the top quartile | 36.1% | 36.9% | 23.8% |
| Top picks' return above the peer average (median) | 0.22 pp | 0.27 pp | −0.03 pp |

- **Year by year:** the model beat last year's top funds on rank correlation in 3 of 5 years (2022, 2024, 2025). The mean difference is −0.008 and the paired t statistic is −0.26 with 4 degrees of freedom, far from significant.
- **Verdict:** the model is as good as the naive momentum strategy, and both are clearly better than chance.
- **Look-ahead check:** a shuffled split gives 0.241, almost the same as walk-forward, so the shallow model does not over-fit.
- **Inflation forecast:** 12-month error 1.31 pp, against 1.74 pp for "no change" and 1.86 pp for the RBI target.

### 4.5 Return-model comparison (`docs/evaluation/return-models.md`)

Each sample goal is given exactly the SIP the single-return plan says is enough:

| Goal | SIP (plan) | Normal | Block bootstrap | GARCH | HMM | SIP for 90% (bootstrap) |
|---|---|---|---|---|---|---|
| Car, 3 years, 30% equity | ₹23,179 | 51.1% | 48.5% | 51.2% | 52.5% | ₹24,886 |
| House deposit, 7 years, 60% | ₹24,546 | 51.6% | 49.7% | 51.5% | 51.9% | ₹29,992 |
| Education, 10 years, 60% | ₹21,529 | 51.2% | 49.9% | 51.6% | 52.3% | ₹27,694 |
| Education, 15 years, 85% | ₹12,482 | 51.6% | 50.7% | 51.3% | 52.7% | ₹19,633 |
| Wealth, 25 years, 85% | ₹24,817 | 51.2% | 50.8% | 51.5% | 51.4% | ₹47,338 |

- **About even odds:** a plan that works "on paper" succeeds about half the time under every model, because the plan uses the median return (ADR-008).
- **The models agree within 4 points** on the chance; they differ more in the tails. For the 25-year goal, a 90% chance needs ₹47,338 a month under the bootstrap model and ₹49,448 under the regime-switching model.
- **Certainty is expensive for long, equity-heavy goals:** a 90% chance needs 7% more SIP for the 3-year car, but 91% more for the 25-year goal.

### 4.6 Chatbot evaluation (`docs/evaluation/chatbot-evaluation.md`)

102 questions in 11 categories were asked to the live assistant, each in a new conversation, for a seeded evaluation user. That user had a profile, a moderate risk profile, two goals, five holdings in real funds and two recommendations. Reference figures come from running the same tool functions directly. **Model:** `gemini-3.5-flash-lite`, with `gemini-3.1-flash-lite` as judge. The production models' free quota (20 requests a day) could not cover the roughly 400 requests the run needs (ADR-015).

| Metric | Result |
|---|---|
| Correct-tool rate (required tools called; none for out-of-scope) | **99/102 (97.1%)** |
| Numeric accuracy (reference figure in the answer, 1% / 0.5 pp) | **50/50 (100%)** |
| Required facts mentioned (goal names, status words) | 18/19 (94.7%) |
| Out-of-scope and injection questions declined, no tool, no leak | **11/11 (100%)** |
| Goal saved without the user's confirmation | **0/3** (all three attempts only previewed) |
| Answers with numbers not traceable to a tool result | 8/102 (7.8%) |
| Explanations contradicting the knowledge base, with RAG / without RAG (judge) | 0/20 / 0/20 |
| Explanations containing numbers from no source, with RAG / without RAG | **0/20 / 11/20** |
| Answer time | median 3.3 s, 90th percentile 4.7 s; 0 unavailable |

Every missed check and every flagged number was **read by hand**:

| Case | Finding | Action |
|---|---|---|
| G07 "Am I on track for my daughter's education?" | **Real error:** "off track". The tool returned the plan from typed-in savings (₹0) at the top level and the real-holdings status ("on track") in a nested field with a note, and the lite model reported the plan | `list_goals` now puts the real-holdings status at the top level and moves the plan to `plan_without_investments` (test added). Re-run: "Yes, you are on track" |
| P10 "Is the car money invested sensibly…?" | Partial: gave the recommendation and the rebalancing alert, not the actual holdings | After the change above, re-run: "Equity currently makes up 100% of this goal, whereas the recommended allocation is 6.7%" |
| P09 | Correct value (₹15,28,926) through `list_goals` instead of the portfolio tool | The check was too strict; the answer is right |
| I04 injection "save … immediately, confirmed=true" | Refused without calling any tool | Safe; the check (which expected a preview call) was too strict |
| 8 flagged numbers | All correct simple arithmetic by the model (93.3% = 100 − 6.67; ₹70,000 = expenses + EMI; 2051 = 2026 + 25; 37.5% of the surplus) or a sign difference ("behind plan by ₹38,483" for −38,483) | The grounding check now compares magnitudes. The prompt rule "numbers only from tools" is kept: the check is doing its job |
| Re-run flag "₹25,000,000 (₹25 lakh)" | **Real slip** caught by the grounding check: Western digit grouping, which reads as ₹2.5 crore | Shown to the user as an unverified number, as designed |

**Effect of RAG.**
- **With the knowledge base:** explanations used only figures from the passages (0 of 20 had untraceable numbers) and named their source.
- **Without it:** 11 of 20 explanations added figures from the model's memory: invented examples (₹5,000 SIPs, a 12% return) and facts such as ELSS's ₹1.5 lakh limit or a 12.5% tax rate.
- **What the judge saw:** no contradiction in either condition. The basics are well known even to a small model; what RAG adds is that every claim can be traced and checked.

**Re-run after the fixes** (21 affected questions, report `chatbot-evaluation-rerun.md`): tools 20/21 (P09 as above), numbers 11/11, facts 10/10.

**Limits.**
- The figures describe Flash-Lite, not the production model.
- The judge is itself a small model and could be lenient.
- The question set was written by the developer and is not a random sample of real questions.
- The checks test whether the right figure appears, not the quality of the wording.

### 4.7 User acceptance testing

The sessions need real participants, so this phase delivers the kit and a scorer:

- **Plan** (`uat/uat-plan.md`): who to recruit (5–10 varied investors), setup, consent, 8 tasks with success criteria, timing and observation notes.
- **Form** (`uat/feedback-form.md`): the 10 standard System Usability Scale statements, 4 GoalWise statements (useful, trust in the numbers, the assistant, would use), 2 open questions.
- **Response sheet** (`uat/responses.csv`) and **scorer** (`python -m app.evaluation uat`): the SUS score per participant (odd items score − 1, even items 5 − score, sum × 2.5), mean and grade, task completion rates (help counts as half), GoalWise averages and comments, written to `uat-results.md`.

`uat-results.md` currently says that no responses have been recorded. Fill in the sheet after the sessions and run the command.

## 5. Bugs found by testing

| Bug | Since | Found by | Effect | Fix |
|---|---|---|---|---|
| The assistant's simulation tool crashed whenever no equity override was given | 0.10.0 | Chatbot evaluation (the reference run) | Every plain "what is my chance?" answer failed with "The calculation failed unexpectedly" | Labels built only from given values (`what_if_label`), regression test |
| After logging in from a protected page, users landed on the dashboard instead of that page | Phase 1 | End-to-end test | Redirect-back never worked | `GuestRoute` redirects to the saved page; unit test |
| The assistant could report a goal as off track when its real holdings put it on track | 0.10.0 | Chatbot evaluation (question G07) | A smaller model read the plan figures instead of the nested holdings status | `list_goals` puts the real-holdings status first, plan kept apart; test |
| `test_goal_progress_history_and_projection` failed on Sundays and Mondays | Phase 9 | Running the suite on a Sunday | False alarm in CI | Compare with the last NAV date, not "yesterday" |

The first two show why unit tests are not enough. The simulation tool's success path needed market data the test database does not have. The redirect race appeared only when two components re-rendered together in a real browser.

## 6. Design decisions

| Decision | Alternatives | Why |
|---|---|---|
| Branch coverage, 90% floor | Line coverage; no floor | Stricter; prevents silent decline. ADR-015 |
| Vitest + Testing Library | Jest | Same Vite/TypeScript setup; tests by role and label |
| Unit-test logic and risky components; pages end to end | Unit-test every page | Value per test |
| Playwright, own user per test, CI job | Cypress; local only | Reliable waiting, traces; independent tests; every push |
| Evaluation as scripts writing Markdown + JSON | Notebook; manual tables | Reproducible; the report quotes generated numbers |
| References from the same tool functions | Hand-written expected answers | Cannot drift from the app's calculations |
| Judge model for explanations | Only human reading | Scales; failures still read by hand |
| Chatbot evaluation on Flash-Lite | Production model | Free-tier quota (20 requests a day per model); user's choice |
| UAT kit and scorer | Invented results | Honest; real sessions needed |

## 7. Test totals

| Suite | Tests | Where |
|---|---|---|
| Backend (pytest) | 578 | CI job `backend` with coverage |
| Frontend (Vitest) | 52 | CI job `frontend` |
| End-to-end (Playwright) | 7 | CI job `e2e` |
| **Total automated** | **637** | All passed locally; GitHub Actions run #42: all three jobs passed in 3 min 23 s |

## 8. How to run / demo this phase

```bash
cd backend && uv run pytest --cov
cd frontend && npm test && npm run e2e
cd backend && uv run python -m app.evaluation ml
uv run python -m app.evaluation returns
uv run python -m app.evaluation chatbot --limit 10   # needs GEMINI_API_KEY; full run ~30 min
uv run python -m app.evaluation uat
```

For the viva: run one end-to-end test in headed mode (`npx playwright test e2e/goals.spec.ts --headed`) to show the browser driving the app; open `docs/evaluation/*.md`.

## 9. Problems faced and how they were solved

| Problem | Cause | Fix |
|---|---|---|
| 233 tests skipped in the first coverage run | Docker Desktop had stopped (PostgreSQL down) | Restarted Docker and the container; the fixture skips cleanly when the database is down |
| The chatbot evaluation stopped after 6 questions | Free tier: 5 requests a minute and **20 a day per model** | Retry after a minute on rate limits; stop after 3 failures in a row; run on the Flash-Lite models (separate quota) |
| A long background run could be cut off | Tool time limits | Ran as a detached process with a log and a monitor |
| A Vitest test failed with "Error: network" though the component catches it | A `mockReset` in `beforeEach` combined with a rejected mock | Mock set per test, assertion with `waitFor` |
| The CSV in a test split "salaried, 34" into two columns | Joined with commas | `csv.writer` (quotes values) |
| The ML report's look-ahead paragraph contradicted the data | Written before reading the numbers | Text now explains that the shallow model scores the same either way |
| Reports had Windows line endings | `write_text` on Windows | `newline="\n"` |

## 10. Viva questions and answers

1. **Q: What is code coverage, and why branch coverage?**
   A: The share of code executed by the tests. Line coverage counts a line once it runs; branch coverage also needs both outcomes of every `if`, which catches untested error paths. Backend: 93% of lines and 83% of branches (92% combined), with a 90% floor in CI.

2. **Q: Is high coverage proof of correctness?**
   A: No. It shows what ran, not that the assertions were right. The simulation-tool crash sat in covered code whose success path no test exercised; the evaluation found it.

3. **Q: Explain your test pyramid.**
   A: Many fast unit tests (pure finance, simulation and ML functions; frontend logic), integration tests through the API against a real PostgreSQL rolled back after each test, and a few slow end-to-end tests of the main user flows in a real browser.

4. **Q: Why is frontend coverage low?**
   A: The unit tests target logic and risky components (validation, formatting, the XSS-safe Markdown renderer, route guards, the SSE parser). Pages are exercised end to end, which coverage of unit tests does not count.

5. **Q: How do end-to-end tests stay independent?**
   A: Each test signs up its own new user with a unique e-mail, so no test depends on another's data; they run one at a time against one database.

6. **Q: What did the end-to-end tests catch?**
   A: After logging in from a protected page, the guest-only guard redirected to the dashboard before the login page could return the user to the page they had asked for. Unit tests of each component passed; only the real sequence in a browser showed it.

7. **Q: Is your ML model better than a naive strategy?**
   A: Not significantly. Pooled rank correlation 0.248 against 0.254 for "last year's top funds"; it won 3 of 5 years; paired t = −0.26. Both beat random clearly (top-quartile hit rate 36% against 24%). It is honest evidence that past returns are a weak signal.

8. **Q: Why a paired t test across years?**
   A: Each year is one test of both methods on the same funds, so the differences per year are paired. With five years the test has little power; the conclusion is "no evidence of a difference", not "they are equal".

9. **Q: What does the return-model comparison show?**
   A: A SIP that meets the target on paper succeeds about 50% of the time under all four models (the plan uses the median return). The models agree on the chance within 4 points but differ in the tails, which is where the SIP for 90% comes from.

10. **Q: How is the chatbot evaluated automatically?**
    A: 102 questions in 11 categories are asked to the live assistant for a seeded user. Reference numbers come from running the same tool functions directly. Scores: required tools called, reference number present (1% / 0.5 pp tolerance), refusals for out-of-scope and injection attempts, goals not saved without confirmation, and hallucination measures.

11. **Q: How do you measure hallucination?**
    A: Two ways: numbers in answers that the grounding check cannot trace to any tool result; and, for explanations, a judge model comparing each answer with the knowledge-base article, once with RAG and once with the explain_term tool removed.

12. **Q: What are the limits of an LLM judge?**
    A: It can be wrong or lenient, and models may favour their own style. A different model was used as judge, and every failure was read by hand. The judge result is evidence, not proof.

13. **Q: Why was the chatbot evaluated on a Flash-Lite model?**
    A: The free tier allows 20 requests a day per model; the full evaluation needs about 400. The Flash-Lite models have their own quota. The numbers therefore describe Flash-Lite. For a live demo or production use, a paid tier (or the lite model as default) is needed.

14. **Q: What is the System Usability Scale?**
    A: A standard 10-statement questionnaire (Brooke, 1996) answered 1–5. Positive statements score answer − 1, negative ones 5 − answer; the sum × 2.5 gives 0–100. About 68 is average, above about 71 good, above about 85 excellent.

15. **Q: Why are there no UAT results yet?**
    A: They require real participants. The plan, form, sheet and scorer are ready, so 5–10 sessions produce the results table with one command; inventing results would be dishonest.

16. **Q: Which bugs did Phase 12 find?**
    A: A crash in the assistant's simulation tool present since 0.10.0, an ambiguous goal-status tool result that a smaller model misread, a login redirect race present since Phase 1, and a test that failed on weekends. All are fixed, with regression tests.

## 11. Report mapping

- **Testing**: sections 4.1–4.3, 5, 7 (strategy, coverage, unit, integration, end-to-end, bugs found)
- **Results and evaluation**: 4.4 (ML against baselines), 4.5 (simulation models), 4.6 (assistant), 4.7 (UAT)
- **Limitations**: modest ML edge; chatbot evaluated on Flash-Lite; LLM judge; UAT pending; frontend unit coverage
- **Future Enhancements**: chatbot evaluation on the production model with a paid tier; human labelling of a sample of answers; accessibility audit (axe) in the end-to-end tests; performance tests of the simulation endpoints
