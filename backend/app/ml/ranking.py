"""Fund ranker: predict next-12-month return quartile within the peer group (LightGBM).

Validation is WALK-FORWARD: for each test year Y the model is trained only on months whose
12-month target was already known before Y began (t + 12 months <= 1 January Y, a "purge" of
the 12 months before the test year), then tested on the months of Y. This is how the model
would have been used in real time. A shuffled K-fold split, run for comparison, mixes future
and past and looks better than it is (look-ahead bias, section 4 of the Phase 7 document).

Explanations are exact tree SHAP values from LightGBM itself (`pred_contrib=True`): for one
fund, the contribution of each feature to the log-odds of "top quartile" next to the average.
"""

import math
from dataclasses import dataclass, field
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.model_selection import KFold

from app.ml.features import FEATURES, HORIZON, matrix

CLASSES = 4
TOP = 0  # class index of quartile 1
SEED = 0
# Hyper-parameters chosen on the TUNING years 2018-2020 only (Phase 7 document, section 4.4),
# then fixed for the years that are reported: very shallow trees (4 leaves), at least 1,000
# fund-months per leaf and 100 rounds. Fund returns are noisy; deeper or longer-trained models
# learned year-specific patterns and ranked worse on the next year.
PARAMS: dict[str, Any] = {
    "objective": "multiclass",
    "num_class": CLASSES,
    "learning_rate": 0.03,
    "num_leaves": 4,
    "min_data_in_leaf": 1000,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "seed": SEED,
    "deterministic": True,
    "num_threads": 4,
    "verbose": -1,
}
ROUNDS = 100
TUNING_YEARS = [2018, 2019, 2020]
REPORTED_YEARS = [2021, 2022, 2023, 2024, 2025]


def train(panel: pd.DataFrame, rounds: int = ROUNDS) -> lgb.Booster:
    labelled = panel[panel["quartile"].notna()]
    data = lgb.Dataset(
        matrix(labelled),
        label=labelled["quartile"].to_numpy(dtype=int) - 1,
        feature_name=list(FEATURES),
        free_raw_data=True,
    )
    return lgb.train(PARAMS, data, num_boost_round=rounds)


def probabilities(model: lgb.Booster, panel: pd.DataFrame) -> np.ndarray:
    """(rows, 4): probability of each quartile."""
    return model.predict(matrix(panel))


def expected_quartile(probs: np.ndarray) -> np.ndarray:
    """1 x P(Q1) + 2 x P(Q2) + 3 x P(Q3) + 4 x P(Q4): lower is better; used to rank."""
    return probs @ np.arange(1, CLASSES + 1)


def contributions(model: lgb.Booster, panel: pd.DataFrame) -> np.ndarray:
    """(rows, features + 1): SHAP values for the top-quartile class; the last column is the base."""
    raw = model.predict(matrix(panel), pred_contrib=True)
    per_class = np.asarray(raw).reshape(len(panel), CLASSES, len(FEATURES) + 1)
    return per_class[:, TOP, :]


# --- Walk-forward validation --------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    year: int
    train: np.ndarray  # boolean masks over the labelled panel
    test: np.ndarray


def walk_forward_folds(
    months: pd.Series, test_years: list[int], horizon: int = HORIZON
) -> list[Fold]:
    """Expanding-window folds with a purge: training targets end before the test year starts."""
    folds = []
    for year in test_years:
        start = pd.Timestamp(year=year, month=1, day=1)
        cutoff = start - pd.DateOffset(months=horizon)  # t + horizon <= start
        train = (months <= cutoff).to_numpy()
        test = (months.dt.year == year).to_numpy()
        if train.any() and test.any():
            folds.append(Fold(year, train, test))
    return folds


def _group_spearman(frame: pd.DataFrame, score: str) -> float:
    """Average rank correlation between score (higher = better) and the forward return, computed
    within each month and peer group (the comparison that matters), weighted by group size."""
    total, weight = 0.0, 0
    for _, group in frame.groupby(["month", "peer_group"]):
        if len(group) < 3 or group[score].nunique() < 2:
            continue
        rho = spearmanr(group[score], group["fwd_12m"]).statistic
        if not math.isnan(rho):
            total += rho * len(group)
            weight += len(group)
    return total / weight if weight else float("nan")


def _top_picks(frame: pd.DataFrame, score: str) -> tuple[float, float]:
    """Pick the best-scored 25% of each peer group each month (as an investor would).

    Returns (hit rate, median excess): the share of picks that really ended in the top quartile
    (random: 25%), and the median over month-groups of the picks' average forward return minus
    the group's, in percentage points. Medians and ranks, not means: a few thematic funds that
    doubled would otherwise decide the result.
    """
    hits, picks, excess = 0, 0, []
    for _, group in frame.groupby(["month", "peer_group"]):
        n = max(1, len(group) // 4)
        top = group.nlargest(n, score)
        hits += int((top["quartile"] == 1).sum())
        picks += n
        excess.append(top["fwd_12m"].mean() - group["fwd_12m"].mean())
    if not picks:
        return float("nan"), float("nan")
    return hits / picks, float(np.median(excess)) * 100


def evaluate(frame: pd.DataFrame, probs: np.ndarray | None, score: np.ndarray) -> dict[str, float]:
    """Classification and ranking metrics. `score`: higher = expected to do better."""
    truth = frame["quartile"].to_numpy(dtype=int)
    scored = frame.assign(score=score)
    hit_rate, excess = _top_picks(scored, "score")
    metrics = {
        "rows": len(frame),
        "rank_ic": round(float(_group_spearman(scored, "score")), 4),
        "top_pick_hit_rate": round(hit_rate, 4),
        "top_pick_median_excess": round(excess, 2),
    }
    if probs is not None:
        predicted = probs.argmax(axis=1) + 1
        top_predicted = predicted == 1
        metrics |= {
            "accuracy": round(accuracy_score(truth, predicted), 4),
            "macro_f1": round(f1_score(truth, predicted, average="macro"), 4),
            "log_loss": round(log_loss(truth - 1, probs, labels=list(range(CLASSES))), 4),
            "top_precision": round(float((truth[top_predicted] == 1).mean()), 4)
            if top_predicted.any()
            else float("nan"),
        }
    return metrics


@dataclass
class ValidationReport:
    folds: list[dict[str, Any]] = field(default_factory=list)
    pooled: dict[str, dict[str, float]] = field(default_factory=dict)
    leaky: dict[str, float] = field(default_factory=dict)


def validate(
    labelled: pd.DataFrame, test_years: list[int], rounds: int = ROUNDS
) -> ValidationReport:
    """Walk-forward: the model vs momentum (12-month peer rank) vs random, per year and pooled."""
    report = ValidationReport()
    rng = np.random.default_rng(SEED)
    pieces: dict[str, list] = {"model": [], "momentum": [], "random": []}
    for fold in walk_forward_folds(labelled["month"], test_years):
        model = train(labelled[fold.train], rounds)
        test = labelled[fold.test]
        probs = probabilities(model, test)
        model_score = -expected_quartile(probs)
        momentum = test["peer_ret_12m"].to_numpy()
        random = rng.random(len(test))
        report.folds.append(
            {
                "year": fold.year,
                "train_rows": int(fold.train.sum()),
                "model": evaluate(test, probs, model_score),
                "momentum": evaluate(test, _rank_probs(test, momentum), momentum),
                "random": evaluate(test, None, random),
            }
        )
        pieces["model"].append((test, probs, model_score))
        pieces["momentum"].append((test, _rank_probs(test, momentum), momentum))
        pieces["random"].append((test, None, random))
    for name, parts in pieces.items():
        frame = pd.concat([p[0] for p in parts])
        probs = None if parts[0][1] is None else np.vstack([p[1] for p in parts])
        report.pooled[name] = evaluate(frame, probs, np.concatenate([p[2] for p in parts]))
    report.leaky = leaky_validation(labelled, rounds)
    return report


def _rank_probs(frame: pd.DataFrame, score: np.ndarray) -> np.ndarray:
    """Turn a score into a hard quartile prediction within each month and peer group (one-hot),
    so a baseline can be scored with the same accuracy metrics."""
    ranks = (
        frame.assign(s=score).groupby(["month", "peer_group"])["s"].rank(ascending=False, pct=True)
    )
    quartile = np.clip(np.ceil(ranks.to_numpy() * 4), 1, 4).astype(int)
    one_hot = np.full((len(frame), CLASSES), 1e-6)
    one_hot[np.arange(len(frame)), quartile - 1] = 1.0
    return one_hot / one_hot.sum(axis=1, keepdims=True)


def leaky_validation(labelled: pd.DataFrame, rounds: int = ROUNDS, splits: int = 5) -> dict:
    """The WRONG way, for comparison: shuffled K-fold mixes months, so the model trains on the
    future of the funds it is tested on (and on overlapping 12-month targets)."""
    folds = KFold(n_splits=splits, shuffle=True, random_state=SEED)
    frames, all_probs = [], []
    for train_index, test_index in folds.split(labelled):
        model = train(labelled.iloc[train_index], rounds)
        test = labelled.iloc[test_index]
        frames.append(test)
        all_probs.append(probabilities(model, test))
    frame = pd.concat(frames)
    probs = np.vstack(all_probs)
    return evaluate(frame, probs, -expected_quartile(probs))


def global_importance(model: lgb.Booster, panel: pd.DataFrame, limit: int = 20_000) -> list[dict]:
    """Mean |SHAP| per feature for the top-quartile class: which inputs move predictions most."""
    sample = panel.sample(min(limit, len(panel)), random_state=SEED)
    values = np.abs(contributions(model, sample)[:, :-1]).mean(axis=0)
    order = np.argsort(values)[::-1]
    return [{"feature": FEATURES[i], "mean_abs_shap": round(float(values[i]), 4)} for i in order]
