# ADR-006: Goal calculation conventions – effective monthly rate, annuity due, projections computed on read

**Status:** Accepted · **Date:** 2026-10-15 · **Phase:** 3

## Context

Phase 3 introduces the financial math every later module depends on (simulation, retirement, recommendations, chatbot). Several conventions change the numbers the user sees, so they must be fixed once and applied everywhere:

1. How an annual return becomes a monthly rate for SIPs.
2. Whether a SIP instalment is invested at the start or the end of the month.
3. Whether projections are stored or recalculated.
4. Which numeric type the formulas use, given that Phase 2 chose exact `NUMERIC` for money.
5. Which return to assume before Phase 8 builds real asset allocations.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Monthly rate | Nominal `r / 12`; effective `(1 + r)^(1/12) − 1` | **Effective** | "12% a year" then means the same growth for a lump sum and for a SIP. `r / 12` compounds to 12.68% a year and flatters SIP results by ~3.7% over 10 years |
| Instalment timing | Ordinary annuity (end of month); annuity due (start) | **Annuity due** | SIPs are debited at the start of the period; the first instalment earns a full month |
| Projection storage | Store computed columns; compute on every read | **Compute on read** | Projections depend on today's date and on the latest risk profile. Stored values would go stale; the calculation costs microseconds |
| Number type in formulas | `Decimal` throughout; `float` | **`float` in `app/finance/`, `NUMERIC` in the database** | Stored money must be exact (accounting). A projection is an estimate built on an assumed rate; float error (~10⁻¹²) is far below that uncertainty, and `Decimal` has no exact fractional powers anyway |
| Rounding of results | Round to nearest paisa | **Required SIP rounded *up* to the rupee; funded % rounded *down*** | Rounding the SIP down left the worked example ₹1.77 short after 15 years while showing 100% |
| Expected return | Fixed 10%; user must enter; derived from risk profile | **Empty = automatic: from the latest risk category (8 / 10 / 12%), 7% if the goal is < 3 years away; the user may override** | Works before Phase 8 exists, is explainable, and follows the user when they retake the questionnaire |

## Decision

- All formulas live in the pure module `backend/app/finance/tvm.py`; goal-level logic in `backend/app/finance/goal_plan.py`.
- Rates are fractions inside `app/finance/`, percentages in the API and the database (`NUMERIC(5,2)`).
- The `goals` table stores only user inputs. `expected_return` is nullable; `NULL` means automatic.
- The frontend never re-implements the formulas: its live preview calls `POST /api/goals/calculate`.

## Consequences

- One source of truth for every number shown, used later by Monte Carlo (Phase 5) and the chatbot (Phase 10).
- Results differ slightly from calculators that use `r / 12`; the phase document explains the difference with a worked comparison.
- Phase 8 will replace the return assumption table with an allocation-based return; goals with `expected_return = NULL` will pick that up automatically.
