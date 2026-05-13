"""Vectorized long/short daily backtest engine.

The engine consumes target weights and daily prices. It does not know how the
universe or signals were built.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.signals.prev3y_momentum import TargetPortfolio


BASELINE_SCHEMA = [
    {"name": "date", "type": "datetime64[ns]", "unit": "UTC calendar date"},
    {"name": "portfolio_return", "type": "float64", "unit": "decimal daily return"},
    {"name": "benchmark_return", "type": "float64", "unit": "decimal daily return"},
    {"name": "gross_exposure", "type": "float64", "unit": "sum(abs(weights))"},
    {"name": "net_exposure", "type": "float64", "unit": "sum(weights)"},
    {"name": "turnover", "type": "float64", "unit": "sum(abs(delta weight)) on effective date"},
    {"name": "n_longs", "type": "int64", "unit": "active long positions"},
    {"name": "n_shorts", "type": "int64", "unit": "active short positions"},
]

POSITIONS_SCHEMA = [
    {"name": "date", "type": "datetime64[ns]", "unit": "UTC calendar date"},
    {"name": "symbol", "type": "string", "unit": "Bybit perpetual symbol"},
    {"name": "weight", "type": "float64", "unit": "portfolio weight"},
    {"name": "signal_rank", "type": "int64", "unit": "1 is strongest momentum"},
]


@dataclass(frozen=True)
class BacktestResult:
    baseline: pd.DataFrame
    positions: pd.DataFrame
    return_anomalies: list[dict[str, object]]


def run_daily_long_short_backtest(
    prices: pd.DataFrame,
    membership: pd.DataFrame,
    targets: list[TargetPortfolio],
    start_date: str,
    end_date: str,
    entry_price: str,
) -> BacktestResult:
    price_col = _price_column(entry_price)
    px = prices.pivot(index="date", columns="symbol", values=price_col).sort_index()
    daily_returns = px.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    dates = pd.date_range(start_date, end_date, freq="D")
    member_by_date = {
        pd.Timestamp(date).normalize(): set(group["symbol"])
        for date, group in membership[membership["is_member"]].groupby("date")
    }
    targets_by_effective = {target.effective_date.normalize(): target for target in targets}

    current_weights: dict[str, float] = {}
    current_ranks: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []
    anomalies: list[dict[str, object]] = []

    for date in dates:
        returns = daily_returns.loc[date] if date in daily_returns.index else pd.Series(dtype="float64")
        portfolio_return, missing_symbols = _weighted_return(current_weights, returns)
        if missing_symbols:
            anomalies.append({
                "symbol": ",".join(missing_symbols[:10]),
                "start_date": str(date.date()),
                "end_date": str(date.date()),
                "issue": f"missing_position_return_symbols={len(missing_symbols)}",
            })

        benchmark_return = _benchmark_return(member_by_date.get(date - pd.Timedelta(days=1), set()), returns)
        turnover = 0.0
        target = targets_by_effective.get(date)
        if target is not None:
            turnover = _turnover(current_weights, target.weights)
            current_weights = dict(target.weights)
            current_ranks = dict(target.signal_ranks)

        gross = float(sum(abs(v) for v in current_weights.values()))
        net = float(sum(current_weights.values()))
        n_longs = int(sum(1 for v in current_weights.values() if v > 0))
        n_shorts = int(sum(1 for v in current_weights.values() if v < 0))
        rows.append({
            "date": date,
            "portfolio_return": float(portfolio_return),
            "benchmark_return": float(benchmark_return),
            "gross_exposure": gross,
            "net_exposure": net,
            "turnover": float(turnover),
            "n_longs": n_longs,
            "n_shorts": n_shorts,
        })
        for symbol, weight in sorted(current_weights.items()):
            position_rows.append({
                "date": date,
                "symbol": symbol,
                "weight": float(weight),
                "signal_rank": int(current_ranks.get(symbol, 0)),
            })

    baseline = pd.DataFrame(rows, columns=[col["name"] for col in BASELINE_SCHEMA])
    positions = pd.DataFrame(position_rows, columns=[col["name"] for col in POSITIONS_SCHEMA])
    if not positions.empty:
        positions["signal_rank"] = positions["signal_rank"].astype("int64")
    return BacktestResult(baseline=baseline, positions=positions, return_anomalies=anomalies)


def _price_column(entry_price: str) -> str:
    if entry_price == "t1_open":
        return "open"
    if entry_price == "t1_close":
        return "close"
    raise ValueError("entry_price must be t1_open or t1_close")


def _weighted_return(weights: dict[str, float], returns: pd.Series) -> tuple[float, list[str]]:
    if not weights:
        return 0.0, []
    total = 0.0
    missing: list[str] = []
    for symbol, weight in weights.items():
        value = returns.get(symbol, np.nan)
        if pd.isna(value):
            missing.append(symbol)
            continue
        total += float(weight) * float(value)
    return total, missing


def _benchmark_return(members: set[str], returns: pd.Series) -> float:
    if not members:
        return 0.0
    available = returns.reindex(sorted(members)).dropna()
    if available.empty:
        return 0.0
    return float(available.mean())


def _turnover(current: dict[str, float], target: dict[str, float]) -> float:
    symbols = set(current) | set(target)
    return float(sum(abs(target.get(symbol, 0.0) - current.get(symbol, 0.0)) for symbol in symbols))
