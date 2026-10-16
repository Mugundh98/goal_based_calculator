"""Batch scoring: apply the ACTIVE models to the latest month and store the results.

Run after the daily data load (pipeline job `ml_score`) or after training. Predictions are
replaced, not appended: the API shows the current view, and each row says which model version
and which month-end produced it.
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ml import clustering, features, ranking, registry
from app.ml.dataset import MonthlyData
from app.models.ml import FundCluster, FundPrediction

TOP_FACTORS = 5


def _factor_list(row: pd.Series, shap_row: np.ndarray) -> list[dict[str, Any]]:
    """The features that moved this fund's top-quartile odds most, either way."""
    order = np.argsort(np.abs(shap_row[:-1]))[::-1][:TOP_FACTORS]
    out = []
    for i in order:
        name = features.FEATURES[i]
        value = row[name]
        out.append(
            {
                "feature": name,
                "label": features.FEATURE_LABELS[name],
                "value": None if value is None or math.isnan(value) else round(float(value), 4),
                "contribution": round(float(shap_row[i]), 4),
            }
        )
    return out


def score_rankings(db: Session, data: MonthlyData) -> int:
    model_row = registry.active(db, "fund_ranker")
    if model_row is None or model_row.file_path is None:
        return 0
    booster = registry.load_booster(model_row.file_path)
    panel = features.build_panel(data.navs, data.market, data.funds)
    latest = panel[panel["month"] == data.last_month].reset_index(drop=True)
    db.execute(delete(FundPrediction).where(FundPrediction.model_id == model_row.id))
    if latest.empty:
        db.commit()
        return 0

    probs = ranking.probabilities(booster, latest)
    shap = ranking.contributions(booster, latest)
    latest["expected_quartile"] = ranking.expected_quartile(probs)
    latest["peer_rank"] = (
        latest.groupby("peer_group")["expected_quartile"].rank(method="first").astype(int)
    )
    as_of = data.last_month.date()
    db.add_all(
        FundPrediction(
            model_id=model_row.id,
            fund_id=int(row.fund_id),
            as_of=as_of,
            peer_group=row.peer_group,
            predicted_quartile=int(probs[i].argmax() + 1),
            prob_top=float(probs[i, ranking.TOP]),
            probabilities=[round(float(p), 4) for p in probs[i]],
            expected_quartile=float(row.expected_quartile),
            peer_rank=int(row.peer_rank),
            peer_size=int(row.peer_size),
            factors=_factor_list(row, shap[i]),
        )
        for i, row in latest.iterrows()
    )
    db.commit()
    return len(latest)


def assign_clusters(db: Session, data: MonthlyData) -> int:
    model_row = registry.active(db, "fund_clusters")
    if model_row is None:
        return 0
    model = clustering.ClusterModel.from_json(model_row.params["model"])
    frame = clustering.snapshot(features.snapshot(data.navs, data.market, data.funds))
    db.execute(delete(FundCluster).where(FundCluster.model_id == model_row.id))
    if frame.empty:
        db.commit()
        return 0
    labels, distances = model.assign(frame[list(clustering.CLUSTER_FEATURES)].to_numpy(float))
    as_of = data.last_month.date()
    db.add_all(
        FundCluster(
            model_id=model_row.id,
            fund_id=int(fund_id),
            as_of=as_of,
            cluster=int(label),
            distance=round(float(distance), 4),
            volatility=float(row.vol_36m),
            return_3y=float(row.ret_36m),
        )
        for (fund_id, row), label, distance in zip(frame.iterrows(), labels, distances, strict=True)
    )
    db.commit()
    return len(frame)
