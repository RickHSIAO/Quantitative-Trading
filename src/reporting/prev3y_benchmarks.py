"""Benchmark return helpers for Prev3Y crypto baseline reporting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


BENCHMARK_COLUMNS_SCHEMA = [
    {"name": "benchmark_cash_return", "type": "float64", "unit": "decimal daily return; always 0"},
    {"name": "benchmark_btc_return", "type": "float64", "unit": "decimal daily BTC perp return; NaN when unavailable"},
    {"name": "benchmark_eqw_return", "type": "float64", "unit": "decimal daily PIT universe equal-weight return"},
]


@dataclass(frozen=True)
class BenchmarkResult:
    baseline: pd.DataFrame
    metadata: dict[str, object]


def apply_benchmarks(
    baseline: pd.DataFrame,
    prices: pd.DataFrame,
    membership: pd.DataFrame,
    start_date: str,
    end_date: str,
    entry_price: str,
    benchmark_config: dict[str, Any],
) -> BenchmarkResult:
    """Add reporting benchmarks without changing portfolio returns or positions."""
    primary = str(benchmark_config.get("primary", "cash"))
    btc_symbol = str(benchmark_config.get("btc_symbol", "BYBIT:BTCUSDT.P"))
    if primary not in {"cash", "btc_perp", "equal_weight_long_only"}:
        raise ValueError("benchmark.primary must be cash, btc_perp, or equal_weight_long_only")

    enriched = baseline.copy()
    dates = pd.DatetimeIndex(pd.to_datetime(enriched["date"]).dt.normalize())
    price_col = _price_column(entry_price)
    returns = prices.pivot(index="date", columns="symbol", values=price_col).sort_index()
    returns = returns.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    eqw_return, eqw_counts = _equal_weight_returns(membership, returns, dates)
    btc_return = _btc_returns(prices, dates, price_col, btc_symbol)

    enriched["benchmark_cash_return"] = 0.0
    enriched["benchmark_btc_return"] = btc_return.to_numpy()
    enriched["benchmark_eqw_return"] = eqw_return.to_numpy()
    enriched["benchmark_return"] = _primary_return(enriched, primary)
    enriched = enriched[[
        "date",
        "portfolio_return",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
        "gross_exposure",
        "net_exposure",
        "turnover",
        "n_longs",
        "n_shorts",
    ]]

    active_mask = enriched["gross_exposure"].astype(float) > 0
    btc_missing_full = int(enriched["benchmark_btc_return"].isna().sum())
    btc_missing_active = int(enriched.loc[active_mask, "benchmark_btc_return"].isna().sum())
    btc_effective_full = int(enriched["benchmark_btc_return"].notna().sum())
    btc_effective_active = int(enriched.loc[active_mask, "benchmark_btc_return"].notna().sum())
    eqw_effective_full = int(eqw_counts.gt(0).sum()) if len(eqw_counts) else 0
    eqw_effective_active = int(eqw_counts.loc[active_mask.to_numpy()].gt(0).sum()) if len(eqw_counts) else 0
    if btc_missing_active:
        raise RuntimeError(
            "NEED_CLARIFICATION: BTC benchmark has missing returns inside the active period; "
            "do not fill with zero."
        )

    btc_prices = prices[prices["symbol"].eq(btc_symbol)].copy()
    metadata = {
        "benchmark_primary": primary,
        "benchmark_btc_symbol": btc_symbol,
        "benchmark_return_definition": _primary_definition(primary),
        "benchmark_cash_definition": "cash benchmark; daily return is 0.0",
        "benchmark_btc_definition": f"{btc_symbol} {price_col}-to-{price_col} return; missing dates remain NaN",
        "benchmark_equal_weight_definition": (
            "same-day PIT universe equal-weight long-only benchmark; "
            "symbol-days with missing returns are dropped"
        ),
        "benchmark_return_equals": _primary_column(primary),
        "benchmark_btc_start_date": _date_or_empty(btc_prices["date"].min()) if not btc_prices.empty else "",
        "benchmark_btc_end_date": _date_or_empty(btc_prices["date"].max()) if not btc_prices.empty else "",
        "benchmark_btc_missing_days_full": btc_missing_full,
        "benchmark_btc_missing_days_active": btc_missing_active,
        "ir_vs_btc_full_effective_days": btc_effective_full,
        "ir_vs_btc_active_effective_days": btc_effective_active,
        "benchmark_eqw_effective_days_full": eqw_effective_full,
        "benchmark_eqw_effective_days_active": eqw_effective_active,
        "eqw_benchmark_avg_symbols": float(eqw_counts.mean()) if len(eqw_counts) else 0.0,
        "eqw_benchmark_min_symbols": int(eqw_counts.min()) if len(eqw_counts) else 0,
        "eqw_benchmark_missing_days": int(eqw_counts.eq(0).sum()) if len(eqw_counts) else 0,
    }
    return BenchmarkResult(baseline=enriched, metadata=metadata)


def _equal_weight_returns(
    membership: pd.DataFrame,
    returns: pd.DataFrame,
    dates: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series]:
    member_by_date = {
        pd.Timestamp(date).normalize(): set(group["symbol"])
        for date, group in membership[membership["is_member"]].groupby("date")
    }
    values: list[float] = []
    counts: list[int] = []
    for date in dates:
        members = member_by_date.get(pd.Timestamp(date).normalize(), set())
        if not members or date not in returns.index:
            values.append(0.0)
            counts.append(0)
            continue
        available = returns.loc[date].reindex(sorted(members)).dropna()
        values.append(float(available.mean()) if not available.empty else 0.0)
        counts.append(int(len(available)))
    return pd.Series(values, index=dates), pd.Series(counts, index=dates)


def _btc_returns(
    prices: pd.DataFrame,
    dates: pd.DatetimeIndex,
    price_col: str,
    btc_symbol: str,
) -> pd.Series:
    btc = prices[prices["symbol"].eq(btc_symbol)].copy()
    if btc.empty:
        raise RuntimeError(f"NEED_CLARIFICATION: BTC benchmark symbol not found: {btc_symbol}")
    btc_px = btc.set_index("date")[price_col].sort_index()
    btc_return = btc_px.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return btc_return.reindex(dates)


def _price_column(entry_price: str) -> str:
    if entry_price == "t1_open":
        return "open"
    if entry_price == "t1_close":
        return "close"
    raise ValueError("entry_price must be t1_open or t1_close")


def _primary_return(baseline: pd.DataFrame, primary: str) -> pd.Series:
    return baseline[_primary_column(primary)]


def _primary_column(primary: str) -> str:
    if primary == "cash":
        return "benchmark_cash_return"
    if primary == "btc_perp":
        return "benchmark_btc_return"
    if primary == "equal_weight_long_only":
        return "benchmark_eqw_return"
    raise ValueError(f"unsupported benchmark primary: {primary}")


def _primary_definition(primary: str) -> str:
    if primary == "cash":
        return "benchmark_return = benchmark_cash_return"
    if primary == "btc_perp":
        return "benchmark_return = benchmark_btc_return"
    if primary == "equal_weight_long_only":
        return "benchmark_return = benchmark_eqw_return"
    raise ValueError(f"unsupported benchmark primary: {primary}")


def _date_or_empty(value) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")
