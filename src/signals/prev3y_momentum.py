"""Previous-3-year cross-sectional momentum rankings."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TargetPortfolio:
    decision_date: pd.Timestamp
    signal_cutoff_date: pd.Timestamp
    effective_date: pd.Timestamp
    weights: dict[str, float]
    signal_ranks: dict[str, int]
    eligible_count: int


def rebalance_dates(start_date: str, end_date: str, freq: str) -> list[pd.Timestamp]:
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if freq == "monthly":
        dates = pd.date_range(start, end, freq="ME")
    elif freq == "weekly":
        dates = pd.date_range(start, end, freq="W-SUN")
    else:
        raise ValueError("rebalance_freq must be monthly or weekly")
    return [pd.Timestamp(d).normalize() for d in dates]


def build_prev3y_targets(
    prices: pd.DataFrame,
    membership: pd.DataFrame,
    start_date: str,
    end_date: str,
    lookback_days: int,
    rebalance_freq: str,
    top_n: int,
    bottom_n: int,
    ranking_method: str,
) -> list[TargetPortfolio]:
    close = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    member_by_date = {
        pd.Timestamp(date).normalize(): set(group["symbol"])
        for date, group in membership[membership["is_member"]].groupby("date")
    }

    targets: list[TargetPortfolio] = []
    end_ts = pd.Timestamp(end_date).normalize()
    for decision_date in rebalance_dates(start_date, end_date, rebalance_freq):
        signal_cutoff = decision_date - pd.Timedelta(days=1)
        lookback_start = signal_cutoff - pd.Timedelta(days=int(lookback_days))
        effective_date = decision_date + pd.Timedelta(days=1)
        if effective_date > end_ts:
            continue
        if signal_cutoff not in close.index or lookback_start not in close.index:
            targets.append(TargetPortfolio(decision_date, signal_cutoff, effective_date, {}, {}, 0))
            continue

        members = member_by_date.get(decision_date, set())
        if not members:
            targets.append(TargetPortfolio(decision_date, signal_cutoff, effective_date, {}, {}, 0))
            continue

        scores = _scores(close, members, lookback_start, signal_cutoff, ranking_method)
        if scores.empty:
            targets.append(TargetPortfolio(decision_date, signal_cutoff, effective_date, {}, {}, 0))
            continue

        scores = scores.sort_values(ascending=False)
        ranks = {symbol: rank for rank, symbol in enumerate(scores.index, start=1)}
        long_count, short_count = _side_counts(len(scores), int(top_n), int(bottom_n))
        longs = list(scores.head(long_count).index)
        shorts = list(scores.tail(short_count).index)
        weights: dict[str, float] = {}
        if longs:
            long_weight = 0.5 / len(longs)
            weights.update({symbol: long_weight for symbol in longs})
        if shorts:
            short_weight = -0.5 / len(shorts)
            weights.update({symbol: short_weight for symbol in shorts})
        targets.append(TargetPortfolio(decision_date, signal_cutoff, effective_date, weights, ranks, len(scores)))
    return targets


def _side_counts(eligible_count: int, top_n: int, bottom_n: int) -> tuple[int, int]:
    if eligible_count <= 0:
        return 0, 0
    if top_n > 0 and bottom_n > 0:
        side_count = min(top_n, bottom_n, eligible_count // 2)
        return side_count, side_count
    if top_n > 0:
        return min(top_n, eligible_count), 0
    if bottom_n > 0:
        return 0, min(bottom_n, eligible_count)
    return 0, 0


def _scores(
    close: pd.DataFrame,
    members: set[str],
    lookback_start: pd.Timestamp,
    signal_cutoff: pd.Timestamp,
    ranking_method: str,
) -> pd.Series:
    symbols = [s for s in sorted(members) if s in close.columns]
    if not symbols:
        return pd.Series(dtype="float64")
    start_px = close.loc[lookback_start, symbols]
    end_px = close.loc[signal_cutoff, symbols]
    returns = end_px / start_px - 1.0
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
    returns = returns[returns.index[(start_px.loc[returns.index] > 0) & (end_px.loc[returns.index] > 0)]]
    if ranking_method == "return":
        return returns
    if ranking_method != "risk_adjusted_return":
        raise ValueError("ranking_method must be return or risk_adjusted_return")

    window = close.loc[lookback_start:signal_cutoff, list(returns.index)].pct_change(fill_method=None)
    vol = window.std(skipna=True).replace(0, np.nan)
    score = returns / vol
    return score.replace([np.inf, -np.inf], np.nan).dropna()
