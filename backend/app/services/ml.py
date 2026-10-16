"""Read side of the ML models: what the API shows. Only the ACTIVE model versions are used.

Nothing here trains or scores; that is done offline (python -m app.ml) and by the ml_score
pipeline job, so these requests are plain database reads.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.peers import LABELS
from app.ml.registry import active
from app.models.market import Fund
from app.models.ml import FundCluster, FundPrediction, MLModel
from app.schemas.ml import (
    ClusterPoint,
    ClusterProfile,
    ClustersOut,
    FundInsight,
    InflationOut,
    ModelCard,
    ModelInfo,
    PeerGroupOut,
    RankedFund,
    RankingsOut,
)

PERCENT = 100


class ModelUnavailable(Exception):
    """No active version of the model yet: it has not been trained."""


def _require(db: Session, name: str) -> MLModel:
    model = active(db, name)
    if model is None:
        raise ModelUnavailable(name)
    return model


def info(model: MLModel) -> ModelInfo:
    return ModelInfo.model_validate(model, from_attributes=True)


def _summary(model: MLModel) -> dict[str, Any]:
    m = model.metrics
    if model.name == "fund_ranker":
        return {
            "walk_forward": m["reported_years"]["pooled"],
            "leaky_random_split": m["leaky_random_split"],
            "importance": m["importance"][:10],
            "rows": m["rows"],
            "funds": m["funds"],
        }
    if model.name == "fund_clusters":
        chosen = next(s for s in m["k_scores"] if s["k"] == m["k"])
        return {
            "k": m["k"],
            "silhouette": chosen["silhouette"],
            "k_scores": m["k_scores"],
            "best_bic_k": m["best_bic_k"],
            "gmm_agreement_ari": m["gmm_agreement_ari"],
            "asset_class_ari": m["asset_class_ari"],
            "funds": m["funds"],
        }
    return {
        "order": m["order"],
        "seasonal_order": m["seasonal_order"],
        "mae_12m_ahead": m["evaluation"]["mae_12m_ahead"],
    }


def model_cards(db: Session) -> list[ModelCard]:
    models = db.scalars(select(MLModel).where(MLModel.is_active).order_by(MLModel.name)).all()
    return [ModelCard(**info(m).model_dump(), summary=_summary(m)) for m in models]


def _ranked(prediction: FundPrediction, fund: Fund) -> RankedFund:
    return RankedFund(
        fund_id=fund.id,
        name=fund.name,
        amc=fund.amc,
        category=fund.category,
        predicted_quartile=prediction.predicted_quartile,
        prob_top=prediction.prob_top,
        probabilities=prediction.probabilities,
        expected_quartile=prediction.expected_quartile,
        peer_rank=prediction.peer_rank,
        peer_size=prediction.peer_size,
        factors=prediction.factors,
    )


def rankings(db: Session, peer_group: str | None) -> RankingsOut:
    model = _require(db, "fund_ranker")
    counts = db.execute(
        select(FundPrediction.peer_group, func.count(), func.max(FundPrediction.as_of))
        .where(FundPrediction.model_id == model.id)
        .group_by(FundPrediction.peer_group)
        .order_by(FundPrediction.peer_group)
    ).all()
    groups = [PeerGroupOut(id=g, label=LABELS.get(g, g), funds=n) for g, n, _ in counts]
    if peer_group is None and groups:
        # The largest group by default, except sectoral/thematic funds: defence, pharma and
        # overseas funds share that label but not a market, so it is the weakest peer group.
        candidates = [g for g in groups if g.id != "sectoral_thematic"] or groups
        peer_group = max(candidates, key=lambda g: g.funds).id
    rows = db.execute(
        select(FundPrediction, Fund)
        .join(Fund, Fund.id == FundPrediction.fund_id)
        .where(FundPrediction.model_id == model.id, FundPrediction.peer_group == peer_group)
        .order_by(FundPrediction.peer_rank)
    ).all()
    as_of = max((d for _, _, d in counts), default=model.data_end)
    return RankingsOut(
        model=info(model),
        as_of=as_of,
        peer_groups=groups,
        peer_group=peer_group,
        funds=[_ranked(p, f) for p, f in rows],
    )


def clusters(db: Session) -> ClustersOut:
    model = _require(db, "fund_clusters")
    rows = db.execute(
        select(FundCluster, Fund)
        .join(Fund, Fund.id == FundCluster.fund_id)
        .where(FundCluster.model_id == model.id)
    ).all()
    m = model.metrics
    chosen = next(s for s in m["k_scores"] if s["k"] == m["k"])
    return ClustersOut(
        model=info(model),
        as_of=rows[0][0].as_of if rows else model.data_end,
        k=m["k"],
        silhouette=chosen["silhouette"],
        asset_class_ari=m["asset_class_ari"],
        clusters=[ClusterProfile(**c) for c in m["clusters"]],
        points=[
            ClusterPoint(
                fund_id=f.id,
                name=f.name,
                category=f.category,
                asset_class=f.asset_class,
                cluster=c.cluster,
                volatility=round(c.volatility * PERCENT, 2),
                return_3y=round(c.return_3y * PERCENT, 2),
            )
            for c, f in rows
        ],
    )


def fund_insight(db: Session, fund: Fund) -> FundInsight:
    ranker, cluster_model = active(db, "fund_ranker"), active(db, "fund_clusters")
    prediction = db.get(FundPrediction, (ranker.id, fund.id)) if ranker is not None else None
    cluster = db.get(FundCluster, (cluster_model.id, fund.id)) if cluster_model else None
    names = cluster_model.params["model"]["names"] if cluster_model else []
    return FundInsight(
        prediction=None if prediction is None else _ranked(prediction, fund),
        peer_group=None if prediction is None else prediction.peer_group,
        peer_group_label=None if prediction is None else LABELS.get(prediction.peer_group),
        cluster=None if cluster is None else cluster.cluster,
        cluster_name=None if cluster is None else names[cluster.cluster],
        as_of=(prediction or cluster).as_of if (prediction or cluster) else None,
    )


def inflation(db: Session, history_months: int = 60) -> InflationOut:
    model = _require(db, "inflation_forecast")
    m = model.metrics
    return InflationOut(
        model=info(model),
        history=m["history"][-history_months:],
        forecast=m["forecast"],
        mae_12m_ahead=m["evaluation"]["mae_12m_ahead"],
    )
