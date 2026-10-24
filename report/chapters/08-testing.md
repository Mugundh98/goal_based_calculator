# Testing and Evaluation

Testing answers whether the system does what it is specified to do; evaluation answers how well its models and its assistant perform. This chapter covers both: the testing strategy and its results, representative test cases, defects found by testing, and the evaluation of the machine-learning ranker, the return models, the assistant and usability.

## Testing strategy

Tests were written alongside the code in every phase, not after it. They are organised as a pyramid: many fast unit tests of the pure computational code, integration tests of the API against a real database, component tests of the user interface, and a few end-to-end tests that drive the whole system through a browser.

Table: Levels of testing

| Level | Scope | Tools | Count |
| --- | --- | --- | --- |
| Unit | Pure functions: financial formulas, simulation engine and models, retirement model, ML features and metrics, optimiser, XIRR, FIFO ledger, grounding check, formatting | pytest | Part of the 606 backend tests |
| Integration | API endpoints through FastAPI's test client against a real PostgreSQL database built from the migrations; authorisation, validation, database constraints, concurrency | pytest, PostgreSQL 16 with pgvector | Part of the 606 backend tests |
| Component | React components and form logic: formats, validation schemas, the safe Markdown renderer, route guards, forms, the waking-up screen, the transaction form | Vitest, React Testing Library, jsdom | 71 |
| End-to-end | The running system in Chromium: sign-up and onboarding, goals, validation, login redirect, admin access, PDF download, assistant | Playwright | 7 flows |

Three principles kept the tests trustworthy:

1. **Real database, isolated tests.** Integration tests run against a dedicated PostgreSQL database created from the real migrations (after downgrading to empty, which also tests the downgrades). Each test runs inside a transaction that is rolled back, so tests never affect one another.
2. **No network in tests.** Data-source parsers are tested on recorded samples of the real file formats, and the language model is replaced by a scripted fake that returns predetermined replies and tool calls, so tests are fast and deterministic.
3. **Independent references.** Financial results are checked against hand-calculated worked examples, against independent month-by-month simulations, and through round trips (for example, investing the computed required SIP must reach the target exactly).

The tests run automatically on GitHub Actions for every push, and a change can be merged only when all three jobs pass. Branch coverage of at least 90% is enforced.

## Representative test cases

Table: Representative test cases and results

| No. | Test case | Input | Expected result | Result |
| --- | --- | --- | --- | --- |
| TC1 | Register with a weak password | Password "onlyletters" | 422 with "must contain at least one letter and one digit" | Pass |
| TC2 | Log in with a wrong password | Correct e-mail, wrong password | 401 "Incorrect email or password"; failure recorded in the audit log | Pass |
| TC3 | Access another user's goal | Token of user B, goal id of user A | 404 Not Found | Pass |
| TC4 | Inflated target | ₹20,00,000 at 10% inflation for 15 years | ₹83,54,496.34 | Pass |
| TC5 | SIP future value equals month-by-month simulation | Four rate and term pairs | Equal to the paisa | Pass |
| TC6 | Required SIP reaches the target | Goal with savings and step-up | Projected value equals the target | Pass |
| TC7 | Re-running a data load | The same AMFI file twice | Second run writes 0 rows | Pass |
| TC8 | Zero volatility reproduces the plan | Simulation with σ = 0 | Every path equals the deterministic projection | Pass |
| TC9 | Bootstrap keeps month-to-month patterns | Alternating +5% / −5% history | Autocorrelation below −0.8 with 12-month blocks | Pass |
| TC10 | No look-ahead in ML features | NAVs after month t multiplied by 3 | No feature at or before t changes | Pass |
| TC11 | Optimiser respects the rules | Goal one year away | Equity within the glide-path bound; short debt minimum met | Pass |
| TC12 | XIRR matches Excel's documented example | Five dated cash flows | 0.373362535 | Pass |
| TC13 | Over-redemption refused | Sell more units than held on that date | 422; holdings unchanged | Pass |
| TC14 | Correction that breaks a later redemption | Reduce a purchase below a later sale | 409; transaction unchanged | Pass |
| TC15 | Fund added by hand is private | Another user requests it | 404; absent from the fund explorer | Pass |
| TC16 | Assistant saves a goal only after confirmation | create_goal without a "yes" | No goal stored; preview shown | Pass |
| TC17 | Password reset lockout | Five wrong answers in an hour | Sixth attempt returns 429 even with the right answer | Pass |
| TC18 | Production refuses the development secret | ENVIRONMENT=production with the default JWT key | Settings validation error at start-up | Pass |
| TC19 | Simulations never overlap with one slot | Three concurrent simulations, limit 1 | At most one running at a time | Pass |
| TC20 | Amounts are typed with Indian grouping | Typing 2500000 in a ₹ field | Shows 25,00,000; the plan reads 25 lakh | Pass |

## Results of testing and evaluation

<!-- include: docs/phases/12-evaluation.md sections="Results" level=3 heading="none" -->

## Defects found by testing

<!-- include: docs/phases/12-evaluation.md sections="Bugs found by testing" level=3 heading="none" -->

Later releases added further regression tests for the problems found after deployment: a data copy that read from the wrong database reported "0 rows" instead of refusing (now refused with an explanation), and a date-dependent test that failed when the start of its three-year window fell on a weekend.

## Final test totals

Table: Test totals at the final release (v1.2.0)

| Suite | Tests | Result |
| --- | --- | --- |
| Backend (pytest) | 606 | All pass; 93.4% of lines and 83.4% of branches covered (92.2% combined; minimum 90%) |
| Frontend (Vitest) | 71 | All pass |
| End-to-end (Playwright) | 7 flows | All pass |
| Continuous integration | 3 jobs per push | Green on every merged release |

## Discussion

The testing shows that the system behaves as specified, including in its failure cases (invalid input, unauthorised access, concurrent writes, data-source errors). The evaluation adds three findings that matter for how the system should be used:

1. **A single-rate plan is a coin toss.** Under all four return models, investing exactly the SIP that the deterministic plan calls "required" reaches the goal in only about half of the simulated futures. Certainty has a price that grows with the horizon: 7–9% more SIP for a 90% chance on a three-year goal, but 91–99% more on a 25-year goal. This is the central argument for simulation over single-number calculators.
2. **Fund selection from public data is hard.** The ranker's rank correlation with next year's outcome (0.248) is clearly better than random (−0.006) but no better than simply following last year's leaders within each category (0.254); the difference is not statistically significant. This agrees with the literature on performance persistence. The ranker's value lies in combining several signals, explaining each ranking and grouping funds by behaviour, not in a superior forecast, and the application says so on its Insights page.
3. **Grounding works.** The assistant chose the correct tool for 97.1% of questions, reproduced every reference number, refused every out-of-scope request and never saved a goal without confirmation. Retrieval made the difference for explanations: without the knowledge base, 11 of 20 explanations contained numbers that could not be traced to any source; with it, none did.
