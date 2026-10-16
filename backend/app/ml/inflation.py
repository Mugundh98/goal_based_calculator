"""Inflation forecast: a seasonal ARIMA (SARIMA) model of the monthly Consumer Price Index.

The model is fitted to log CPI with one ordinary and one seasonal (12-month) difference, so it
describes the month-to-month changes in inflation and the yearly pattern (vegetable prices rise
every monsoon, for example). The orders (p, q, P, Q) are chosen by AIC on the data before the
first evaluation date only. Walk-forward evaluation: from each origin, forecast the next 12
months of year-on-year inflation and compare with what happened, against two baselines - "the
current rate persists" (naive) and "the RBI's 4% target".

The final forecast covers the next 12 months, with an exact 80% band from the forecast's normal
distribution (section 4.6 of the Phase 7 document).
"""

import itertools
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

SEASON = 12
RBI_TARGET = 0.04
ORDERS = [(p, 1, q) for p, q in itertools.product((0, 1, 2), (0, 1))]
SEASONAL_ORDERS = [(sp, 1, sq, SEASON) for sp, sq in ((0, 1), (1, 1), (1, 0))]


def yoy(cpi: pd.Series) -> pd.Series:
    """Year-on-year inflation: CPI / CPI twelve months earlier - 1."""
    return cpi / cpi.shift(SEASON) - 1


def _fit(log_cpi: pd.Series, order: tuple, seasonal: tuple):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence chatter from the optimiser
        model = SARIMAX(log_cpi, order=order, seasonal_order=seasonal, trend="n")
        return model.fit(disp=False)


def choose_order(log_cpi: pd.Series) -> tuple[tuple, tuple, list[dict[str, Any]]]:
    """Lowest AIC over a small grid (the AIC trades fit against the number of parameters)."""
    results = []
    for order, seasonal in itertools.product(ORDERS, SEASONAL_ORDERS):
        try:
            aic = _fit(log_cpi, order, seasonal).aic
        except (ValueError, np.linalg.LinAlgError):
            continue
        results.append({"order": order, "seasonal_order": seasonal, "aic": round(float(aic), 2)})
    best = min(results, key=lambda r: r["aic"])
    return best["order"], best["seasonal_order"], sorted(results, key=lambda r: r["aic"])


def forecast_yoy(cpi: pd.Series, order: tuple, seasonal: tuple, months: int) -> pd.Series:
    """Point forecast of year-on-year inflation for the next `months` months."""
    result = _fit(np.log(cpi), order, seasonal)
    future = np.exp(result.forecast(months))
    path = pd.concat([cpi, pd.Series(future.to_numpy(), index=_next_months(cpi.index, months))])
    return yoy(path).iloc[-months:]


def _next_months(index: pd.DatetimeIndex, months: int) -> pd.DatetimeIndex:
    return pd.date_range(index[-1] + pd.DateOffset(months=1), periods=months, freq="MS")


@dataclass(frozen=True)
class Evaluation:
    origins: list[str]
    mae: dict[str, float]  # mean absolute error of 12-month-ahead YoY inflation, percentage points
    mae_by_horizon: dict[str, list[float]]


def evaluate(
    cpi: pd.Series, order: tuple, seasonal: tuple, origins: list[pd.Timestamp]
) -> Evaluation:
    """Walk-forward: refit at each origin on data up to it, forecast 12 months, compare."""
    actual = yoy(cpi)
    errors: dict[str, list[list[float]]] = {"sarima": [], "naive": [], "rbi_target": []}
    used = []
    for origin in origins:
        history = cpi.loc[:origin]
        future = actual.loc[origin + pd.DateOffset(months=1) :].iloc[:SEASON]
        if len(future) < SEASON:
            continue
        predicted = forecast_yoy(history, order, seasonal, SEASON)
        errors["sarima"].append(list(np.abs(predicted.to_numpy() - future.to_numpy())))
        errors["naive"].append(list(np.abs(actual.loc[origin] - future.to_numpy())))
        errors["rbi_target"].append(list(np.abs(RBI_TARGET - future.to_numpy())))
        used.append(origin.strftime("%Y-%m"))
    return Evaluation(
        origins=used,
        # Error of the 12-month-ahead forecast (the last horizon), in percentage points.
        mae={k: round(float(np.mean([e[-1] for e in v])) * 100, 2) for k, v in errors.items()},
        mae_by_horizon={
            k: [round(float(x) * 100, 2) for x in np.mean(np.array(v), axis=0)]
            for k, v in errors.items()
        },
    )


def forecast_band(cpi: pd.Series, order: tuple, seasonal: tuple) -> list[dict[str, Any]]:
    """Median and 80% band of year-on-year inflation for the next 12 months.

    For h <= 12 months the CPI a year before the forecast month is already known, so
    YoY = exp(log CPI forecast - log CPI known) - 1. The log forecast is normally distributed,
    and exp is increasing, so its 10th/50th/90th percentiles map straight to YoY percentiles:
    exact, no simulation needed.
    """
    result = _fit(np.log(cpi), order, seasonal)
    forecast = result.get_forecast(SEASON)
    mean = forecast.predicted_mean.to_numpy()
    band = forecast.conf_int(alpha=0.2).to_numpy()  # 80% interval of log CPI
    base = np.log(cpi.to_numpy()[-SEASON:])  # log CPI one year before each forecast month
    out = []
    for h, month in enumerate(_next_months(cpi.index, SEASON)):
        out.append(
            {
                "month": month.strftime("%Y-%m-%d"),
                "p10": round(float(np.expm1(band[h, 0] - base[h])) * 100, 2),
                "p50": round(float(np.expm1(mean[h] - base[h])) * 100, 2),
                "p90": round(float(np.expm1(band[h, 1] - base[h])) * 100, 2),
            }
        )
    return out
