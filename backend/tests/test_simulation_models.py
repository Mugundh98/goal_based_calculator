"""Statistical tests of the four return models: shapes, means, fitting on synthetic data.

Synthetic data with known parameters is generated, the model is fitted, and the estimates must
come back close to the truth. Every test is seeded.
"""

import math

import numpy as np
import pytest

from app.simulation.models import (
    BlockBootstrapModel,
    GarchModel,
    NormalModel,
    RegimeModel,
    fit_model,
)

RNG_SEED = 3


def rng():
    return np.random.default_rng(RNG_SEED)


def autocorrelation(x: np.ndarray) -> float:
    """Lag-1 autocorrelation of each path's series, averaged over paths."""
    a, b = x[:, :-1] - x.mean(), x[:, 1:] - x.mean()
    return float((a * b).mean() / x.var())


# --- Normal -----------------------------------------------------------------------------------


def test_normal_shocks_have_mean_zero_and_the_fitted_sigma():
    history = np.array([0.03, -0.01, 0.02, -0.04, 0.05, 0.00])
    model = NormalModel.fit(history)
    assert model.sigma == pytest.approx(np.std(history, ddof=1))
    shocks = model.shocks(rng(), 2_000, 120)
    standard_error = model.sigma / math.sqrt(shocks.size)
    assert abs(shocks.mean()) < 4 * standard_error
    assert shocks.std() == pytest.approx(model.sigma, rel=0.01)
    assert model.annual_volatility == pytest.approx(model.sigma * math.sqrt(12))


def test_assumed_volatility_without_market_data():
    assert NormalModel.assumed(1.0).annual_volatility == pytest.approx(0.18)
    assert NormalModel.assumed(0.0).annual_volatility == pytest.approx(0.03)
    # 50/50, uncorrelated: sqrt(0.09^2 + 0.015^2) = 9.12%
    assert NormalModel.assumed(0.5).annual_volatility == pytest.approx(math.hypot(0.09, 0.015))
    assert NormalModel.assumed(0.5).details()["source"] == "assumption"


# --- Block bootstrap --------------------------------------------------------------------------


def test_bootstrap_draws_whole_blocks_of_real_history():
    history = np.arange(10, dtype=float)  # 0..9, mean 4.5
    model = BlockBootstrapModel.fit(history, block_months=4)
    assert model.residuals == tuple(history - 4.5)
    shocks = model.shocks(rng(), 50, 10) + 4.5
    # Every value is a real month, and inside a block consecutive months follow each other
    # (wrapping from 9 back to 0).
    assert set(np.unique(shocks)) <= set(history)
    for path in shocks:
        for block_start in (0, 4, 8):
            block = path[block_start : block_start + 4]
            assert all((b - a) % 10 == 1 for a, b in zip(block, block[1:], strict=False))


def test_bootstrap_is_centred_and_keeps_the_volatility():
    history = rng().standard_t(df=4, size=200) * 0.04 + 0.01  # fat-tailed, mean 1%
    model = BlockBootstrapModel.fit(history)
    shocks = model.shocks(np.random.default_rng(9), 4_000, 120)
    assert abs(shocks.mean()) < 0.001
    assert shocks.std() == pytest.approx(np.std(history), rel=0.02)
    # Fat tails survive (a normal distribution has kurtosis 3).
    kurtosis = ((shocks - shocks.mean()) ** 4).mean() / shocks.var() ** 2
    assert kurtosis > 3.5


def test_bootstrap_blocks_keep_month_to_month_patterns():
    # A history in which a good month is always followed by a bad one (negative autocorrelation).
    history = np.tile([0.05, -0.05], 60)
    blocks = BlockBootstrapModel.fit(history, block_months=12).shocks(rng(), 500, 60)
    singles = BlockBootstrapModel.fit(history, block_months=1).shocks(rng(), 500, 60)
    assert autocorrelation(blocks) < -0.8
    assert abs(autocorrelation(singles)) < 0.05


def test_bootstrap_rejects_bad_block_length():
    with pytest.raises(ValueError):
        BlockBootstrapModel.fit(np.zeros(10), block_months=0)


# --- GARCH(1, 1) ------------------------------------------------------------------------------


def simulate_garch(omega, alpha, beta, n, seed):
    generator = np.random.default_rng(seed)
    out, variance = np.empty(n), omega / (1 - alpha - beta)
    for t in range(n):
        out[t] = math.sqrt(variance) * generator.standard_normal()
        variance = omega + alpha * out[t] ** 2 + beta * variance
    return out


def test_garch_long_run_variance_and_half_life():
    model = GarchModel(omega=0.0002, alpha=0.1, beta=0.8)
    assert model.persistence == pytest.approx(0.9)
    assert model.long_run_variance == pytest.approx(0.002)  # 0.0002 / (1 - 0.9)
    assert model.annual_volatility == pytest.approx(math.sqrt(0.002 * 12))
    assert model.details()["half_life_months"] == pytest.approx(math.log(0.5) / math.log(0.9))
    with pytest.raises(ValueError):
        GarchModel(omega=0.0002, alpha=0.5, beta=0.5)


def test_garch_shocks_cluster_and_keep_the_long_run_variance():
    model = GarchModel(omega=0.0002, alpha=0.15, beta=0.8)
    shocks = model.shocks(rng(), 4_000, 120)
    assert abs(shocks.mean()) < 0.001
    assert shocks.var() == pytest.approx(model.long_run_variance, rel=0.05)
    # Volatility clustering: big shocks follow big shocks, so SQUARED shocks are correlated,
    # while the shocks themselves are not.
    assert autocorrelation(shocks**2) > 0.1
    assert abs(autocorrelation(shocks)) < 0.02
    normal = NormalModel(math.sqrt(model.long_run_variance)).shocks(rng(), 4_000, 120)
    assert abs(autocorrelation(normal**2)) < 0.02


def test_garch_fit_recovers_known_parameters():
    data = simulate_garch(omega=0.0002, alpha=0.15, beta=0.75, n=5_000, seed=1) + 0.01
    model = GarchModel.fit(data)
    assert model.alpha == pytest.approx(0.15, abs=0.05)
    assert model.beta == pytest.approx(0.75, abs=0.08)
    assert model.long_run_variance == pytest.approx(0.002, rel=0.15)


# --- Two-state HMM ----------------------------------------------------------------------------

HMM = RegimeModel(
    means=(0.01, -0.03),
    stds=(0.03, 0.08),
    transition=((0.9, 0.1), (0.3, 0.7)),
)


def test_hmm_stationary_shares_by_hand():
    # pi_calm = P(turbulent -> calm) / (P(calm -> turbulent) + P(turbulent -> calm))
    #         = 0.3 / (0.1 + 0.3) = 0.75
    assert HMM.stationary == pytest.approx((0.75, 0.25))
    details = HMM.details()
    assert details["regimes"][0]["average_months"] == pytest.approx(10)  # 1 / (1 - 0.9)
    assert details["regimes"][1]["average_months"] == pytest.approx(1 / 0.3)
    # Long-run mean 0.75 x 1% + 0.25 x -3% = 0; shifts are relative to it.
    assert details["regimes"][1]["annual_return_shift"] == pytest.approx(-0.36)


def test_hmm_shocks_are_centred_with_the_mixture_volatility():
    shocks = HMM.shocks(rng(), 4_000, 120)
    assert abs(shocks.mean()) < 0.001
    assert shocks.std() * math.sqrt(12) == pytest.approx(HMM.annual_volatility, rel=0.02)
    # Regimes persist, so squared shocks are correlated (like GARCH, for a different reason).
    assert autocorrelation(shocks**2) > 0.05


def test_hmm_rejects_a_bad_transition_matrix():
    with pytest.raises(ValueError):
        RegimeModel(means=(0, 0), stds=(0.1, 0.2), transition=((0.9, 0.2), (0.5, 0.5)))


def test_hmm_fit_finds_the_calm_and_the_turbulent_regime():
    generator = np.random.default_rng(4)
    regime, data = 0, []
    for _ in range(3_000):
        data.append(generator.normal(HMM.means[regime], HMM.stds[regime]))
        regime = int(generator.random() < HMM.transition[regime][1])
    model = RegimeModel.fit(np.array(data))
    assert model.stds[0] == pytest.approx(0.03, rel=0.15)
    assert model.stds[1] == pytest.approx(0.08, rel=0.15)
    assert model.transition[0][0] == pytest.approx(0.9, abs=0.05)
    assert model.transition[1][1] == pytest.approx(0.7, abs=0.1)
    assert model.stationary[0] == pytest.approx(0.75, abs=0.08)
    assert model.means[1] < model.means[0]  # the turbulent regime has the lower mean


# --- Common behaviour -------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["normal", "bootstrap", "garch", "hmm"])
def test_every_model_is_reproducible_and_centred(name):
    history = simulate_garch(omega=0.0003, alpha=0.1, beta=0.8, n=300, seed=2) + 0.01
    model = fit_model(name, history)
    first = model.shocks(np.random.default_rng(1), 1_000, 60)
    again = model.shocks(np.random.default_rng(1), 1_000, 60)
    np.testing.assert_array_equal(first, again)
    assert first.shape == (1_000, 60)
    assert abs(first.mean()) < 0.002
    # Every model keeps roughly the volatility of the history it was fitted to.
    assert model.annual_volatility == pytest.approx(np.std(history) * math.sqrt(12), rel=0.25)
    assert isinstance(model.details(), dict)
