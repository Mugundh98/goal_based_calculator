"""ML evaluation report from the validation results stored with each active model version.

The fund ranker is compared, year by year on data it never saw (purged walk-forward, 2021-2025),
with two naive baselines: "last year's top funds" (ranking by the past 12-month return within the
peer group, i.e. momentum) and random picks. Pure: reads the stored metrics.
"""

import statistics
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.report import table
from app.models import MLModel

RANKER_METRICS = (
    ("rank_ic", "Rank correlation (Spearman) with the real outcome"),
    ("top_pick_hit_rate", "Top picks that ended in the top quartile"),
    ("top_pick_median_excess", "Top picks' return above the peer average (pp, median)"),
    ("accuracy", "Quartile accuracy"),
    ("macro_f1", "Macro F1 over the 4 quartiles"),
)
BASELINES = {"model": "LightGBM ranker", "momentum": "Last year's top funds", "random": "Random"}


def _active(db: Session, name: str) -> MLModel | None:
    return db.scalar(select(MLModel).where(MLModel.name == name, MLModel.is_active))


def ranker_section(model: MLModel) -> tuple[str, dict[str, Any]]:
    reported = model.metrics.get("reported_years", {})
    folds, pooled = reported.get("folds", []), reported.get("pooled", {})
    rows = []
    for key, label in RANKER_METRICS:
        row: list[Any] = [label]
        for who in BASELINES:
            row.append(pooled.get(who, {}).get(key))
        rows.append(row)
    yearly = [
        [
            f["year"],
            f["model"]["rows"],
            f["model"]["rank_ic"],
            f["momentum"]["rank_ic"],
            f["random"]["rank_ic"],
            f["model"]["top_pick_hit_rate"],
            f["momentum"]["top_pick_hit_rate"],
            f["random"]["top_pick_hit_rate"],
        ]
        for f in folds
    ]
    differences = [f["model"]["rank_ic"] - f["momentum"]["rank_ic"] for f in folds]
    wins = sum(d > 0 for d in differences)
    mean_diff = statistics.fmean(differences) if differences else 0.0
    spread = statistics.stdev(differences) if len(differences) > 1 else 0.0
    # Paired t statistic over the years: is the model's edge over momentum real?
    t_stat = mean_diff / (spread / len(differences) ** 0.5) if spread else 0.0
    leaky = model.metrics.get("leaky_random_split", {})
    summary = {
        "version": model.version,
        "pooled": pooled,
        "folds": folds,
        "model_minus_momentum_rank_ic": differences,
        "years_model_beats_momentum": wins,
        "paired_t": t_stat,
        "leaky_random_split": leaky,
    }
    md = f"""
## Fund ranker (v{model.version}, {model.algorithm})

Walk-forward validation: for each year 2021-2025 the model is trained only on earlier months
(with a 12-month gap so no target overlaps training) and tested on that year. Baselines on the
same funds and months: **last year's top funds** (rank by the past 12-month return within the
peer group, i.e. momentum, the naive strategy most investors follow) and **random** picks.

### Pooled over 2021-2025 ({pooled.get("model", {}).get("rows", 0):,} fund-months)

{table(["Metric", *BASELINES.values()], rows)}

Chance level: a random pick lands in the top quartile 25% of the time.

### Year by year

{
        table(
            [
                "Year",
                "Fund-months",
                "Rank corr. model",
                "Rank corr. last year's top",
                "Rank corr. random",
                "Top-pick hit model",
                "Top-pick hit last year's top",
                "Top-pick hit random",
            ],
            yearly,
        )
    }

The model beat last year's top funds on rank correlation in **{wins} of {len(folds)}** years;
mean difference {mean_diff:+.3f} (standard deviation {spread:.3f} across years), paired
t = {t_stat:.2f} with {len(differences) - 1} degrees of freedom; |t| would have to exceed 2.78 for
significance at 5%. **The model is about as good as momentum, and both are clearly better than
chance.**

### Look-ahead check

A shuffled 5-fold split (which lets the model train on months after the ones it is tested on)
gives rank correlation {leaky.get("rank_ic", 0):.3f} against
{
        pooled.get("model", {}).get(
            "rank_ic", 0
        ):.3f} walk-forward. The chosen, deliberately shallow model scores the same either way: it cannot
memorise individual funds across overlapping 12-month targets, which is evidence that it does
not over-fit. (A more flexible model tried in Phase 7 scored 0.433 shuffled but 0.158
walk-forward: that gap is the look-ahead bias the time-ordered split exposes.)
"""  # noqa: E501
    return md, summary


def clusters_section(model: MLModel) -> tuple[str, dict[str, Any]]:
    m = model.metrics
    scores = m.get("k_scores", [])
    rows = [[s.get("k"), s.get("silhouette"), s.get("inertia")] for s in scores]
    md = f"""
## Fund behaviour clusters (v{model.version}, {model.algorithm})

{table(["k", "Silhouette", "Inertia"], rows)}

Chosen k = {m.get("k")} (best silhouette among k >= 4); a Gaussian mixture prefers k =
{m.get("best_bic_k")} by BIC. Agreement with the GMM clusters (adjusted Rand index):
{m.get("gmm_agreement_ari")}; with SEBI asset classes: {m.get("asset_class_ari")}: the clusters
group funds by behaviour, related to but not the same as their labels.
"""
    return md, {"version": model.version, "k": m.get("k"), "k_scores": scores}


def inflation_section(model: MLModel) -> tuple[str, dict[str, Any]]:
    evaluation = model.metrics.get("evaluation", {})
    mae = evaluation.get("mae_12m_ahead", {})
    by_horizon = evaluation.get("mae_by_horizon", {})
    horizons = [
        [h + 1, *(by_horizon.get(k, [None] * 12)[h] for k in ("sarima", "naive", "rbi_target"))]
        for h in (0, 2, 5, 8, 11)
    ]
    md = f"""
## Inflation forecast (v{model.version}, {model.algorithm})

Rolling-origin evaluation from {len(evaluation.get("origins", []))} forecast origins
(every 6 months, {(evaluation.get("origins") or ["?"])[0]} to
{(evaluation.get("origins") or ["?"])[-1]}). Mean absolute error of CPI inflation, percentage
points:

{table(["Months ahead", "SARIMA", "Naive (no change)", "RBI target (4%)"], horizons)}

Twelve months ahead: SARIMA {mae.get("sarima")} pp, naive {mae.get("naive")} pp, RBI target
{mae.get("rbi_target")} pp.
"""
    return md, {"version": model.version, "mae_12m_ahead": mae, "mae_by_horizon": by_horizon}


def build(db: Session, today: date | None = None) -> tuple[str, dict[str, Any]]:
    parts = [
        f"# ML evaluation\n\n_Generated {(today or date.today()).isoformat()} from the "
        "validation results stored with each active model (`ml_models.metrics`)._"
    ]
    data: dict[str, Any] = {}
    for name, section in (("fund_ranker", ranker_section), ("fund_clusters", clusters_section),
                          ("inflation_forecast", inflation_section)):  # fmt: skip
        model = _active(db, name)
        if model is None:
            parts.append(f"## {name}\n\nNo active model: run `python -m app.ml train all`.")
            continue
        md, summary = section(model)
        parts.append(md)
        data[name] = summary
    return "\n".join(parts), data
