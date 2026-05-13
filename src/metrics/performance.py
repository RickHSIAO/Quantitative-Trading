"""Performance statistics reproducible from baseline.csv."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


STATS_SCHEMA = [
    {"name": "ir", "type": "float64", "unit": "annualized active return / active volatility"},
    {"name": "sharpe", "type": "float64", "unit": "annualized mean portfolio return / volatility"},
    {"name": "sortino", "type": "float64", "unit": "annualized mean portfolio return / downside volatility"},
    {"name": "max_dd", "type": "float64", "unit": "decimal drawdown"},
    {"name": "calmar", "type": "float64", "unit": "CAGR / abs(max drawdown)"},
    {"name": "turnover_annual", "type": "float64", "unit": "sum daily turnover / elapsed years"},
    {"name": "hit_rate", "type": "float64", "unit": "share of active days with positive portfolio return"},
    {"name": "exposure_stats", "type": "object", "unit": "gross/net/position count summary"},
]


def compute_stats(baseline: pd.DataFrame, annualization: float = 365.25) -> dict[str, object]:
    returns = baseline["portfolio_return"].astype(float)
    benchmark = baseline["benchmark_return"].astype(float)
    active = returns - benchmark
    equity = (1.0 + returns).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0
    years = max(len(baseline) / annualization, 1.0 / annualization)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if not equity.empty and equity.iloc[-1] > 0 else -1.0

    active_days = baseline["gross_exposure"].astype(float) > 0
    active_returns = returns[active_days]
    hit_rate = float((active_returns > 0).mean()) if len(active_returns) else 0.0

    stats = {
        "ir": _annual_ratio(active, annualization),
        "sharpe": _annual_ratio(returns, annualization),
        "sortino": _sortino(returns, annualization),
        "max_dd": max_dd,
        "calmar": _safe_div(cagr, abs(max_dd)),
        "turnover_annual": float(baseline["turnover"].astype(float).sum() / years),
        "hit_rate": hit_rate,
        "exposure_stats": {
            "gross_mean": float(baseline["gross_exposure"].astype(float).mean()),
            "gross_max": float(baseline["gross_exposure"].astype(float).max()),
            "net_mean": float(baseline["net_exposure"].astype(float).mean()),
            "net_min": float(baseline["net_exposure"].astype(float).min()),
            "net_max": float(baseline["net_exposure"].astype(float).max()),
            "avg_longs": float(baseline["n_longs"].astype(float).mean()),
            "avg_shorts": float(baseline["n_shorts"].astype(float).mean()),
        },
    }
    return _clean(stats)


def _annual_ratio(series: pd.Series, annualization: float) -> float:
    series = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return 0.0
    std = float(series.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return 0.0
    return float(series.mean() / std * math.sqrt(annualization))


def _sortino(series: pd.Series, annualization: float) -> float:
    series = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    downside = series[series < 0]
    if series.empty or downside.empty:
        return 0.0
    downside_std = float(downside.std(ddof=1))
    if downside_std == 0.0 or math.isnan(downside_std):
        return 0.0
    return float(series.mean() / downside_std * math.sqrt(annualization))


def _safe_div(num: float, den: float) -> float:
    if den == 0.0 or math.isnan(den):
        return 0.0
    return float(num / den)


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(val) for key, val in value.items()}
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value)
    return value
