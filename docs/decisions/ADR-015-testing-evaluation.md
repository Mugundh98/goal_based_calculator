# ADR-015: Testing and evaluation – a test pyramid in CI, evaluation as repeatable scripts

**Status:** Accepted · **Date:** 2026-10-18 · **Phase:** 12

## Context

By Phase 11 the backend had 559 tests but no coverage measurement. The frontend had no tests, and no test drove the whole stack through a browser. The ML models, return models and assistant had been checked phase by phase, but never evaluated together in a form the report can cite and anyone can re-run. Users had not tried the app.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Backend coverage | Line coverage; **branch coverage**; none | **pytest-cov with branch coverage, 90% minimum in CI** | Branch coverage also checks both outcomes of every `if`; a floor stops coverage from quietly falling |
| What to exclude | Nothing; **entry points** | **`__main__` modules, the admin CLI and the timing benchmark** | Thin command-line wrappers; their logic lives in tested modules. Model training stays counted (and shows as untested) |
| Frontend unit tests | Jest; **Vitest + Testing Library** | **Vitest (jsdom) + React Testing Library + user-event** | Runs on the same Vite config and TypeScript; tests use roles and labels as a user would |
| What to unit-test in the frontend | Every page; **logic and risky components** | **Formats, chart ticks, validation schemas, API error text, the safe Markdown renderer, guards, login form, download button, SSE parser** | Highest value per test; whole pages are covered end to end |
| End-to-end | Cypress; Selenium; **Playwright** | **Playwright with Chromium; Playwright starts the API and Vite itself; each test signs up its own user** | Auto-waiting, traces on failure, downloads supported; independent tests on one database |
| End-to-end in CI | Local only; **CI job** | **A third CI job with PostgreSQL, after the backend and frontend jobs** | Every push proves the main flows work in a real browser (no market data or Gemini key needed) |
| ML evaluation | Re-train for the report; **report from stored validation** | **Walk-forward results stored with each model version, compared with "last year's top funds" (momentum) and random, plus a paired t test across years** | Reproducible without re-training; the baseline the plan asked for is the momentum baseline already in the validation |
| Return models | Single example; **sample goals** | **5 sample goals (3–25 years, 30–85% equity), each given the plan's required SIP, under all 4 models on one seed** | Shows how often a plan that works on paper succeeds, and how the models differ |
| Chatbot evaluation | Manual spot checks; **scripted question set** | **102 questions in 11 categories, run against the live model for a seeded user; references from the same tool functions; automatic scoring; a judge model for explanations with and without RAG** | Repeatable and quantitative; references cannot drift from what the app calculates |
| Judge for explanations | Human only; **LLM judge + reading the failures** | **A second Gemini model compares each explanation with the knowledge-base article** | Scales to 40 judgements; its verdicts on failures were read by hand |
| Model for the chatbot evaluation | Production models; **lite models** | **`gemini-3.5-flash-lite` (fallback and judge `gemini-3.1-flash-lite`)** | The free tier allows 20 requests a day per model; the full run needs about 400. The lite models have their own quota. Results describe the lite models (the user's choice) |
| UAT | Skip; **kit to run** | **Plan with 8 tasks, SUS questionnaire plus 4 GoalWise questions, response sheet, scorer** | Real participants are needed; the kit makes the sessions consistent and the results one command |

## Decision

CI runs ruff, the backend tests with coverage (≥ 90%), the frontend linter, Vitest and the build, then Playwright end-to-end tests. `python -m app.evaluation ml | returns | chatbot | uat` writes Markdown and JSON reports to `docs/evaluation/`.

## Consequences

- The evaluation found two real bugs that the unit tests had missed: a crash in the assistant's simulation tool (since 0.10.0) and a login redirect race (since Phase 1). Both are fixed, with regression tests.
- Coverage is reported honestly: backend 94% (branches included); frontend unit coverage is low by design, because pages are covered end to end.
- The chatbot numbers describe the lite models. Re-running on the production model needs a paid tier (or many days of free quota).
- UAT results depend on the student running the sessions; until then `uat-results.md` says there are no responses.
