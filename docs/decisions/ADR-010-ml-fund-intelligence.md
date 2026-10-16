# ADR-010: ML fund intelligence – peer-quartile target, purged walk-forward validation, LightGBM with tree SHAP, versioned models

**Status:** Accepted · **Date:** 2026-10-17 · **Phase:** 7

## Context

Phase 7 adds machine learning on the Phase 4 fund data: a model that ranks funds within their category, clusters of funds that behave alike, and an inflation forecast. Financial time series make it easy to fool yourself: overlapping targets, survivorship, look-ahead in features and in validation, and noisy labels. The choices below decide whether the reported numbers can be trusted.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| What to predict | Next-year return (regression); beat the index (binary); return quartile among all funds; **quartile within the SEBI peer group** | **Quartile of the next-12-month return within the peer group**, at every month-end | Investors choose *between comparable funds*; a cross-category target would only learn "small caps beat liquid funds in bull years". Quartiles are balanced by construction (no class imbalance) and robust to outliers |
| Peer groups | AMFI category text; asset class | **~30 canonical peer groups from keyword rules** over AMFI's inconsistent labels; index funds clustered but not ranked; pre-2017 generic labels excluded | The same SEBI category appears under several names; index funds track different indices on purpose |
| Data | All plans; direct growth | **Direct-plan growth options only**, month-end NAVs, unit changes adjusted (`finance/nav_adjust.py`) | One share class per scheme; no IDCW payouts that look like losses; face-value changes (×100, ÷10) are not returns |
| Validation | Random K-fold; one train/test split; **walk-forward** | **Expanding-window walk-forward by year with a 12-month purge**; hyper-parameters chosen on 2018–2020 only, results reported for 2021–2025; a shuffled K-fold run kept for comparison | A random split trains on the future of the funds it tests and on overlapping targets; the comparison quantifies that bias |
| Baselines | None; random | **Random and momentum** (last 12 months' rank in the peer group) | A model must beat the simplest rule an investor already uses, not just chance |
| Metrics | Accuracy only | **Rank correlation (Spearman within month and peer group), top-pick hit rate, median excess return**, plus accuracy, macro-F1, log-loss | Ranking is what the product shows; medians and ranks, not means, because a few thematic funds that doubled dominate averages |
| Model | Logistic regression; random forest; XGBoost; **LightGBM** | **LightGBM multiclass, very shallow** (4 leaves, ≥ 1,000 rows per leaf, 100 rounds) | Handles missing values and non-linear interactions; small wheel (XGBoost on Linux pulls ~200 MB of CUDA libraries); deeper models over-fitted year-specific patterns |
| Explanations | `shap` package; permutation importance; **built-in tree SHAP** | **LightGBM `pred_contrib`** (exact TreeSHAP): per-fund contributions to the top-quartile log-odds, and mean \|SHAP\| for global importance | Exact, fast, no extra dependency (`shap` brings numba/llvmlite); contributions add up to the model output (tested) |
| Clusters | Categories; K-Means; GMM; hierarchical | **K-Means on 7 standardised 3-year risk/return features, k by silhouette among k ≥ 4**, GMM by BIC reported for comparison, stored as plain JSON (scaler + centroids) | k ≤ 3 only rediscovers asset classes; JSON avoids pickle files; nearest-centroid assignment is trivial to serve |
| Inflation | Prophet; SARIMA; naive | **SARIMA on log CPI, orders by AIC on data before 2019**, walk-forward vs naive and the RBI 4% target, 12-month forecast with an exact 80% band | Classic, explainable, available in statsmodels (Prophet adds a heavy dependency); log CPI makes the model multiplicative |
| Training vs serving | Train inside the API; offline | **Offline training** (`python -m app.ml train`) → model file + `ml_models` row; **online serving reads stored predictions**; `ml_score` pipeline job rescored daily | Training takes minutes; requests stay database reads (~0.3 s) |
| Versioning | Overwrite; **versions with one active** | **`ml_models` (name, version) unique, partial unique index allows one active version per name**; predictions reference the model version | Reproducibility and rollback; every number can be traced to a model and its metrics |

## Decision

- Code in `backend/app/ml/` (`peers`, `dataset`, `features`, `ranking`, `clustering`, `inflation`, `registry`, `scoring`, `train`); training CLI `python -m app.ml`; experiment records in `docs/ml/*.json`; model files in `backend/data/models/` (not in git).
- Tables `ml_models`, `fund_predictions`, `fund_clusters` (migration `0008`); endpoints under `/api/ml`.
- The plan's top-level `ml/` folder for offline notebooks was not created: training lives next to the features it shares with serving, so the two can never drift apart.

## Consequences

- Honest result: the model ranks funds about as well as momentum (rank correlation 0.248 vs 0.254 on 2021–2025) and picks top-quartile funds 1.4× as often as chance; SHAP shows its main input is momentum, adjusted for risk. The UI says so.
- Survivorship bias: only funds that exist today were backfilled (Phase 4), so closed and merged funds are missing from the history; reported skill is probably slightly optimistic.
- The ranker must be retrained as data grows (CLI); scoring runs daily after the NAV load.
- Phase 8 recommendations can use the predictions and clusters; Phase 10's chatbot can call the read services.
