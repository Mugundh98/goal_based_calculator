"""Fund clusters: groups of funds that BEHAVE alike, found from their returns and risk.

SEBI categories say what a fund promises to hold; clusters say how it actually behaved over the
last three years. K-Means is run on standardised risk/return features for k = 2..10; the number
of clusters is chosen by the silhouette score (how much closer each fund is to its own cluster
than to the next one), among k >= 4: with 2 or 3 clusters K-Means only rediscovers the asset
classes (cash-like, bonds, equity), which the categories already say. A Gaussian
mixture is fitted for comparison (BIC, and agreement with K-Means by the adjusted Rand index).

The fitted model is plain numbers (scaler mean/scale and centroids), stored as JSON, so serving
needs no pickle files: a fund is assigned to the nearest centroid.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

SEED = 0
CLUSTER_FEATURES = (
    "ret_36m",
    "vol_36m",
    "downside_36m",
    "max_dd_36m",
    "sharpe_36m",
    "beta_36m",
    "corr_36m",
)
K_RANGE = range(2, 11)
MIN_K = 4
CLIP_Z = 4.0  # a handful of extreme funds must not get a cluster of their own


@dataclass(frozen=True)
class ClusterModel:
    mean: np.ndarray
    scale: np.ndarray
    centroids: np.ndarray  # in standardised units, (k, features)
    names: list[str]

    def standardise(self, values: np.ndarray) -> np.ndarray:
        return np.clip((values - self.mean) / self.scale, -CLIP_Z, CLIP_Z)

    def assign(self, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Nearest centroid and the distance to it, for rows of CLUSTER_FEATURES."""
        z = self.standardise(values)
        distances = np.linalg.norm(z[:, None, :] - self.centroids[None, :, :], axis=2)
        return distances.argmin(axis=1), distances.min(axis=1)

    def to_json(self) -> dict[str, Any]:
        return {
            "features": list(CLUSTER_FEATURES),
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "centroids": self.centroids.tolist(),
            "names": self.names,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ClusterModel":
        return cls(
            np.asarray(data["mean"]),
            np.asarray(data["scale"]),
            np.asarray(data["centroids"]),
            list(data["names"]),
        )


def snapshot(panel_month: pd.DataFrame) -> pd.DataFrame:
    """Funds with a full three years of history in that month (every cluster feature known)."""
    return panel_month.dropna(subset=list(CLUSTER_FEATURES))


def _risk_label(volatility: float) -> str:
    if volatility < 0.02:
        return "Cash-like"
    if volatility < 0.06:
        return "Low risk"
    if volatility < 0.12:
        return "Moderate risk"
    if volatility < 0.18:
        return "High risk"
    return "Very high risk"


def name_clusters(centroids_raw: pd.DataFrame) -> list[str]:
    """Plain names from each centroid: its risk band, how it moves with the market (for funds
    with real risk), and how it compares on return per unit of risk."""
    names = []
    median_sharpe = centroids_raw["sharpe_36m"].median()
    for _, c in centroids_raw.iterrows():
        parts = [_risk_label(c["vol_36m"])]
        if c["vol_36m"] >= 0.06:
            if c["corr_36m"] < 0.75:
                parts.append("moves apart from the market")
            elif c["beta_36m"] >= 1.0:
                parts.append("amplifies the market")
            else:
                parts.append("follows the market")
        parts.append(
            "strong risk-adjusted return"
            if c["sharpe_36m"] >= median_sharpe
            else "weaker risk-adjusted return"
        )
        names.append(", ".join(parts))
    # Two clusters can land in the same band and quality: tell them apart by their volatility.
    return [
        name
        if names.count(name) == 1
        else f"{name} (volatility {centroids_raw['vol_36m'].iloc[i] * 100:.1f}%)"
        for i, name in enumerate(names)
    ]


def fit(frame: pd.DataFrame) -> tuple[ClusterModel, dict[str, Any]]:
    """Choose k by silhouette, fit K-Means, compare with a Gaussian mixture."""
    values = frame[list(CLUSTER_FEATURES)].to_numpy(dtype=float)
    scaler = StandardScaler().fit(values)
    z = np.clip(scaler.transform(values), -CLIP_Z, CLIP_Z)

    scores = []
    for k in K_RANGE:
        kmeans = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(z)
        gmm = GaussianMixture(k, covariance_type="full", random_state=SEED, n_init=3).fit(z)
        scores.append(
            {
                "k": k,
                "silhouette": round(float(silhouette_score(z, kmeans.labels_)), 4),
                "inertia": round(float(kmeans.inertia_), 2),
                "gmm_bic": round(float(gmm.bic(z)), 2),
            }
        )
    best = max((s for s in scores if s["k"] >= MIN_K), key=lambda s: s["silhouette"])
    k = best["k"]
    kmeans = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(z)
    # Order clusters from least to most volatile, so cluster 0 is always the safest.
    raw_centroids = pd.DataFrame(
        scaler.inverse_transform(kmeans.cluster_centers_), columns=list(CLUSTER_FEATURES)
    )
    order = raw_centroids["vol_36m"].argsort().to_numpy()
    centroids = kmeans.cluster_centers_[order]
    raw_centroids = raw_centroids.iloc[order].reset_index(drop=True)
    model = ClusterModel(scaler.mean_, scaler.scale_, centroids, name_clusters(raw_centroids))

    labels, _ = model.assign(values)
    gmm = GaussianMixture(k, covariance_type="full", random_state=SEED, n_init=3).fit(z)
    report = {
        "funds": len(frame),
        "k": k,
        "k_scores": scores,
        "best_bic_k": min(scores, key=lambda s: s["gmm_bic"])["k"],
        "gmm_agreement_ari": round(float(adjusted_rand_score(labels, gmm.predict(z))), 4),
        "asset_class_ari": round(float(adjusted_rand_score(labels, frame["asset_class"])), 4),
        "clusters": profiles(frame.assign(cluster=labels), model),
    }
    return model, report


def profiles(frame: pd.DataFrame, model: ClusterModel) -> list[dict[str, Any]]:
    """Size, average behaviour and the commonest peer groups of each cluster."""
    out = []
    for cluster, group in frame.groupby("cluster"):
        peers = group["peer_group"].fillna("other").value_counts()
        out.append(
            {
                "cluster": int(cluster),
                "name": model.names[int(cluster)],
                "funds": len(group),
                "median": {f: round(float(group[f].median()), 4) for f in CLUSTER_FEATURES},
                "asset_classes": group["asset_class"].value_counts().to_dict(),
                "top_peer_groups": [
                    {"peer_group": str(p), "funds": int(n)} for p, n in peers.head(4).items()
                ],
            }
        )
    return out
