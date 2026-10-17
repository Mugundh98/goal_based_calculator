# ML evaluation

_Generated 2026-10-18 from the validation results stored with each active model (`ml_models.metrics`)._

## Fund ranker (v2, LightGBM multiclass (gradient-boosted trees))

Walk-forward validation: for each year 2021-2025 the model is trained only on earlier months
(with a 12-month gap so no target overlaps training) and tested on that year. Baselines on the
same funds and months: **last year's top funds** (rank by the past 12-month return within the
peer group, i.e. momentum, the naive strategy most investors follow) and **random** picks.

### Pooled over 2021-2025 (42,435 fund-months)

| Metric | LightGBM ranker | Last year's top funds | Random |
|---|---|---|---|
| Rank correlation (Spearman) with the real outcome | 0.248 | 0.254 | -0.006 |
| Top picks that ended in the top quartile | 0.361 | 0.369 | 0.238 |
| Top picks' return above the peer average (pp, median) | 0.22 | 0.27 | -0.03 |
| Quartile accuracy | 0.349 | 0.356 | - |
| Macro F1 over the 4 quartiles | 0.33 | 0.355 | - |

Chance level: a random pick lands in the top quartile 25% of the time.

### Year by year

| Year | Fund-months | Rank corr. model | Rank corr. last year's top | Rank corr. random | Top-pick hit model | Top-pick hit last year's top | Top-pick hit random |
|---|---|---|---|---|---|---|---|
| 2021 | 7425 | 0.268 | 0.384 | 0.005 | 0.337 | 0.426 | 0.253 |
| 2022 | 8071 | 0.374 | 0.311 | -0.013 | 0.438 | 0.405 | 0.228 |
| 2023 | 8924 | 0.42 | 0.438 | -0.012 | 0.457 | 0.471 | 0.232 |
| 2024 | 9905 | 0.041 | 0.039 | -0.014 | 0.259 | 0.263 | 0.235 |
| 2025 | 8110 | 0.166 | 0.136 | 0.007 | 0.325 | 0.301 | 0.244 |

The model beat last year's top funds on rank correlation in **3 of 5** years;
mean difference -0.008 (standard deviation 0.068 across years), paired
t = -0.26 with 4 degrees of freedom; |t| would have to exceed 2.78 for
significance at 5%. **The model is about as good as momentum, and both are clearly better than
chance.**

### Look-ahead check

A shuffled 5-fold split (which lets the model train on months after the ones it is tested on)
gives rank correlation 0.241 against
0.248 walk-forward. The chosen, deliberately shallow model scores the same either way: it cannot
memorise individual funds across overlapping 12-month targets, which is evidence that it does
not over-fit. (A more flexible model tried in Phase 7 scored 0.433 shuffled but 0.158
walk-forward: that gap is the look-ahead bias the time-ordered split exposes.)


## Fund behaviour clusters (v3, K-Means (k = 8) on standardised 3-year risk and return)

| k | Silhouette | Inertia |
|---|---|---|
| 2 | 0.615 | 2,171.1 |
| 3 | 0.546 | 1,616.5 |
| 4 | 0.42 | 1,183.7 |
| 5 | 0.427 | 979.0 |
| 6 | 0.424 | 855.5 |
| 7 | 0.427 | 747.0 |
| 8 | 0.434 | 641.7 |
| 9 | 0.397 | 571.1 |
| 10 | 0.398 | 521.3 |

Chosen k = 8 (best silhouette among k >= 4); a Gaussian mixture prefers k =
10 by BIC. Agreement with the GMM clusters (adjusted Rand index):
0.5421; with SEBI asset classes: 0.3417: the clusters
group funds by behaviour, related to but not the same as their labels.


## Inflation forecast (v2, SARIMA(0, 1, 1)x(0, 1, 1, 12) on log CPI)

Rolling-origin evaluation from 13 forecast origins
(every 6 months, 2018-12 to
2024-12). Mean absolute error of CPI inflation, percentage
points:

| Months ahead | SARIMA | Naive (no change) | RBI target (4%) |
|---|---|---|---|
| 1 | 0.5 | 0.71 | 1.79 |
| 3 | 0.74 | 0.92 | 1.55 |
| 6 | 1.07 | 1.42 | 1.72 |
| 9 | 1.01 | 1.22 | 1.66 |
| 12 | 1.31 | 1.74 | 1.86 |

Twelve months ahead: SARIMA 1.31 pp, naive 1.74 pp, RBI target
1.86 pp.
