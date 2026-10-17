# Return-model comparison

_Generated 2026-10-17. 10,000 paths per model, same seed; market data
2013-02-01 to 2026-09-01
(164 months)._

Each goal gets the monthly SIP that the single-return plan says is exactly enough (inflation 6%,
return from the equity share: 13% equity / 7% debt). Then each return model simulates it.

## Chance of reaching the target (%)

| Goal | Equity | Assumed return | SIP (plan) | Normal | Block bootstrap | GARCH(1,1) | Regime-switching (HMM) |
|---|---|---|---|---|---|---|---|
| Car, 3 years, conservative | 30% | 8.8% | Rs 23,179 | 51.1 | 48.5 | 51.2 | 52.5 |
| House deposit, 7 years, moderate | 60% | 10.6% | Rs 24,546 | 51.6 | 49.7 | 51.5 | 51.9 |
| Education, 10 years, moderate | 60% | 10.6% | Rs 21,529 | 51.2 | 49.9 | 51.6 | 52.3 |
| Education, 15 years, aggressive | 85% | 12.1% | Rs 12,482 | 51.6 | 50.7 | 51.3 | 52.7 |
| Wealth, 25 years, aggressive | 85% | 12.1% | Rs 24,817 | 51.2 | 50.8 | 51.5 | 51.4 |

## SIP needed for a 90% chance

| Goal | SIP (plan) | Normal | Block bootstrap | GARCH(1,1) | Regime-switching (HMM) |
|---|---|---|---|---|---|
| Car, 3 years, conservative | Rs 23,179 | Rs 24,922 | Rs 24,886 | Rs 24,894 | Rs 25,267 |
| House deposit, 7 years, moderate | Rs 24,546 | Rs 30,401 | Rs 29,992 | Rs 30,416 | Rs 30,623 |
| Education, 10 years, moderate | Rs 21,529 | Rs 27,833 | Rs 27,694 | Rs 27,820 | Rs 28,060 |
| Education, 15 years, aggressive | Rs 12,482 | Rs 19,734 | Rs 19,633 | Rs 19,830 | Rs 20,034 |
| Wealth, 25 years, aggressive | Rs 24,817 | Rs 47,478 | Rs 47,338 | Rs 47,457 | Rs 49,448 |

## Simulated portfolio volatility (% a year)

| Goal | Normal | Block bootstrap | GARCH(1,1) | Regime-switching (HMM) |
|---|---|---|---|---|
| Car, 3 years, conservative | 5.54 | 5.54 | 5.52 | 6.58 |
| House deposit, 7 years, moderate | 10.2 | 10.2 | 10.4 | 10.5 |
| Education, 10 years, moderate | 10.2 | 10.2 | 10.4 | 10.5 |
| Education, 15 years, aggressive | 14.3 | 14.3 | 14.5 | 14.3 |
| Wealth, 25 years, aggressive | 14.3 | 14.3 | 14.5 | 14.3 |

## What this shows

- A SIP that meets the target "on paper" succeeds only about half the time: the plan uses the
  median return (ADR-008), so roughly half the paths end above the target and half below.
- The models agree within 0.7 to 4.0 percentage points on the chance
  of success; they differ more in the tails (the 10th percentile and the SIP for 90%), where fat
  tails, volatility clustering and crisis regimes matter.
- The SIP for a 90% chance is the practical number: certainty costs more for equity-heavy and
  long goals, because their outcomes spread wider.
