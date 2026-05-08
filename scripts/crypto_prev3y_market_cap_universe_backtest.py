"""Backtest Crypto by previous-3-year average CMC Top-N universe.

Example:
  2021 backtest uses 2018-2020 average market cap or volume top 100.
  2022 backtest uses 2019-2021 average market cap or volume top 100.

This script only changes universe construction. Strategy signals, parameters,
costs, and position sizing are left untouched.
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


BASELINE_COST_OVERRIDES = {
    "BACKTEST_TP_AS_TAKER": False,
    "BACKTEST_SLIPPAGE_ON_TP": False,
    "BACKTEST_FUNDING_DAILY_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_INTRABAR_CONFLICT_MODE": "tp_first",
}


def _deepcopy_attr(name: str) -> Any:
    return copy.deepcopy(getattr(config, name))


def _apply_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    saved = {name: _deepcopy_attr(name) for name in overrides if hasattr(config, name)}
    for name, value in overrides.items():
        if not hasattr(config, name):
            raise AttributeError(f"Unknown config override: {name}")
        setattr(config, name, copy.deepcopy(value))
    return saved


def _restore_overrides(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(config, name, value)


def _to_bybit_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    if s.startswith("BYBIT:") and s.endswith(".P"):
        return s
    if s.endswith("USDT"):
        return f"BYBIT:{s}.P"
    return f"BYBIT:{s}USDT.P"


def _has_rankings_table() -> bool:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crypto_market_cap_rankings'"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


RANK_BY_COLUMNS = {
    "market_cap": "market_cap",
    "volume_24h": "volume_24h",
}


def _prev3y_universe(year: int, top_n: int, rank_by: str = "market_cap") -> pd.DataFrame:
    if not _has_rankings_table():
        return pd.DataFrame()
    if rank_by not in RANK_BY_COLUMNS:
        raise ValueError(f"rank_by must be one of: {', '.join(RANK_BY_COLUMNS)}")
    rank_col = RANK_BY_COLUMNS[rank_by]
    start = f"{year - 3}-01-01"
    end = f"{year - 1}-12-31"
    conn = sqlite3.connect(config.DB_PATH)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT
                symbol,
                MAX(name) AS name,
                AVG({rank_col}) AS avg_rank_value,
                AVG(market_cap) AS avg_market_cap,
                AVG(volume_24h) AS avg_volume_24h,
                AVG(rank) AS avg_cmc_rank,
                COUNT(*) AS snapshots
            FROM crypto_market_cap_rankings
            WHERE snapshot_date BETWEEN ? AND ?
              AND {rank_col} IS NOT NULL
              AND COALESCE(is_stablecoin, 0) = 0
              AND COALESCE(is_wrapped, 0) = 0
              AND COALESCE(is_leveraged, 0) = 0
            GROUP BY symbol
            ORDER BY avg_rank_value DESC
            LIMIT ?
            """,
            conn,
            params=(start, end, int(top_n)),
        )
    finally:
        conn.close()
    if df.empty:
        return df
    df["bybit_symbol"] = df["symbol"].map(_to_bybit_symbol)
    df.insert(0, "test_year", year)
    df.insert(1, "lookback_start", start)
    df.insert(2, "lookback_end", end)
    df.insert(3, "universe_rank", range(1, len(df) + 1))
    df.insert(4, "rank_by", rank_by)
    return df


def _has_enough_data(sym: str, start: pd.Timestamp, min_history_days: int) -> tuple[bool, str, pd.DataFrame | None]:
    try:
        df = load_prices(sym)
    except Exception as exc:
        return False, f"load_prices_failed:{exc}", None
    if df is None or df.empty:
        return False, "missing_local_ohlcv", None
    hist = df.loc[df.index < start]
    if len(hist) < min_history_days:
        return False, "ohlcv_lt_required_history", df
    return True, "ok", df


def _build_inputs(symbols: list[str]) -> tuple[dict, dict, dict]:
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map: dict[str, str] = {}
    for sym in symbols:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=True)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs
        type_map[sym] = "Crypto"
    return data, signals, type_map


def _slice_inputs(base: tuple[dict, dict, dict],
                  start: str,
                  end: str,
                  tradable_symbols: set[str]) -> tuple[dict, dict, dict]:
    base_data, base_signals, base_type_map = base
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map = dict(base_type_map)
    for sym, df in base_data.items():
        mask = (df.index >= start_ts) & (df.index <= end_ts)
        if not mask.any():
            continue
        data[sym] = df.loc[mask].copy()
        signals[sym] = {
            key: series.loc[mask].copy()
            for key, series in base_signals[sym].items()
        }
    apply_cross_asset_filters(data, signals, type_map)
    for sym, sigs in signals.items():
        if sym in tradable_symbols:
            continue
        for key in ("trend", "vp", "bb", "combined", "score", "ema_bull", "ema_bear"):
            if key in sigs:
                sigs[key].loc[:] = 0
    return data, signals, type_map


def _run_year(tradable_symbols: list[str],
              context_symbols: list[str],
              start: str,
              end: str) -> tuple[list[Any], dict[str, Any]]:
    all_symbols = sorted(set(tradable_symbols) | set(context_symbols))
    base = _build_inputs(all_symbols)
    data, signals, type_map = _slice_inputs(base, start, end, set(tradable_symbols))
    if not data:
        return [], {}
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    saved = _apply_overrides(BASELINE_COST_OVERRIDES)
    try:
        trades, results = run_silo_backtest(
            data,
            signals,
            type_map,
            {"Crypto": ["Crypto"]},
            config.SILO_CAPITAL,
            {"Crypto": profile},
        )
    finally:
        _restore_overrides(saved)
    return list(trades), dict(results.get("Crypto", {}).get("metrics", {}))


def _contributors(trades: list[Any], n: int = 10) -> tuple[str, str, int]:
    closed = [t for t in trades if getattr(t, "pnl", None) is not None]
    if not closed:
        return "", "", 0
    df = pd.DataFrame([{
        "symbol": t.symbol,
        "pnl": float(t.pnl or 0.0),
        "r": float(t.r_multiple or 0.0),
    } for t in closed])
    grouped = df.groupby("symbol", as_index=False).agg(total_pnl=("pnl", "sum"), total_R=("r", "sum"))
    top = grouped.sort_values("total_pnl", ascending=False).head(n)
    worst = grouped.sort_values("total_pnl", ascending=True).head(n)
    return (
        ";".join(f"{r.symbol}:{r.total_pnl:.2f}" for r in top.itertuples()),
        ";".join(f"{r.symbol}:{r.total_pnl:.2f}" for r in worst.itertuples()),
        int(grouped["symbol"].nunique()),
    )


def _row(year: int,
         universe_df: pd.DataFrame,
         eligible_symbols: list[str],
         rejected: list[dict[str, Any]],
         trades: list[Any],
         metrics: dict[str, Any]) -> dict[str, Any]:
    top, worst, traded_symbols = _contributors(trades)
    return {
        "test_year": year,
        "rank_by": universe_df["rank_by"].iloc[0] if "rank_by" in universe_df and not universe_df.empty else "",
        "lookback_years": f"{year - 3}-{year - 1}",
        "status": "ok" if metrics else "no_backtest_result",
        "total_return": metrics.get("total_return_pct", ""),
        "annual_return": metrics.get("annual_return_pct", ""),
        "MDD": metrics.get("max_drawdown_pct", ""),
        "PF": metrics.get("profit_factor", ""),
        "Sharpe": metrics.get("sharpe_ratio", ""),
        "Calmar": metrics.get("calmar_ratio", ""),
        "win_rate": (metrics.get("win_rate", "") * 100.0 if metrics.get("win_rate", "") != "" else ""),
        "avg_R": metrics.get("avg_r_multiple", ""),
        "trades": metrics.get("total_trades", ""),
        "cmc_universe_symbols": len(universe_df),
        "eligible_local_ohlcv_symbols": len(eligible_symbols),
        "rejected_symbols": len(rejected),
        "number_of_symbols_traded": traded_symbols,
        "top_contributors": top,
        "worst_contributors": worst,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest yearly PIT universe from previous-3-year average CMC metric.")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--end-date", default="2026-05-07")
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--rank-by", choices=sorted(RANK_BY_COLUMNS), default="market_cap")
    parser.add_argument("--min-history-days", type=int, default=210)
    parser.add_argument("--output", default="output/crypto_prev3y_mcap_top100_yearly.csv")
    parser.add_argument("--universe-output", default="output/crypto_prev3y_mcap_top100_universe.csv")
    args = parser.parse_args()
    if args.rank_by == "volume_24h":
        if args.output == parser.get_default("output"):
            args.output = "output/crypto_prev3y_volume_top100_yearly.csv"
        if args.universe_output == parser.get_default("universe_output"):
            args.universe_output = "output/crypto_prev3y_volume_top100_universe.csv"

    available = set(get_all_symbols())
    rows: list[dict[str, Any]] = []
    universe_rows: list[dict[str, Any]] = []
    for year in range(args.start_year, args.end_year + 1):
        start = f"{year}-01-01"
        end = args.end_date if year == pd.Timestamp(args.end_date).year else f"{year}-12-31"
        if pd.Timestamp(start) > pd.Timestamp(args.end_date):
            break
        universe = _prev3y_universe(year, args.top_n, args.rank_by)
        eligible: list[str] = []
        rejected: list[dict[str, Any]] = []
        for rec in universe.to_dict("records"):
            sym = rec["bybit_symbol"]
            ok = False
            reason = ""
            if sym not in available:
                reason = "missing_local_ohlcv"
            else:
                ok, reason, _ = _has_enough_data(sym, pd.Timestamp(start), args.min_history_days)
            rec["test_start"] = start
            rec["test_end"] = end
            rec["eligible_for_backtest"] = int(ok)
            rec["eligibility_reason"] = reason
            universe_rows.append(rec)
            if ok:
                eligible.append(sym)
            else:
                rejected.append({"symbol": sym, "reason": reason})

        # BTC is required for the cross-asset moat. Include it only as filtering
        # context if it is not tradable by the PIT universe/eligibility rules.
        btc = getattr(config, "CRYPTO_MARKET_SYMBOL", "BYBIT:BTCUSDT.P")
        context = [btc] if btc in available else []

        trades, metrics = _run_year(eligible, context, start, end)
        rows.append(_row(year, universe, eligible, rejected, trades, metrics))
        print(
            f"{year} lookback={year-3}-{year-1} "
            f"rank_by={args.rank_by} "
            f"cmc={len(universe)} eligible={len(eligible)} "
            f"return={metrics.get('total_return_pct', '')} "
            f"PF={metrics.get('profit_factor', '')} trades={metrics.get('total_trades', '')}"
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    uni_out = Path(args.universe_output)
    uni_out.parent.mkdir(parents=True, exist_ok=True)
    if universe_rows:
        with uni_out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(universe_rows[0].keys()))
            writer.writeheader()
            writer.writerows(universe_rows)

    print(f"\nSaved: {out}")
    print(f"Saved: {uni_out}")


if __name__ == "__main__":
    main()
