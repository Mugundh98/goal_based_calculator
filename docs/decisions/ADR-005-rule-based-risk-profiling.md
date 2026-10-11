# ADR-005: Rule-based risk profiling using the lower of tolerance and capacity

**Status:** Accepted · **Date:** 2026-10-11 · **Phase:** 2

## Context

Recommendations (Phase 8) must match each investor's risk profile. The profile must be explainable to the user and defensible in an evaluation. There is no dataset of investors labelled with a "correct" risk profile.

## Options considered

| Option | For | Against |
|---|---|---|
| ML classifier | Could find patterns automatically | No labelled data; black box; hard to justify each result |
| Questionnaire only | Simple | Ignores whether the person can afford losses |
| Weighted average of tolerance and capacity | One number | A high score can hide a dangerously low one |
| **Separate tolerance (questionnaire) and capacity (financial rules); final = minimum** | Transparent; mirrors adviser suitability practice; each factor can be shown | Thresholds are expert-chosen, not statistically calibrated |

## Decision

- Tolerance: 7-question questionnaire, points scaled to 0–100.
- Capacity: 6 factors from the financial profile (age, savings rate, emergency fund, EMI burden, dependants, income stability), points summing to 100.
- Final score = min(tolerance, capacity); bands 0–39 conservative, 40–69 moderate, 70–100 aggressive.
- Rules live in the pure module `backend/app/finance/risk_profile.py`; each assessment stores its answers and a capacity breakdown snapshot, tagged with `questionnaire_version`.

## Consequences

- Every result can be explained factor by factor in the UI and in the viva.
- Thresholds may be refined later; versioning keeps old assessments interpretable.
- ML is reserved for problems with real labelled data (fund performance, Phase 7).
