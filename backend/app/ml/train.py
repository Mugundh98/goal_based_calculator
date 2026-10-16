"""Offline training: fit, validate, save, register and activate each model, then score.

    uv run python -m app.ml train all        # ranker, clusters and inflation forecast
    uv run python -m app.ml train ranker     # one model
    uv run python -m app.ml score            # re-score with the active models

Each run writes its full validation results to docs/ml/<name>-v<version>.json, the experiment
record the Phase 7 document and the project report are written from.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ml import clustering, dataset, features, inflation, ranking, registry, scoring

logger = logging.getLogger(__name__)
REPORTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "ml"
INFLATION_ORDER_UNTIL = pd.Timestamp("2018-12-01")  # choose SARIMA orders on data before this
INFLATION_ORIGINS = pd.date_range("2018-12-01", "2024-12-01", freq="6MS")


def _write_report(name: str, version: int, report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{name}-v{version}.json"
    path.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    raise TypeError(f"not JSON serialisable: {type(value)}")


def _plain(value: Any) -> Any:
    """NumPy numbers to Python ones, so the JSONB column accepts them."""
    return json.loads(json.dumps(value, default=_json_default))


def train_ranker(db: Session, data: dataset.MonthlyData) -> int:
    started = time.perf_counter()
    panel = features.build_panel(data.navs, data.market, data.funds)
    labelled = panel[panel["quartile"].notna()].reset_index(drop=True)
    tuning = ranking.validate(labelled, ranking.TUNING_YEARS)
    reported = ranking.validate(labelled, ranking.REPORTED_YEARS)
    model = ranking.train(labelled)
    version = registry.next_version(db, "fund_ranker")
    path = registry.model_path("fund_ranker", version)
    model.save_model(str(path))

    report = {
        "rows": len(labelled),
        "funds": int(labelled["fund_id"].nunique()),
        "peer_groups": int(labelled["peer_group"].nunique()),
        "months": [labelled["month"].min(), labelled["month"].max()],
        "class_balance": labelled["quartile"].value_counts().sort_index().to_dict(),
        "tuning_years": {"folds": tuning.folds, "pooled": tuning.pooled},
        "reported_years": {"folds": reported.folds, "pooled": reported.pooled},
        "leaky_random_split": reported.leaky,
        "importance": ranking.global_importance(model, labelled),
        "seconds": round(time.perf_counter() - started, 1),
    }
    report = _plain(report)
    registry.register(
        db,
        name="fund_ranker",
        version=version,
        algorithm="LightGBM multiclass (gradient-boosted trees)",
        params={**ranking.PARAMS, "rounds": ranking.ROUNDS, "horizon_months": features.HORIZON},
        metrics={k: report[k] for k in ("reported_years", "leaky_random_split", "importance")}
        | {"rows": report["rows"], "funds": report["funds"]},
        features=list(features.FEATURES),
        file_path=path,
        data_start=labelled["month"].min().date(),
        data_end=data.last_month.date(),
    )
    logger.info("fund_ranker v%s: %s", version, _write_report("fund_ranker", version, report))
    return version


def train_clusters(db: Session, data: dataset.MonthlyData) -> int:
    frame = clustering.snapshot(features.snapshot(data.navs, data.market, data.funds))
    model, report = clustering.fit(frame)
    version = registry.next_version(db, "fund_clusters")
    report = _plain(report)
    registry.register(
        db,
        name="fund_clusters",
        version=version,
        algorithm=f"K-Means (k = {report['k']}) on standardised 3-year risk and return",
        params={"model": model.to_json()},
        metrics=report,
        features=list(clustering.CLUSTER_FEATURES),
        data_start=(data.last_month - pd.DateOffset(months=36)).date(),
        data_end=data.last_month.date(),
    )
    logger.info("fund_clusters v%s: %s", version, _write_report("fund_clusters", version, report))
    return version


def load_cpi(db: Session) -> pd.Series:
    rows = db.execute(
        text(
            "SELECT period, cpi FROM inflation_data WHERE base_year = "
            "(SELECT max(base_year) FROM inflation_data) ORDER BY period"
        )
    ).all()
    return pd.Series([float(r.cpi) for r in rows], index=pd.to_datetime([r.period for r in rows]))


def train_inflation(db: Session) -> int:
    cpi = load_cpi(db)
    if len(cpi) < 60:
        raise ValueError("Need at least five years of CPI: run the inflation pipeline job")
    order, seasonal, grid = inflation.choose_order(np.log(cpi.loc[:INFLATION_ORDER_UNTIL]))
    evaluation = inflation.evaluate(cpi, order, seasonal, list(INFLATION_ORIGINS))
    band = inflation.forecast_band(cpi, order, seasonal)
    history = (inflation.yoy(cpi).dropna() * 100).round(2)
    report = _plain(
        {
            "order": order,
            "seasonal_order": seasonal,
            "aic_grid": grid,
            "evaluation": {
                "origins": evaluation.origins,
                "mae_12m_ahead": evaluation.mae,
                "mae_by_horizon": evaluation.mae_by_horizon,
            },
            "forecast": band,
            "history": [{"month": m.strftime("%Y-%m-%d"), "yoy": v} for m, v in history.items()],
        }
    )
    version = registry.next_version(db, "inflation_forecast")
    registry.register(
        db,
        name="inflation_forecast",
        version=version,
        algorithm=f"SARIMA{tuple(order)}x{tuple(seasonal)} on log CPI",
        params={"order": list(order), "seasonal_order": list(seasonal)},
        metrics=report,
        data_start=cpi.index[0].date(),
        data_end=cpi.index[-1].date(),
    )
    logger.info(
        "inflation_forecast v%s: %s", version, _write_report("inflation_forecast", version, report)
    )
    return version


def score(db: Session, data: dataset.MonthlyData | None = None) -> dict[str, int]:
    data = data or dataset.load(db)
    return {
        "predictions": scoring.score_rankings(db, data),
        "clusters": scoring.assign_clusters(db, data),
    }
