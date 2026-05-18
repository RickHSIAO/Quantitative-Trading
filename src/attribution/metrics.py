from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def safe_div(num: float, den: float) -> float:
    if den == 0.0 or math.isnan(den):
        return 0.0
    return float(num / den)


def signed_side(value: float) -> str:
    if value > 0:
        return "long"
    if value < 0:
        return "short"
    return "flat"


def aggregate_by_symbol(fact: pd.DataFrame, gap_symbols: set[str]) -> pd.DataFrame:
    grouped = fact.groupby("symbol", dropna=False).agg(
        gross_alpha_contribution=("gross_contribution", "sum"),
        net_alpha_contribution=("net_contribution", "sum"),
        fee_cost_total=("fee_cost", "sum"),
        slippage_cost_total=("slippage_cost", "sum"),
        funding_cost_total=("funding_cost", "sum"),
        outlier_funding_cost_total=("outlier_funding_cost", "sum"),
        holding_days=("has_prior_position", "sum"),
        long_days=("is_long_day", "sum"),
        short_days=("is_short_day", "sum"),
        funding_gap_days=("funding_gap", "sum"),
        funding_settlement_count=("funding_settlement_count", "sum"),
        trade_turnover=("trade_turnover", "sum"),
    ).reset_index()
    grouped["total_cost"] = (
        grouped["fee_cost_total"] + grouped["slippage_cost_total"] + grouped["funding_cost_total"]
    )
    grouped["side_primary"] = np.where(
        grouped["long_days"].gt(grouped["short_days"]),
        "long",
        np.where(grouped["short_days"].gt(grouped["long_days"]), "short", "mixed"),
    )
    grouped["gross_alpha_rank"] = grouped["gross_alpha_contribution"].rank(
        ascending=False, method="min"
    ).astype(int)
    grouped["net_alpha_rank"] = grouped["net_alpha_contribution"].rank(
        ascending=False, method="min"
    ).astype(int)
    grouped["rank_change"] = grouped["net_alpha_rank"] - grouped["gross_alpha_rank"]
    grouped["is_funding_gap"] = grouped["symbol"].isin(gap_symbols)
    interval = fact.groupby("symbol")["funding_interval_group"].agg(_mode_or_unknown).reset_index()
    grouped = grouped.merge(interval, on="symbol", how="left")
    return grouped.sort_values("net_alpha_contribution", ascending=False).reset_index(drop=True)


def aggregate_period(fact: pd.DataFrame, period: str) -> pd.DataFrame:
    frame = fact.copy()
    if period == "year":
        frame["period"] = pd.to_datetime(frame["date"]).dt.year.astype(int).astype(str)
    elif period == "month":
        frame["period"] = pd.to_datetime(frame["date"]).dt.to_period("M").astype(str)
    else:
        raise ValueError(f"unsupported period={period}")
    grouped = _aggregate_group(frame, "period").rename(columns={"period": period})
    return grouped.sort_values(period).reset_index(drop=True)


def aggregate_by_side(fact: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_group(fact, "side")


def aggregate_by_funding_gap(fact: pd.DataFrame) -> pd.DataFrame:
    frame = fact.copy()
    frame["funding_gap_group"] = np.where(frame["is_funding_gap_symbol"], "funding_gap_7", "non_gap")
    return _aggregate_group(frame, "funding_gap_group")


def aggregate_by_interval(fact: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_group(fact, "funding_interval_group")


def aggregate_cost_type(fact: pd.DataFrame) -> pd.DataFrame:
    totals = {
        "fee": float(fact["fee_cost"].sum()),
        "slippage": float(fact["slippage_cost"].sum()),
        "funding": float(fact["funding_cost"].sum()),
    }
    total_cost = sum(totals.values())
    gross_total = float(fact["gross_contribution"].sum())
    rows = []
    for name, value in totals.items():
        rows.append({
            "cost_type": name,
            "total_cost": value,
            "pct_of_total_cost": safe_div(value, total_cost),
            "pct_of_gross_alpha": safe_div(value, gross_total),
        })
    return pd.DataFrame(rows)


def top_contributors(by_symbol: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    frame = by_symbol.copy()
    frame["abs_net_alpha_contribution"] = frame["net_alpha_contribution"].abs()
    frame["contribution_direction"] = np.where(frame["net_alpha_contribution"].ge(0), "positive", "negative")
    return (
        frame.sort_values("abs_net_alpha_contribution", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def drawdown_contributors(baseline: pd.DataFrame, fact: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    active = baseline[baseline["gross_exposure"].astype(float).gt(0)].copy()
    active["date"] = pd.to_datetime(active["date"]).dt.normalize()
    returns = active["portfolio_return"].astype(float).fillna(0.0)
    equity = (1.0 + returns).cumprod()
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    trough_idx = drawdown.idxmin()
    trough_date = pd.Timestamp(active.loc[trough_idx, "date"]).normalize()
    peak_slice = equity.loc[:trough_idx]
    peak_idx = peak_slice.idxmax()
    peak_date = pd.Timestamp(active.loc[peak_idx, "date"]).normalize()
    window = fact[fact["date"].between(peak_date, trough_date)].copy()
    grouped = aggregate_by_symbol(window, set())
    grouped = grouped.loc[
        :,
        [
            "symbol",
            "side_primary",
            "gross_alpha_contribution",
            "net_alpha_contribution",
            "fee_cost_total",
            "slippage_cost_total",
            "funding_cost_total",
            "total_cost",
            "funding_interval_group",
        ],
    ]
    grouped["drawdown_start"] = peak_date.strftime("%Y-%m-%d")
    grouped["drawdown_trough"] = trough_date.strftime("%Y-%m-%d")
    grouped["max_drawdown"] = float(drawdown.loc[trough_idx])
    grouped["abs_net_alpha_contribution"] = grouped["net_alpha_contribution"].abs()
    grouped = grouped.sort_values("abs_net_alpha_contribution", ascending=False).reset_index(drop=True)
    grouped["drawdown_contribution_rank"] = grouped.index + 1
    metadata = {
        "drawdown_start": peak_date.strftime("%Y-%m-%d"),
        "drawdown_trough": trough_date.strftime("%Y-%m-%d"),
        "max_drawdown": float(drawdown.loc[trough_idx]),
    }
    return grouped, metadata


def warning_gates(
    by_symbol: pd.DataFrame,
    by_year: pd.DataFrame,
    by_side: pd.DataFrame,
    by_gap: pd.DataFrame,
    thresholds: dict[str, float],
) -> dict[str, dict[str, Any]]:
    positive_total = float(by_symbol.loc[by_symbol["net_alpha_contribution"].gt(0), "net_alpha_contribution"].sum())
    top5 = float(
        by_symbol[by_symbol["net_alpha_contribution"].gt(0)]
        .sort_values("net_alpha_contribution", ascending=False)
        .head(5)["net_alpha_contribution"]
        .sum()
    )
    top_symbol = by_symbol.sort_values("net_alpha_contribution", ascending=False).head(1)
    top_symbol_value = float(top_symbol["net_alpha_contribution"].iloc[0]) if not top_symbol.empty else 0.0
    top_symbol_name = str(top_symbol["symbol"].iloc[0]) if not top_symbol.empty else ""
    gap_row = by_gap[by_gap["funding_gap_group"].eq("funding_gap_7")]
    gap_positive = float(max(gap_row["net_alpha_contribution"].sum(), 0.0)) if not gap_row.empty else 0.0
    year_positive_total = float(by_year.loc[by_year["net_alpha_contribution"].gt(0), "net_alpha_contribution"].sum())
    year_top = by_year.sort_values("net_alpha_contribution", ascending=False).head(1)
    year_value = float(year_top["net_alpha_contribution"].iloc[0]) if not year_top.empty else 0.0
    year_name = str(year_top["year"].iloc[0]) if not year_top.empty else ""
    short_row = by_side[by_side["side"].eq("short")]
    short_net = float(short_row["net_alpha_contribution"].sum()) if not short_row.empty else 0.0
    gross_combined = float(by_side["gross_alpha_contribution"].sum())
    max_rank_change = int(by_symbol["rank_change"].abs().max()) if not by_symbol.empty else 0

    top5_ratio = safe_div(top5, positive_total)
    single_ratio = safe_div(max(top_symbol_value, 0.0), positive_total)
    gap_ratio = safe_div(gap_positive, positive_total)
    year_ratio = safe_div(max(year_value, 0.0), year_positive_total)
    short_ratio = safe_div(abs(short_net), abs(gross_combined))

    return {
        "top5_symbol_concentration": {
            "triggered": bool(top5_ratio > thresholds["top5_symbol_concentration"]),
            "value": top5_ratio,
            "threshold": thresholds["top5_symbol_concentration"],
        },
        "single_symbol_concentration": {
            "triggered": bool(single_ratio > thresholds["single_symbol_concentration"]),
            "worst_symbol": top_symbol_name,
            "value": single_ratio,
            "threshold": thresholds["single_symbol_concentration"],
        },
        "funding_gap_concentration": {
            "triggered": bool(gap_ratio > thresholds["funding_gap_concentration"]),
            "value": gap_ratio,
            "threshold": thresholds["funding_gap_concentration"],
        },
        "single_year_concentration": {
            "triggered": bool(year_ratio > thresholds["single_year_concentration"]),
            "worst_year": year_name,
            "value": year_ratio,
            "threshold": thresholds["single_year_concentration"],
        },
        "short_side_drag": {
            "triggered": bool(short_net < 0 and short_ratio > thresholds["short_side_drag_pct_gross"]),
            "short_net_alpha": short_net,
            "value": short_ratio,
            "threshold_pct": thresholds["short_side_drag_pct_gross"],
        },
        "gross_net_rank_divergence": {
            "triggered": bool(max_rank_change > thresholds["gross_net_rank_divergence"]),
            "max_rank_change": max_rank_change,
            "threshold": int(thresholds["gross_net_rank_divergence"]),
        },
    }


def fail_gates(
    gross_max_diff: float,
    net_max_diff: float,
    tolerance: float,
    missing_outputs: list[str] | None = None,
    schema_errors: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    missing_outputs = missing_outputs or []
    schema_errors = schema_errors or []
    return {
        "symbol_pnl_sum_mismatch": {
            "triggered": bool(gross_max_diff > tolerance),
            "value": gross_max_diff,
            "threshold": tolerance,
        },
        "net_pnl_sum_mismatch": {
            "triggered": bool(net_max_diff > tolerance),
            "value": net_max_diff,
            "threshold": tolerance,
        },
        "missing_output_files": {
            "triggered": bool(missing_outputs),
            "missing": missing_outputs,
        },
        "schema_mismatch": {
            "triggered": bool(schema_errors),
            "errors": schema_errors,
        },
    }


def _aggregate_group(fact: pd.DataFrame, group_col: str) -> pd.DataFrame:
    grouped = fact.groupby(group_col, dropna=False).agg(
        gross_alpha_contribution=("gross_contribution", "sum"),
        net_alpha_contribution=("net_contribution", "sum"),
        fee_cost_total=("fee_cost", "sum"),
        slippage_cost_total=("slippage_cost", "sum"),
        funding_cost_total=("funding_cost", "sum"),
        total_days=("date", "nunique"),
        holding_days=("has_prior_position", "sum"),
        symbol_count=("symbol", "nunique"),
        trade_turnover=("trade_turnover", "sum"),
    ).reset_index()
    grouped["total_cost"] = (
        grouped["fee_cost_total"] + grouped["slippage_cost_total"] + grouped["funding_cost_total"]
    )
    return grouped.sort_values("net_alpha_contribution", ascending=False).reset_index(drop=True)


def _mode_or_unknown(values: pd.Series) -> str:
    clean = values.dropna().astype(str)
    if clean.empty:
        return "unknown"
    return str(clean.value_counts().sort_index().idxmax())
