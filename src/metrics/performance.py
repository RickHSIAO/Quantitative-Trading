"""Performance statistics reproducible from baseline.csv."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


STATS_SCHEMA = [
    {"name": "ir", "type": "float64", "unit": "legacy full-period alias for ir_full"},
    {"name": "sharpe", "type": "float64", "unit": "legacy full-period alias for sharpe_full"},
    {"name": "sortino", "type": "float64", "unit": "legacy full-period alias for sortino_full"},
    {"name": "max_dd", "type": "float64", "unit": "legacy full-period alias for max_dd_full"},
    {"name": "calmar", "type": "float64", "unit": "legacy full-period alias for calmar_full"},
    {"name": "turnover_annual", "type": "float64", "unit": "legacy full-period alias for turnover_annual_full"},
    {"name": "hit_rate", "type": "float64", "unit": "legacy full-period alias for hit_rate_full"},
    {"name": "ir_full", "type": "float64", "unit": "full-period annualized active return / active volatility"},
    {"name": "ir_active", "type": "float64", "unit": "active-period annualized active return / active volatility"},
    {"name": "sharpe_full", "type": "float64", "unit": "full-period annualized mean portfolio return / volatility"},
    {"name": "sharpe_active", "type": "float64", "unit": "active-period annualized mean portfolio return / volatility"},
    {"name": "sortino_full", "type": "float64", "unit": "full-period annualized mean portfolio return / downside volatility"},
    {"name": "sortino_active", "type": "float64", "unit": "active-period annualized mean portfolio return / downside volatility"},
    {"name": "max_dd_full", "type": "float64", "unit": "full-period decimal drawdown"},
    {"name": "max_dd_active", "type": "float64", "unit": "active-period decimal drawdown"},
    {"name": "calmar_full", "type": "float64", "unit": "full-period CAGR / abs(max drawdown)"},
    {"name": "calmar_active", "type": "float64", "unit": "active-period CAGR / abs(max drawdown)"},
    {"name": "turnover_annual_full", "type": "float64", "unit": "full-period sum daily turnover / elapsed years"},
    {"name": "turnover_annual_active", "type": "float64", "unit": "active-period sum daily turnover / elapsed years"},
    {"name": "hit_rate_full", "type": "float64", "unit": "full-period share of days with positive portfolio return"},
    {"name": "hit_rate_active", "type": "float64", "unit": "active-period share of days with positive portfolio return"},
    {"name": "mean_daily_return_full", "type": "float64", "unit": "full-period arithmetic mean daily return"},
    {"name": "mean_daily_return_active", "type": "float64", "unit": "active-period arithmetic mean daily return"},
    {"name": "volatility_full", "type": "float64", "unit": "full-period annualized daily return volatility"},
    {"name": "volatility_active", "type": "float64", "unit": "active-period annualized daily return volatility"},
    {"name": "full_start_date", "type": "string", "unit": "full-period first date"},
    {"name": "full_end_date", "type": "string", "unit": "full-period last date"},
    {"name": "full_days", "type": "int64", "unit": "full-period row count"},
    {"name": "active_start_date", "type": "string", "unit": "active-period first date where gross_exposure > 0"},
    {"name": "active_end_date", "type": "string", "unit": "active-period last date where gross_exposure > 0"},
    {"name": "active_days", "type": "int64", "unit": "active-period row count where gross_exposure > 0"},
    {"name": "active_fraction", "type": "float64", "unit": "active_days / full_days"},
    {"name": "gross_exposure_mean_full", "type": "float64", "unit": "full-period mean gross exposure"},
    {"name": "gross_exposure_mean_active", "type": "float64", "unit": "active-period mean gross exposure"},
    {"name": "net_exposure_mean_full", "type": "float64", "unit": "full-period mean net exposure"},
    {"name": "net_exposure_mean_active", "type": "float64", "unit": "active-period mean net exposure"},
    {"name": "ir_vs_cash_full", "type": "float64", "unit": "full-period IR versus cash benchmark"},
    {"name": "ir_vs_cash_active", "type": "float64", "unit": "active-period IR versus cash benchmark"},
    {"name": "ir_vs_btc_full", "type": "float64", "unit": "full-period IR versus BTC benchmark; BTC NaN dates dropped"},
    {"name": "ir_vs_btc_active", "type": "float64", "unit": "active-period IR versus BTC benchmark"},
    {"name": "ir_vs_equal_weight_full", "type": "float64", "unit": "full-period IR versus PIT equal-weight benchmark"},
    {"name": "ir_vs_equal_weight_active", "type": "float64", "unit": "active-period IR versus PIT equal-weight benchmark"},
    {"name": "methodology", "type": "object", "unit": "formula conventions for reproducibility"},
    {"name": "data_quality_policy", "type": "object", "unit": "TASK-001d missing-data exclusion policy"},
    {"name": "dq_abnormal_symbol_days", "type": "int64", "unit": "unique hard abnormal symbol-days"},
    {"name": "dq_excluded_from_ranking_candidates", "type": "int64", "unit": "decision-date symbol candidates excluded from ranking"},
    {"name": "dq_excluded_from_holding_days", "type": "int64", "unit": "symbol-days excluded from holding/return calculation"},
    {"name": "dq_forced_holding_exits", "type": "int64", "unit": "held symbols removed by data-quality policy"},
    {"name": "dq_affected_symbols", "type": "int64", "unit": "symbols with non-warning data-quality events"},
    {"name": "benchmark_primary", "type": "string", "unit": "primary benchmark used by benchmark_return"},
    {"name": "benchmark_btc_symbol", "type": "string", "unit": "BTC benchmark symbol"},
    {"name": "benchmark_return_equals", "type": "string", "unit": "benchmark_return alias target"},
    {"name": "benchmark_btc_missing_days_full", "type": "int64", "unit": "full-period dates with unavailable BTC benchmark return"},
    {"name": "benchmark_btc_missing_days_active", "type": "int64", "unit": "active-period dates with unavailable BTC benchmark return"},
    {"name": "ir_vs_btc_full_effective_days", "type": "int64", "unit": "full-period rows used by IR versus BTC after dropping unavailable BTC returns"},
    {"name": "ir_vs_btc_active_effective_days", "type": "int64", "unit": "active-period rows used by IR versus BTC after dropping unavailable BTC returns"},
    {"name": "benchmark_eqw_effective_days_full", "type": "int64", "unit": "full-period dates with at least one available PIT equal-weight benchmark constituent"},
    {"name": "benchmark_eqw_effective_days_active", "type": "int64", "unit": "active-period dates with at least one available PIT equal-weight benchmark constituent"},
    {"name": "eqw_benchmark_avg_symbols", "type": "float64", "unit": "mean available symbols in PIT equal-weight benchmark"},
    {"name": "eqw_benchmark_min_symbols", "type": "int64", "unit": "minimum available symbols in PIT equal-weight benchmark"},
    {"name": "eqw_benchmark_missing_days", "type": "int64", "unit": "dates with zero available PIT equal-weight benchmark symbols"},
    {"name": "exposure_stats", "type": "object", "unit": "gross/net/position count summary"},
    {"name": "start_date", "type": "string", "unit": "configured backtest start date"},
    {"name": "end_date", "type": "string", "unit": "configured backtest end date"},
    {"name": "warmup_start_date", "type": "string", "unit": "configured warm-up start date"},
    {"name": "effective_entry_price", "type": "string", "unit": "configured effective entry price convention"},
    {"name": "rebalance_freq", "type": "string", "unit": "configured rebalance frequency"},
    {"name": "lookback_days", "type": "int64", "unit": "configured lookback days"},
    {"name": "top_n", "type": "int64", "unit": "configured long leg count"},
    {"name": "bottom_n", "type": "int64", "unit": "configured short leg count"},
    {"name": "average_universe_size", "type": "float64", "unit": "mean daily PIT universe size"},
    {"name": "average_number_of_tradable_symbols", "type": "float64", "unit": "mean eligible ranked symbols on rebalance dates"},
]


def compute_stats(baseline: pd.DataFrame, annualization: float = 365.25) -> dict[str, object]:
    full = _period_stats(baseline, annualization)
    active_mask = baseline["gross_exposure"].astype(float) > 0
    active_baseline = baseline.loc[active_mask].copy()
    active = _period_stats(active_baseline, annualization)

    stats = {
        "ir": full["ir"],
        "sharpe": full["sharpe"],
        "sortino": full["sortino"],
        "max_dd": full["max_dd"],
        "calmar": full["calmar"],
        "turnover_annual": full["turnover_annual"],
        "hit_rate": full["hit_rate"],
        "ir_full": full["ir"],
        "ir_active": active["ir"],
        "sharpe_full": full["sharpe"],
        "sharpe_active": active["sharpe"],
        "sortino_full": full["sortino"],
        "sortino_active": active["sortino"],
        "max_dd_full": full["max_dd"],
        "max_dd_active": active["max_dd"],
        "calmar_full": full["calmar"],
        "calmar_active": active["calmar"],
        "turnover_annual_full": full["turnover_annual"],
        "turnover_annual_active": active["turnover_annual"],
        "hit_rate_full": full["hit_rate"],
        "hit_rate_active": active["hit_rate"],
        "mean_daily_return_full": full["mean_daily_return"],
        "mean_daily_return_active": active["mean_daily_return"],
        "volatility_full": full["volatility"],
        "volatility_active": active["volatility"],
        "full_start_date": _date_or_empty(baseline["date"].min()) if len(baseline) else "",
        "full_end_date": _date_or_empty(baseline["date"].max()) if len(baseline) else "",
        "full_days": int(len(baseline)),
        "active_start_date": _date_or_empty(active_baseline["date"].min()) if len(active_baseline) else "",
        "active_end_date": _date_or_empty(active_baseline["date"].max()) if len(active_baseline) else "",
        "active_days": int(len(active_baseline)),
        "active_fraction": _safe_div(float(len(active_baseline)), float(len(baseline))),
        "gross_exposure_mean_full": full["gross_exposure_mean"],
        "gross_exposure_mean_active": active["gross_exposure_mean"],
        "net_exposure_mean_full": full["net_exposure_mean"],
        "net_exposure_mean_active": active["net_exposure_mean"],
        "methodology": _methodology(annualization),
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
    stats.update(_benchmark_ir_stats(baseline, active_baseline, annualization))
    return _clean(stats)


def _period_stats(baseline: pd.DataFrame, annualization: float) -> dict[str, float]:
    if baseline.empty:
        return {
            "ir": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_dd": 0.0,
            "calmar": 0.0,
            "turnover_annual": 0.0,
            "hit_rate": 0.0,
            "mean_daily_return": 0.0,
            "volatility": 0.0,
            "gross_exposure_mean": 0.0,
            "net_exposure_mean": 0.0,
        }

    returns = baseline["portfolio_return"].astype(float)
    benchmark = baseline["benchmark_return"].astype(float)
    active_returns = returns - benchmark
    equity = (1.0 + returns).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0
    years = max(len(baseline) / annualization, 1.0 / annualization)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if not equity.empty and equity.iloc[-1] > 0 else -1.0

    return {
        "ir": _annual_ratio(active_returns, annualization),
        "sharpe": _annual_ratio(returns, annualization),
        "sortino": _sortino(returns, annualization),
        "max_dd": max_dd,
        "calmar": _safe_div(cagr, abs(max_dd)),
        "turnover_annual": float(baseline["turnover"].astype(float).sum() / years),
        "hit_rate": float((returns > 0).mean()),
        "mean_daily_return": float(returns.mean()),
        "volatility": _annual_volatility(returns, annualization),
        "gross_exposure_mean": float(baseline["gross_exposure"].astype(float).mean()),
        "net_exposure_mean": float(baseline["net_exposure"].astype(float).mean()),
    }


def _annual_ratio(series: pd.Series, annualization: float) -> float:
    series = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return 0.0
    std = float(series.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return 0.0
    return float(series.mean() / std * math.sqrt(annualization))


def _benchmark_ir_stats(
    baseline: pd.DataFrame,
    active_baseline: pd.DataFrame,
    annualization: float,
) -> dict[str, float]:
    specs = {
        "cash": "benchmark_cash_return",
        "btc": "benchmark_btc_return",
        "equal_weight": "benchmark_eqw_return",
    }
    stats: dict[str, float] = {}
    for name, col in specs.items():
        if col not in baseline.columns:
            continue
        stats[f"ir_vs_{name}_full"] = _annual_ratio(
            baseline["portfolio_return"].astype(float) - baseline[col].astype(float),
            annualization,
        )
        stats[f"ir_vs_{name}_active"] = _annual_ratio(
            active_baseline["portfolio_return"].astype(float) - active_baseline[col].astype(float),
            annualization,
        )
    return stats


def _methodology(annualization: float) -> dict[str, object]:
    return {
        "annualization_factor": float(annualization),
        "std_ddof": 1,
        "sortino_formula": "mean(portfolio_return) / std(portfolio_return where < 0, ddof=1) * sqrt(annualization_factor)",
        "active_period_definition": "gross_exposure > 0",
        "ir_formula": "mean(portfolio_return - benchmark_return) / std(portfolio_return - benchmark_return, ddof=1) * sqrt(annualization_factor)",
        "benchmark_primary": "cash",
        "btc_missing_policy": "benchmark_btc_return remains NaN on missing BTC dates; IR versus BTC drops NaN benchmark dates",
        "equal_weight_missing_policy": (
            "symbol-days with missing equal-weight benchmark returns are dropped from that day's basket; "
            "dates with no PIT members or no available returns use 0.0 benchmark_eqw_return"
        ),
    }


def _annual_volatility(series: pd.Series, annualization: float) -> float:
    series = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return 0.0
    std = float(series.std(ddof=1))
    if math.isnan(std):
        return 0.0
    return float(std * math.sqrt(annualization))


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


def _date_or_empty(value) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(val) for key, val in value.items()}
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value)
    return value
