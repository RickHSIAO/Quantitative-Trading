from __future__ import annotations

import math

import numpy as np
import pandas as pd


def compute_cost_stress_metrics(
    daily: pd.DataFrame,
    annualization: float,
) -> dict[str, float | int | str]:
    full = _period_metrics(daily, annualization)
    active_daily = daily[daily["gross_exposure"].astype(float) > 0].copy()
    active = _period_metrics(active_daily, annualization)
    return {
        "total_return_full": full["total_return"],
        "total_return_active": active["total_return"],
        "sharpe_full": full["sharpe"],
        "sharpe_active": active["sharpe"],
        "ir_vs_cash_full": _benchmark_ir(daily, "benchmark_cash_return", annualization),
        "ir_vs_cash_active": _benchmark_ir(active_daily, "benchmark_cash_return", annualization),
        "ir_vs_btc_full": _benchmark_ir(daily, "benchmark_btc_return", annualization),
        "ir_vs_btc_active": _benchmark_ir(active_daily, "benchmark_btc_return", annualization),
        "ir_vs_equal_weight_full": _benchmark_ir(daily, "benchmark_eqw_return", annualization),
        "ir_vs_equal_weight_active": _benchmark_ir(active_daily, "benchmark_eqw_return", annualization),
        "max_dd_full": full["max_dd"],
        "max_dd_active": active["max_dd"],
        "calmar_full": full["calmar"],
        "calmar_active": active["calmar"],
        "turnover_annual_full": full["turnover_annual"],
        "turnover_annual_active": active["turnover_annual"],
        "effective_days_full": int(len(daily)),
        "effective_days_active": int(len(active_daily)),
    }


def _period_metrics(daily: pd.DataFrame, annualization: float) -> dict[str, float]:
    if daily.empty:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_dd": 0.0,
            "calmar": 0.0,
            "turnover_annual": 0.0,
        }
    returns = daily["portfolio_return_net"].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    running_max = equity.cummax()
    max_dd = float((equity / running_max - 1.0).min()) if len(equity) else 0.0
    years = max(float(len(daily)) / float(annualization), 1.0 / float(annualization))
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    return {
        "total_return": total_return,
        "sharpe": _annual_ratio(returns, annualization),
        "max_dd": max_dd,
        "calmar": _safe_div(cagr, abs(max_dd)),
        "turnover_annual": float(daily["turnover"].astype(float).sum() / years),
    }


def _benchmark_ir(daily: pd.DataFrame, benchmark_col: str, annualization: float) -> float:
    if daily.empty or benchmark_col not in daily.columns:
        return 0.0
    diff = daily["portfolio_return_net"].astype(float) - daily[benchmark_col].astype(float)
    return _annual_ratio(diff, annualization)


def _annual_ratio(series: pd.Series, annualization: float) -> float:
    clean = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    std = float(clean.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return 0.0
    return float(clean.mean() / std * math.sqrt(float(annualization)))


def _safe_div(num: float, den: float) -> float:
    if den == 0.0 or math.isnan(den):
        return 0.0
    return float(num / den)
