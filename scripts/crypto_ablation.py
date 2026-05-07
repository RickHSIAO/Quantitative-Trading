"""Crypto strategy ablation test.

This script changes only test-time signal/filter switches. It does not add
indicators or tune strategy parameters.
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
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import LONG, SHORT, apply_cross_asset_filters, combine_signals, generate_all_signals


IS_START = "2021-03-01"
IS_END = "2024-04-30"
OOS_START = "2024-05-01"
OOS_END = "2026-05-07"

PERIODS = {
    "IS": (IS_START, IS_END),
    "OOS": (OOS_START, OOS_END),
    "WF_2023": ("2023-01-01", "2023-12-31"),
    "WF_2024": ("2024-01-01", "2024-12-31"),
    "WF_2025_26": ("2025-01-01", "2026-05-07"),
}


@dataclass(frozen=True)
class Variant:
    label: str
    description: str
    mode: str
    apply_btc_moat: bool = False
    use_symbol_wr: bool = False
    use_geometric_rr: bool = False


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


def _zero_like(ref: pd.Series) -> pd.Series:
    return pd.Series(0, index=ref.index, dtype=int)


def _combine_raw(*series: pd.Series) -> pd.Series:
    ref = series[0]
    longs = pd.Series(False, index=ref.index)
    shorts = pd.Series(False, index=ref.index)
    for ser in series:
        longs |= ser == LONG
        shorts |= ser == SHORT
    out = pd.Series(0, index=ref.index, dtype=int)
    out[longs & ~shorts] = LONG
    out[shorts & ~longs] = SHORT
    return out


def _forced_score(combined: pd.Series, score: int = 7) -> pd.Series:
    out = pd.Series(0, index=combined.index, dtype=int)
    out[combined != 0] = score
    return out


def _ema_score_for(combined: pd.Series, base_sigs: dict[str, pd.Series]) -> pd.Series:
    out = pd.Series(0, index=combined.index, dtype=int)
    bull = base_sigs.get("ema_bull", _zero_like(combined))
    bear = base_sigs.get("ema_bear", _zero_like(combined))
    out[combined == LONG] = 1 + bull[combined == LONG]
    out[combined == SHORT] = 1 + bear[combined == SHORT]
    return out


def _build_supertrend_ema(df: pd.DataFrame, base_sigs: dict[str, pd.Series]) -> dict[str, pd.Series]:
    zero = _zero_like(base_sigs["combined"])
    combined = combine_signals(
        df,
        base_sigs["trend"],
        zero,
        zero,
        asset_type="Crypto",
        benchmark_df=None,
        moat_tf_only=True,
    )
    return {
        "trend": base_sigs["trend"],
        "vp": zero,
        "bb": zero,
        "combined": combined,
        "score": _ema_score_for(combined, base_sigs),
        "ema_bull": base_sigs.get("ema_bull", zero),
        "ema_bear": base_sigs.get("ema_bear", zero),
    }


def _make_ablation_sigs(df: pd.DataFrame,
                        base_sigs: dict[str, pd.Series],
                        mode: str) -> dict[str, pd.Series]:
    zero = _zero_like(base_sigs["combined"])

    if mode == "baseline":
        return {k: v.copy() for k, v in base_sigs.items()}

    if mode == "supertrend_only":
        combined = base_sigs["trend"].copy()
        return {
            "trend": base_sigs["trend"].copy(),
            "vp": zero,
            "bb": zero,
            "combined": combined,
            "score": _forced_score(combined),
            "ema_bull": base_sigs.get("ema_bull", zero),
            "ema_bear": base_sigs.get("ema_bear", zero),
        }

    if mode == "vp_only":
        combined = base_sigs["vp"].copy()
        return {
            "trend": zero,
            "vp": base_sigs["vp"].copy(),
            "bb": zero,
            "combined": combined,
            "score": _forced_score(combined),
            "ema_bull": base_sigs.get("ema_bull", zero),
            "ema_bear": base_sigs.get("ema_bear", zero),
        }

    if mode == "bb_only":
        combined = base_sigs["bb"].copy()
        return {
            "trend": zero,
            "vp": zero,
            "bb": base_sigs["bb"].copy(),
            "combined": combined,
            "score": _forced_score(combined),
            "ema_bull": base_sigs.get("ema_bull", zero),
            "ema_bear": base_sigs.get("ema_bear", zero),
        }

    if mode == "supertrend_ema":
        return _build_supertrend_ema(df, base_sigs)

    if mode == "supertrend_btc":
        combined = base_sigs["trend"].copy()
        return {
            "trend": base_sigs["trend"].copy(),
            "vp": zero,
            "bb": zero,
            "combined": combined,
            "score": _forced_score(combined),
            "ema_bull": base_sigs.get("ema_bull", zero),
            "ema_bear": base_sigs.get("ema_bear", zero),
        }

    if mode == "vp_bb":
        combined = _combine_raw(base_sigs["vp"], base_sigs["bb"])
        return {
            "trend": zero,
            "vp": base_sigs["vp"].copy(),
            "bb": base_sigs["bb"].copy(),
            "combined": combined,
            "score": _forced_score(combined),
            "ema_bull": base_sigs.get("ema_bull", zero),
            "ema_bear": base_sigs.get("ema_bear", zero),
        }

    raise ValueError(f"Unknown ablation mode: {mode}")


def _variants() -> list[Variant]:
    return [
        Variant("baseline", "all modules enabled", "baseline", True, True, True),
        Variant("supertrend_only", "only Supertrend raw signal", "supertrend_only"),
        Variant("vp_only", "only VP POC raw signal", "vp_only"),
        Variant("bb_only", "only Bollinger raw signal", "bb_only"),
        Variant("no_btc_moat", "baseline without BTC moat", "baseline", False, True, True),
        Variant("no_symbol_wr", "baseline without symbol rolling winrate filter", "baseline", True, False, True),
        Variant("no_geometric_rr", "baseline without geometric RR filter", "baseline", True, True, False),
        Variant("supertrend_btc", "Supertrend raw signal + BTC moat", "supertrend_btc", True),
        Variant("supertrend_ema", "Supertrend + EMA score gate", "supertrend_ema"),
        Variant("vp_bb", "VP POC + Bollinger raw signals", "vp_bb"),
    ]


def _build_base_inputs() -> tuple[dict, dict, dict]:
    assets = get_selected_assets(42)
    available = set(get_all_symbols())
    cryptos = [sym for sym in assets["cryptos"] if sym in available]
    type_map = {sym: "Crypto" for sym in cryptos}
    data: dict[str, pd.DataFrame] = {}
    base_signals: dict[str, dict[str, pd.Series]] = {}

    for sym in cryptos:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=True)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        data[sym] = df
        base_signals[sym] = sigs

    if not data:
        raise RuntimeError("No Crypto data available. Run `python main.py update` first.")
    return data, base_signals, type_map


def _slice_inputs(base: tuple[dict, dict, dict],
                  variant: Variant,
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
        ablated = _make_ablation_sigs(df, base_signals[sym], variant.mode)
        signals[sym] = {
            key: series.loc[mask].copy()
            for key, series in ablated.items()
        }

    if variant.apply_btc_moat:
        apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def _run_period(base: tuple[dict, dict, dict],
                variant: Variant,
                start: str | None,
                end: str | None) -> dict[str, Any]:
    overrides = {
        "ENABLE_GEOMETRIC_RR": bool(variant.use_geometric_rr),
        "SYM_MIN_WINRATE_BY_CLASS": {"Crypto": 0.45} if variant.use_symbol_wr else {"Crypto": 0.0},
        "BACKTEST_TP_AS_TAKER": False,
        "BACKTEST_SLIPPAGE_ON_TP": False,
        "BACKTEST_FUNDING_DAILY_PCT_BY_CLASS": {"Crypto": 0.0},
        "BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS": {"Crypto": 0.0},
        "BACKTEST_INTRABAR_CONFLICT_MODE": "tp_first",
    }
    saved = _apply_overrides(overrides)
    try:
        data, signals, type_map = _slice_inputs(base, variant, start, end)
        profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
        _, results = run_silo_backtest(
            data,
            signals,
            type_map,
            {"Crypto": ["Crypto"]},
            config.SILO_CAPITAL,
            {"Crypto": profile},
        )
        return dict(results["Crypto"]["metrics"])
    finally:
        _restore_overrides(saved)


def _row(variant: Variant, period: str, start: str, end: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": variant.label,
        "period": period,
        "start": start,
        "end": end,
        "description": variant.description,
        "profit_factor": metrics.get("profit_factor", 0.0),
        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        "calmar_ratio": metrics.get("calmar_ratio", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "win_rate": metrics.get("win_rate", 0.0),
        "avg_r_multiple": metrics.get("avg_r_multiple", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "total_return_pct": metrics.get("total_return_pct", 0.0),
        "annual_return_pct": metrics.get("annual_return_pct", 0.0),
    }


def _print_summary(rows: list[dict[str, Any]]) -> None:
    print("\nCrypto ablation OOS summary")
    print("variant             PF     Sharpe  Calmar  MDD      WR      avgR    trades  return")
    for row in [r for r in rows if r["period"] == "OOS"]:
        print(
            f"{row['variant']:<18} "
            f"{row['profit_factor']:>6.3f} "
            f"{row['sharpe_ratio']:>7.3f} "
            f"{row['calmar_ratio']:>7.3f} "
            f"{row['max_drawdown_pct']:>7.2f}% "
            f"{row['win_rate'] * 100:>6.2f}% "
            f"{row['avg_r_multiple']:>7.3f} "
            f"{row['total_trades']:>7} "
            f"{row['total_return_pct']:>7.2f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Crypto strategy ablation tests.")
    parser.add_argument("--output", default="output/crypto_ablation.csv")
    args = parser.parse_args()

    base = _build_base_inputs()
    rows: list[dict[str, Any]] = []
    for variant in _variants():
        for period, (start, end) in PERIODS.items():
            metrics = _run_period(base, variant, start, end)
            rows.append(_row(variant, period, start, end, metrics))

    _print_summary(rows)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
