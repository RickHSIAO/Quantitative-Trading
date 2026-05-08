"""Crypto intrabar TP/SL path stress test.

Runs the current Crypto strategy with identical signals, costs, sizing, and
asset universe while changing only same-bar TP/SL conflict resolution.
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config import get_selected_assets
from scripts import crypto_prev3y_top100_optimize as opt
from scripts import crypto_top100_overfit_checks as checks
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


DEFAULT_START = "2024-05-01"
DEFAULT_END = "2026-05-07"


@dataclass(frozen=True)
class Variant:
    label: str
    mode: str
    description: str


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


def _build_inputs(use_vp: bool = True) -> tuple[dict, dict, dict]:
    assets = get_selected_assets(42)
    available = set(get_all_symbols())
    cryptos = [sym for sym in assets["cryptos"] if sym in available]
    type_map = {sym: "Crypto" for sym in cryptos}
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}

    for sym in cryptos:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=use_vp)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs

    if not data:
        raise RuntimeError("No Crypto data available. Run `python main.py update` first.")
    return data, signals, type_map


def _slice_inputs(base: tuple[dict, dict, dict],
                  start: str | None,
                  end: str | None) -> tuple[dict, dict, dict]:
    base_data, base_signals, base_type_map = base
    start_ts = pd.Timestamp(start) if start else None
    end_ts = pd.Timestamp(end) if end else None
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map = dict(base_type_map)

    for sym, df in base_data.items():
        mask = pd.Series(True, index=df.index)
        if start_ts is not None:
            mask &= df.index >= start_ts
        if end_ts is not None:
            mask &= df.index <= end_ts

        sliced = df.loc[mask].copy()
        if sliced.empty:
            continue
        data[sym] = sliced
        signals[sym] = {
            key: series.loc[mask].copy()
            for key, series in base_signals[sym].items()
        }

    apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def _run_crypto(base: tuple[dict, dict, dict],
                start: str | None,
                end: str | None) -> tuple[list, dict[str, Any], dict[str, pd.DataFrame]]:
    data, signals, type_map = _slice_inputs(base, start, end)
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    _, results = run_silo_backtest(
        data,
        signals,
        type_map,
        {"Crypto": ["Crypto"]},
        config.SILO_CAPITAL,
        {"Crypto": profile},
    )
    return (
        list(results["Crypto"]["trades"]),
        dict(results["Crypto"]["metrics"]),
        data,
    )


def _candidate_cache(start: str,
                     end: str,
                     top_n: int,
                     lookback_years: int) -> dict[str, Any]:
    universe = checks.UniverseKey(
        "volume_24h",
        int(top_n),
        lookback_years=int(lookback_years),
        min_history_days=180,
    )
    return checks._prepare_universe_cache(start, end, universe)


def _run_candidate(cache: dict[str, Any],
                   start: str,
                   end: str) -> tuple[list, dict[str, Any], dict[str, pd.DataFrame]]:
    data, signals, type_map = opt._slice_inputs(
        cache["base"],
        start,
        end,
        cache["allowed_by_year"],
    )
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    trades, results = run_silo_backtest(
        data,
        signals,
        type_map,
        {"Crypto": ["Crypto"]},
        config.SILO_CAPITAL,
        {"Crypto": profile},
    )
    return (
        list(trades),
        dict(results["Crypto"]["metrics"]),
        data,
    )


def _conflict_stats(trades: list, data: dict[str, pd.DataFrame]) -> dict[str, Any]:
    conflicts = 0
    conflict_pnl = 0.0
    for trade in trades:
        if not getattr(trade, "exit_date", None):
            continue
        df = data.get(trade.symbol)
        if df is None:
            continue
        dt = pd.Timestamp(trade.exit_date)
        if dt not in df.index:
            continue
        row = df.loc[dt]
        hi = float(row["High"])
        lo = float(row["Low"])
        if trade.direction == 1:
            tp_hit = hi >= trade.take_profit
            sl_hit = lo <= trade.stop_loss
        else:
            tp_hit = lo <= trade.take_profit
            sl_hit = hi >= trade.stop_loss
        if tp_hit and sl_hit:
            conflicts += 1
            conflict_pnl += float(trade.pnl or 0.0)
    total = len([t for t in trades if getattr(t, "pnl", None) is not None])
    return {
        "conflict_trades": conflicts,
        "conflict_trade_pct": (conflicts / total * 100.0) if total else 0.0,
        "conflict_pnl": round(conflict_pnl, 2),
    }


def _variants() -> list[Variant]:
    return [
        Variant("TP-first", "tp_first", "same-bar TP/SL conflict resolves to TP"),
        Variant("SL-first", "sl_first", "same-bar TP/SL conflict resolves to SL"),
        Variant("Conservative", "conservative", "same-bar TP/SL conflict resolves against the strategy"),
    ]


def _row(variant: Variant, metrics: dict[str, Any], conflicts: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": variant.label,
        "mode": variant.mode,
        "description": variant.description,
        "total_return_pct": metrics.get("total_return_pct", 0.0),
        "annual_return_pct": metrics.get("annual_return_pct", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        "calmar_ratio": metrics.get("calmar_ratio", 0.0),
        "win_rate": metrics.get("win_rate", 0.0),
        "avg_r_multiple": metrics.get("avg_r_multiple", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        **conflicts,
    }


def _print_rows(rows: list[dict[str, Any]]) -> None:
    print("\nCrypto intrabar TP/SL path stress test")
    print("variant       return  CAGR    MDD      PF     Sharpe  Calmar  WR      avgR    trades conflicts conflictPnL")
    for row in rows:
        print(
            f"{row['variant']:<12} "
            f"{row['total_return_pct']:>7.2f}% "
            f"{row['annual_return_pct']:>7.2f}% "
            f"{row['max_drawdown_pct']:>7.2f}% "
            f"{row['profit_factor']:>6.3f} "
            f"{row['sharpe_ratio']:>7.3f} "
            f"{row['calmar_ratio']:>7.3f} "
            f"{row['win_rate'] * 100:>6.2f}% "
            f"{row['avg_r_multiple']:>7.3f} "
            f"{row['total_trades']:>7} "
            f"{row['conflict_trades']:>9} "
            f"{row['conflict_pnl']:>11.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Crypto same-bar TP/SL path stress test.")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--candidate", default="",
                        choices=["", "volume-top125-lb3-sym035"],
                        help="Run the frozen Top125 volume candidate instead of config baseline.")
    parser.add_argument("--top-n", type=int, default=125)
    parser.add_argument("--lookback-years", type=int, default=3)
    parser.add_argument("--sym-wr-threshold", type=float, default=0.35)
    parser.add_argument("--output", default="output/crypto_intrabar_path_stress.csv")
    args = parser.parse_args()

    if args.candidate:
        base = _candidate_cache(
            args.start_date,
            args.end_date,
            args.top_n,
            args.lookback_years,
        )
        candidate_overrides = {
            "SYM_MIN_WINRATE_BY_CLASS": opt._crypto_dict(
                "SYM_MIN_WINRATE_BY_CLASS",
                float(args.sym_wr_threshold),
            ),
        }
    else:
        base = _build_inputs(use_vp=True)
        candidate_overrides = {}

    rows: list[dict[str, Any]] = []
    for variant in _variants():
        overrides = copy.deepcopy(candidate_overrides)
        overrides.update({
            "BACKTEST_INTRABAR_CONFLICT_MODE": variant.mode,
            "BACKTEST_TP_AS_TAKER": False,
            "BACKTEST_SLIPPAGE_ON_TP": False,
            "BACKTEST_FUNDING_DAILY_PCT_BY_CLASS": {"Crypto": 0.0},
            "BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS": {"Crypto": 0.0},
        })
        saved = _apply_overrides(overrides)
        try:
            if args.candidate:
                trades, metrics, data = _run_candidate(base, args.start_date, args.end_date)
            else:
                trades, metrics, data = _run_crypto(base, args.start_date, args.end_date)
            rows.append(_row(variant, metrics, _conflict_stats(trades, data)))
        finally:
            _restore_overrides(saved)

    _print_rows(rows)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
