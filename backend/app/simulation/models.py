"""Four return models: four ways of drawing random monthly returns.

Every model answers one question - "give me `paths` x `months` random monthly SHOCKS" - and the
shocks are centred: their expected value is zero. The engine adds the goal's expected monthly
log return to them (ADR-008). The models therefore differ only in the shape of risk:

* normal - sigma x z with z ~ N(0, 1), independent months: average volatility only.
* bootstrap - real months of history, drawn in 12-month blocks: fat tails, crashes and
  short-term patterns, whatever history contained.
* garch - sigma_t x z with sigma_t^2 = omega + alpha e_{t-1}^2 + beta sigma_{t-1}^2: volatility
  clustering, calm and stormy spells.
* hmm - the mean and sigma of a hidden regime (calm or turbulent) that switches by a Markov
  chain: bull and bear regimes that persist for months.

Fitting (`fit`) estimates the parameters from a history of monthly log returns: GARCH with the
`arch` package and the HMM with `hmmlearn`, both by maximum likelihood. Simulating (`shocks`) is
our own vectorised NumPy code, seeded, so every run can be reproduced exactly.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol

import numpy as np

from app.finance.tvm import MONTHS_PER_YEAR

ModelName = Literal["normal", "bootstrap", "garch", "hmm"]
MODEL_NAMES: tuple[ModelName, ...] = ("normal", "bootstrap", "garch", "hmm")

# Used only when no market history is loaded (normal model only): long-run annual volatility.
ASSUMED_EQUITY_VOLATILITY = 0.18
ASSUMED_DEBT_VOLATILITY = 0.03

BLOCK_MONTHS = 12
HMM_RESTARTS = 5  # EM finds a local maximum; the best of a few starting points is kept

SQRT_12 = math.sqrt(MONTHS_PER_YEAR)


class ReturnModel(Protocol):
    name: ClassVar[ModelName]

    def shocks(self, rng: np.random.Generator, paths: int, months: int) -> np.ndarray:
        """Centred monthly log-return shocks, shape (paths, months)."""
        ...

    @property
    def annual_volatility(self) -> float:
        """Long-run standard deviation of the shocks, annualised with sqrt(12)."""
        ...

    def details(self) -> dict[str, Any]:
        """Fitted parameters, for the API response and the stored run."""
        ...


def _centre(log_returns: np.ndarray) -> np.ndarray:
    values = np.asarray(log_returns, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("need a 1-D history of at least 2 monthly returns")
    return values - values.mean()


# --- 1. Normal (log-normal prices) ------------------------------------------------------------


@dataclass(frozen=True)
class NormalModel:
    """Independent, normally distributed monthly log returns with a constant volatility."""

    name: ClassVar[ModelName] = "normal"
    sigma: float  # monthly standard deviation of log returns
    source: str = "history"

    @classmethod
    def fit(cls, log_returns: np.ndarray) -> "NormalModel":
        return cls(sigma=float(np.std(_centre(log_returns), ddof=1)))

    @classmethod
    def assumed(cls, equity_share: float) -> "NormalModel":
        """Volatility from fixed assumptions (no market data): equity 18%, debt 3%, uncorrelated.

        Portfolio variance of two uncorrelated assets: (e s_e)^2 + ((1 - e) s_d)^2.
        """
        annual = math.hypot(
            equity_share * ASSUMED_EQUITY_VOLATILITY, (1 - equity_share) * ASSUMED_DEBT_VOLATILITY
        )
        return cls(sigma=annual / SQRT_12, source="assumption")

    def shocks(self, rng: np.random.Generator, paths: int, months: int) -> np.ndarray:
        return self.sigma * rng.standard_normal((paths, months))

    @property
    def annual_volatility(self) -> float:
        return self.sigma * SQRT_12

    def details(self) -> dict[str, Any]:
        return {"monthly_sigma": self.sigma, "source": self.source}


# --- 2. Block bootstrap -----------------------------------------------------------------------


@dataclass(frozen=True)
class BlockBootstrapModel:
    """Resample real (centred) months of history in blocks of consecutive months.

    Drawing single months would keep the distribution of returns (fat tails, crashes) but
    destroy any pattern across months: a crash followed by a rebound, a calm year. Blocks keep
    those patterns inside each block. Blocks wrap around the end of the history (a "circular"
    bootstrap), so every month is equally likely to be drawn and the shocks average exactly 0.
    """

    name: ClassVar[ModelName] = "bootstrap"
    residuals: tuple[float, ...]  # the history minus its mean
    block_months: int = BLOCK_MONTHS

    @classmethod
    def fit(
        cls, log_returns: np.ndarray, block_months: int = BLOCK_MONTHS
    ) -> "BlockBootstrapModel":
        if block_months < 1:
            raise ValueError("block length must be at least 1 month")
        return cls(residuals=tuple(_centre(log_returns).tolist()), block_months=block_months)

    def shocks(self, rng: np.random.Generator, paths: int, months: int) -> np.ndarray:
        history = np.asarray(self.residuals)
        n, block = len(history), self.block_months
        blocks = -(-months // block)  # ceiling division
        starts = rng.integers(0, n, size=(paths, blocks))
        # Index of every month of every block: start, start + 1, ..., wrapping around at n.
        index = (starts[:, :, None] + np.arange(block)) % n
        return history[index.reshape(paths, blocks * block)[:, :months]]

    @property
    def annual_volatility(self) -> float:
        return float(np.std(self.residuals, ddof=1)) * SQRT_12

    def details(self) -> dict[str, Any]:
        return {"block_months": self.block_months, "history_months": len(self.residuals)}


# --- 3. GARCH(1, 1) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GarchModel:
    """Volatility that clusters: a big shock raises next month's volatility.

        e_t = sigma_t z_t,   sigma_t^2 = omega + alpha e_{t-1}^2 + beta sigma_{t-1}^2

    alpha: how strongly last month's shock feeds volatility; beta: how long high volatility
    lasts. alpha + beta < 1 ("persistence") makes volatility return to its long-run level
    omega / (1 - alpha - beta). Paths start at that long-run level, not at today's volatility,
    so a 15-year plan does not swing with this month's market mood.
    """

    name: ClassVar[ModelName] = "garch"
    omega: float  # in squared monthly log-return units
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if self.omega <= 0 or self.alpha < 0 or self.beta < 0 or self.alpha + self.beta >= 1:
            raise ValueError("GARCH needs omega > 0, alpha, beta >= 0 and alpha + beta < 1")

    @classmethod
    def fit(cls, log_returns: np.ndarray) -> "GarchModel":
        from arch import arch_model  # imported here: heavy, and only needed for fitting

        # arch's optimiser works best on percentages, so fit on 100 x returns and scale back.
        scaled = _centre(log_returns) * 100
        result = arch_model(scaled, mean="Zero", vol="GARCH", p=1, q=1, rescale=False).fit(
            disp="off"
        )
        alpha, beta = float(result.params["alpha[1]"]), float(result.params["beta[1]"])
        if alpha + beta >= 0.999:  # (almost) no mean reversion: keep the long-run level finite
            beta = 0.999 - alpha
        return cls(omega=float(result.params["omega"]) / 100**2, alpha=alpha, beta=beta)

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def long_run_variance(self) -> float:
        return self.omega / (1 - self.persistence)

    def shocks(self, rng: np.random.Generator, paths: int, months: int) -> np.ndarray:
        z = rng.standard_normal((paths, months))
        out = np.empty_like(z)
        variance = np.full(paths, self.long_run_variance)
        # Each month depends on the previous one, so the loop over months stays; every step is
        # vectorised over all paths at once.
        for t in range(months):
            out[:, t] = np.sqrt(variance) * z[:, t]
            variance = self.omega + self.alpha * out[:, t] ** 2 + self.beta * variance
        return out

    @property
    def annual_volatility(self) -> float:
        return math.sqrt(self.long_run_variance) * SQRT_12

    def details(self) -> dict[str, Any]:
        return {
            "omega": self.omega,
            "alpha": self.alpha,
            "beta": self.beta,
            "persistence": self.persistence,
            # Months for a volatility shock to fade by half: persistence^h = 0.5.
            "half_life_months": math.log(0.5) / math.log(self.persistence)
            if 0 < self.persistence < 1
            else None,
        }


# --- 4. Two-state hidden Markov model ---------------------------------------------------------


@dataclass(frozen=True)
class RegimeModel:
    """Markets switch between a calm and a turbulent regime that each last for a while.

    The regime is hidden (never observed directly). Each month the return is drawn from the
    current regime's normal distribution, then the regime moves on according to the transition
    matrix P, where P[i][j] = probability of moving from regime i to regime j next month.
    Regime 0 is the calm one (lower volatility). Paths start in a regime drawn from the
    long-run (stationary) shares, and the regime means are shifted together so that the shocks
    average exactly 0 - the turbulent regime keeps its lower mean relative to the calm one.
    """

    name: ClassVar[ModelName] = "hmm"
    means: tuple[float, float]
    stds: tuple[float, float]
    transition: tuple[tuple[float, float], tuple[float, float]]
    log_likelihood: float | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        for row in self.transition:
            if min(row) < 0 or not math.isclose(sum(row), 1.0, abs_tol=1e-9):
                raise ValueError("each row of the transition matrix must be probabilities")

    @classmethod
    def fit(cls, log_returns: np.ndarray) -> "RegimeModel":
        from hmmlearn.hmm import GaussianHMM

        logging.getLogger("hmmlearn").setLevel(logging.ERROR)  # "not converging" chatter
        data = _centre(log_returns).reshape(-1, 1)
        best, best_score = None, -math.inf
        for seed in range(HMM_RESTARTS):
            hmm = GaussianHMM(
                n_components=2, covariance_type="diag", n_iter=500, tol=1e-8, random_state=seed
            )
            hmm.fit(data)
            score = hmm.score(data)
            if score > best_score:
                best, best_score = hmm, score
        assert best is not None
        means = best.means_[:, 0]
        stds = np.sqrt(best.covars_[:, 0, 0])
        order = np.argsort(stds)  # calm regime first
        matrix = best.transmat_[np.ix_(order, order)]
        rows = [row / row.sum() for row in matrix]
        return cls(
            means=(float(means[order[0]]), float(means[order[1]])),
            stds=(float(stds[order[0]]), float(stds[order[1]])),
            transition=(
                (float(rows[0][0]), float(rows[0][1])),
                (float(rows[1][0]), float(rows[1][1])),
            ),
            log_likelihood=float(best_score),
        )

    @property
    def stationary(self) -> tuple[float, float]:
        """Long-run share of months in each regime: pi_0 = P10 / (P01 + P10)."""
        leave_calm, leave_turbulent = self.transition[0][1], self.transition[1][0]
        if leave_calm + leave_turbulent == 0:
            return (0.5, 0.5)
        calm = leave_turbulent / (leave_calm + leave_turbulent)
        return (calm, 1 - calm)

    @property
    def _long_run_mean(self) -> float:
        share = self.stationary
        return share[0] * self.means[0] + share[1] * self.means[1]

    def shocks(self, rng: np.random.Generator, paths: int, months: int) -> np.ndarray:
        means = np.asarray(self.means) - self._long_run_mean
        stds = np.asarray(self.stds)
        to_turbulent = np.array([self.transition[0][1], self.transition[1][1]])
        regime = (rng.random(paths) < self.stationary[1]).astype(np.intp)
        z = rng.standard_normal((paths, months))
        u = rng.random((paths, months))
        out = np.empty_like(z)
        for t in range(months):
            out[:, t] = means[regime] + stds[regime] * z[:, t]
            regime = (u[:, t] < to_turbulent[regime]).astype(np.intp)
        return out

    @property
    def annual_volatility(self) -> float:
        """Std of the mixture: sqrt(sum pi_k (s_k^2 + (m_k - m)^2)) x sqrt(12)."""
        share, mean = self.stationary, self._long_run_mean
        variance = sum(
            share[k] * (self.stds[k] ** 2 + (self.means[k] - mean) ** 2) for k in range(2)
        )
        return math.sqrt(variance) * SQRT_12

    def details(self) -> dict[str, Any]:
        share = self.stationary
        return {
            "regimes": [
                {
                    "name": label,
                    "annual_return_shift": (self.means[k] - self._long_run_mean) * MONTHS_PER_YEAR,
                    "annual_volatility": self.stds[k] * SQRT_12,
                    "long_run_share": share[k],
                    # A regime that is left with probability p each month lasts 1/p months.
                    "average_months": 1 / (1 - self.transition[k][k])
                    if self.transition[k][k] < 1
                    else None,
                }
                for k, label in enumerate(("calm", "turbulent"))
            ],
            "transition": [list(row) for row in self.transition],
        }


def preload_fitting_libraries() -> None:
    """Import the fitting libraries ahead of time (they load pandas and SciPy: seconds)."""
    import arch  # noqa: F401
    import hmmlearn.hmm  # noqa: F401


FITTERS = {
    "normal": NormalModel.fit,
    "bootstrap": BlockBootstrapModel.fit,
    "garch": GarchModel.fit,
    "hmm": RegimeModel.fit,
}


def fit_model(name: ModelName, log_returns: np.ndarray) -> ReturnModel:
    return FITTERS[name](log_returns)
