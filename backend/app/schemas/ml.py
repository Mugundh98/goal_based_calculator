from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ModelInfo(BaseModel):
    name: str
    version: int
    algorithm: str
    trained_at: datetime
    data_start: date
    data_end: date


class ModelCard(ModelInfo):
    """A model and its headline validation results (full detail in docs/ml/<name>-v<n>.json)."""

    summary: dict[str, Any]


class Factor(BaseModel):
    feature: str
    label: str
    value: float | None
    contribution: float  # SHAP value for "top quartile", log-odds; > 0 raises the chance


class RankedFund(BaseModel):
    fund_id: int
    name: str
    amc: str
    category: str
    predicted_quartile: int
    prob_top: float
    probabilities: list[float]  # P(Q1) .. P(Q4)
    expected_quartile: float
    peer_rank: int
    peer_size: int
    factors: list[Factor]


class PeerGroupOut(BaseModel):
    id: str
    label: str
    funds: int


class RankingsOut(BaseModel):
    model: ModelInfo
    as_of: date
    peer_groups: list[PeerGroupOut]
    peer_group: str | None
    funds: list[RankedFund]


class ClusterProfile(BaseModel):
    cluster: int
    name: str
    funds: int
    median: dict[str, float]
    asset_classes: dict[str, int]
    top_peer_groups: list[dict[str, Any]]


class ClusterPoint(BaseModel):
    fund_id: int
    name: str
    category: str
    asset_class: str
    cluster: int
    volatility: float  # %
    return_3y: float  # %


class ClustersOut(BaseModel):
    model: ModelInfo
    as_of: date
    k: int
    silhouette: float
    asset_class_ari: float
    clusters: list[ClusterProfile]
    points: list[ClusterPoint]


class FundInsight(BaseModel):
    """What the models say about one fund (fund detail page)."""

    prediction: RankedFund | None
    peer_group: str | None
    peer_group_label: str | None
    cluster: int | None
    cluster_name: str | None
    as_of: date | None


class InflationPoint(BaseModel):
    month: date
    yoy: float  # %


class InflationBand(BaseModel):
    month: date
    p10: float
    p50: float
    p90: float


class InflationOut(BaseModel):
    model: ModelInfo
    history: list[InflationPoint]
    forecast: list[InflationBand]
    mae_12m_ahead: dict[str, float]  # sarima, naive, rbi_target (percentage points)
