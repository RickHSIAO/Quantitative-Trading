"""Optimize Crypto strategy on previous-3-year Top100 universes.

This is an OOS research harness for the Top100 question.  It keeps the
universe construction point-in-time-like:

  - each test year uses the previous three calendar years
  - ranking metric can be market_cap or volume_24h
  - only Bybit symbols with local OHLCV warmup are tradable

The script sweeps a small, explicit candidate set and reports both aggregate
OOS and split-period results so a candidate that only fits one recent regime is
easy to spot.
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
from scripts.crypto_prev3y_market_cap_universe_backtest import (
    BASELINE_COST_OVERRIDES,
    RANK_BY_COLUMNS,
    _prev3y_universe,
)
from src import risk as risk_mod
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


DEFAULT_START = "2024-05-01"
DEFAULT_END = "2026-05-07"


@dataclass(frozen=True)
class Candidate:
    label: str
    overrides: dict[str, Any]
    profile_overrides: dict[str, Any] | None = None


def _patch_risk_params() -> None:
    risk_mod._STRAT_PARAMS = {
        "trend": (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        "combined": (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        "vp": (config.STRAT_VP_ATR_MULT, config.STRAT_VP_RR),
        "bb": (config.STRAT_BB_ATR_MULT, config.STRAT_BB_RR),
    }


def _deepcopy_attr(name: str) -> Any:
    return copy.deepcopy(getattr(config, name))


def _apply_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(BASELINE_COST_OVERRIDES)
    merged.update(copy.deepcopy(overrides))
    saved = {name: _deepcopy_attr(name) for name in merged if hasattr(config, name)}
    for name, value in merged.items():
        if not hasattr(config, name):
            raise AttributeError(f"Unknown config override: {name}")
        setattr(config, name, copy.deepcopy(value))
    _patch_risk_params()
    return saved


def _restore_overrides(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(config, name, value)
    _patch_risk_params()


def _eligible_by_year(start: str,
                      end: str,
                      rank_by: str,
                      top_n: int,
                      min_history_days: int) -> tuple[dict[int, set[str]], set[str], list[dict[str, Any]]]:
    available = set(get_all_symbols())
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    allowed_by_year: dict[int, set[str]] = {}
    all_symbols: set[str] = set()
    summary: list[dict[str, Any]] = []
    history_cache: dict[str, pd.DataFrame] = {}

    for year in range(start_ts.year, end_ts.year + 1):
        year_start = pd.Timestamp(f"{year}-01-01")
        ranked = _prev3y_universe(year, top_n, rank_by)
        eligible: set[str] = set()
        bybit_symbols = ranked["bybit_symbol"].dropna().astype(str).tolist() if not ranked.empty else []
        bybit_available = [sym for sym in bybit_symbols if sym in available]
        for sym in bybit_available:
            if sym not in history_cache:
                try:
                    history_cache[sym] = load_prices(sym)
                except Exception:
                    history_cache[sym] = pd.DataFrame()
            df = history_cache[sym]
            if df is None or df.empty:
                continue
            if len(df.loc[df.index < year_start]) < min_history_days:
                continue
            eligible.add(sym)
        allowed_by_year[year] = eligible
        all_symbols.update(eligible)
        summary.append({
            "year": year,
            "ranked": int(len(ranked)),
            "bybit_available": int(len(set(bybit_available))),
            "eligible": int(len(eligible)),
        })

    return allowed_by_year, all_symbols, summary


def _build_inputs(symbols: set[str]) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, pd.Series]], dict[str, str]]:
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map: dict[str, str] = {}
    for sym in sorted(symbols):
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=True)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs
        type_map[sym] = "Crypto"
    return data, signals, type_map


def _slice_inputs(base: tuple[dict[str, pd.DataFrame], dict[str, dict[str, pd.Series]], dict[str, str]],
                  start: str,
                  end: str,
                  allowed_by_year: dict[int, set[str]]) -> tuple[dict, dict, dict]:
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
        sliced = df.loc[mask].copy()
        sigs = {
            key: series.loc[mask].copy()
            for key, series in base_signals[sym].items()
        }
        disallowed = pd.Series(False, index=sliced.index)
        for year in sorted(set(sliced.index.year)):
            if sym not in allowed_by_year.get(int(year), set()):
                disallowed.loc[sliced.index.year == year] = True
        if disallowed.any():
            for key in ("trend", "vp", "bb", "combined", "score", "ema_bull", "ema_bear"):
                if key in sigs:
                    sigs[key].loc[disallowed] = 0
        data[sym] = sliced
        signals[sym] = sigs

    apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def _run_period(base: tuple[dict, dict, dict],
                allowed_by_year: dict[int, set[str]],
                start: str,
                end: str,
                profile_overrides: dict[str, Any] | None) -> tuple[list[Any], dict[str, Any]]:
    data, signals, type_map = _slice_inputs(base, start, end, allowed_by_year)
    if not data:
        return [], {}
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    if profile_overrides:
        profile.update(copy.deepcopy(profile_overrides))
    trades, results = run_silo_backtest(
        data,
        signals,
        type_map,
        {"Crypto": ["Crypto"]},
        config.SILO_CAPITAL,
        {"Crypto": profile},
    )
    return list(trades), dict(results.get("Crypto", {}).get("metrics", {}))


def _years_from_metrics(metrics: dict[str, Any], start: str, end: str) -> float:
    if not metrics:
        return 0.01
    days = max((pd.Timestamp(end) - pd.Timestamp(start)).days, 1)
    return max(days / 365.25, 0.01)


def _score(metrics: dict[str, Any]) -> float:
    if not metrics:
        return -999.0
    dd = float(metrics.get("max_drawdown_pct", -999.0) or -999.0)
    dd_penalty = max(0.0, abs(dd) - 50.0) * 1.5
    return (
        float(metrics.get("annual_return_pct", 0.0) or 0.0)
        + (float(metrics.get("profit_factor", 0.0) or 0.0) - 1.0) * 45.0
        + float(metrics.get("sharpe_ratio", 0.0) or 0.0) * 18.0
        + float(metrics.get("calmar_ratio", 0.0) or 0.0) * 8.0
        - dd_penalty
    )


def _passes_gate(metrics: dict[str, Any]) -> bool:
    if not metrics:
        return False
    return (
        float(metrics.get("annual_return_pct", 0.0) or 0.0) >= 20.0
        and float(metrics.get("profit_factor", 0.0) or 0.0) >= 1.15
        and float(metrics.get("sharpe_ratio", 0.0) or 0.0) >= 0.70
        and float(metrics.get("max_drawdown_pct", -999.0) or -999.0) >= -50.0
    )


def _row(candidate: Candidate,
         period: str,
         start: str,
         end: str,
         trades: list[Any],
         metrics: dict[str, Any],
         rank_by: str) -> dict[str, Any]:
    years = _years_from_metrics(metrics, start, end)
    return {
        "candidate": candidate.label,
        "rank_by": rank_by,
        "period": period,
        "start": start,
        "end": end,
        "total_return_pct": metrics.get("total_return_pct", ""),
        "annual_return_pct": metrics.get("annual_return_pct", ""),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", ""),
        "profit_factor": metrics.get("profit_factor", ""),
        "sharpe_ratio": metrics.get("sharpe_ratio", ""),
        "calmar_ratio": metrics.get("calmar_ratio", ""),
        "win_rate": (metrics.get("win_rate", "") * 100.0 if metrics.get("win_rate", "") != "" else ""),
        "avg_r_multiple": metrics.get("avg_r_multiple", ""),
        "total_trades": metrics.get("total_trades", ""),
        "trades_per_year": round((metrics.get("total_trades", 0) or 0) / years, 2),
        "score": round(_score(metrics), 3),
        "passes_gate": _passes_gate(metrics),
        "overrides": repr(candidate.overrides),
        "profile_overrides": repr(candidate.profile_overrides or {}),
    }


def _crypto_dict(name: str, value: Any) -> dict[str, Any]:
    current = copy.deepcopy(getattr(config, name))
    current["Crypto"] = value
    return current


def _stops(trend: tuple[float, float], vp: tuple[float, float]) -> dict[str, Any]:
    params = copy.deepcopy(config.STRAT_PARAMS_BY_CLASS)
    params.setdefault("Crypto", {})
    params["Crypto"]["trend"] = trend
    params["Crypto"]["combined"] = trend
    params["Crypto"]["vp"] = vp
    return {"STRAT_PARAMS_BY_CLASS": params}


def _candidates(quick: bool) -> list[Candidate]:
    risk5 = {
        "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.05),
        "MAX_RISK_PCT": 0.06,
    }
    candidates = [
        Candidate("baseline_current", {}),
        Candidate("score4", {
            "MIN_ENTRY_SCORE_BY_CLASS": _crypto_dict("MIN_ENTRY_SCORE_BY_CLASS", 4),
        }),
        Candidate("hold21", {
            "MAX_HOLD_DAYS_BY_CLASS": _crypto_dict("MAX_HOLD_DAYS_BY_CLASS", 21),
        }),
        Candidate("hold45", {
            "MAX_HOLD_DAYS_BY_CLASS": _crypto_dict("MAX_HOLD_DAYS_BY_CLASS", 45),
        }),
        Candidate("sym_filter_off", {
            "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.0),
        }),
        Candidate("sym_wr_40_3_20", {
            "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.40),
            "SYM_WR_MIN_TRADES_BY_CLASS": _crypto_dict("SYM_WR_MIN_TRADES_BY_CLASS", 3),
            "SYM_WR_WINDOW_BY_CLASS": _crypto_dict("SYM_WR_WINDOW_BY_CLASS", 20),
        }),
        Candidate("cap8", {}, {"max_total_positions": 8}),
        Candidate("cap12", {}, {"max_total_positions": 12}),
        Candidate("pos30", {}, {"max_position_pct": 0.30}),
        Candidate("risk5pct", risk5),
        Candidate("stops_t1.75_rr2", _stops((1.75, 2.0), (1.5, 1.5))),
        Candidate("stops_t1.75_rr2.25", _stops((1.75, 2.25), (1.5, 1.5))),
        Candidate("stops_t2_rr2.25", _stops((2.0, 2.25), (1.5, 1.5))),
        Candidate("stops_t2_rr2.5", _stops((2.0, 2.5), (1.5, 1.5))),
        Candidate("stops_t2.25_rr2.25", _stops((2.25, 2.25), (1.5, 1.5))),
        Candidate("vp_1.25_rr1.25", _stops((2.0, 2.0), (1.25, 1.25))),
        Candidate("vp_1.5_rr1.75", _stops((2.0, 2.0), (1.5, 1.75))),
    ]
    if quick:
        keep = {
            "baseline_current", "score4", "hold21", "sym_filter_off",
            "sym_wr_40_3_20", "cap8", "pos30", "risk5pct",
            "stops_t1.75_rr2.25", "stops_t2_rr2.25", "vp_1.25_rr1.25",
        }
        candidates = [cand for cand in candidates if cand.label in keep]
    return candidates


def _periods(start: str, end: str) -> dict[str, tuple[str, str]]:
    end_ts = pd.Timestamp(end)
    periods = {
        "OOS_ALL": (start, end),
        "OOS_2024_H2": (start, "2024-12-31"),
        "OOS_2025": ("2025-01-01", "2025-12-31"),
    }
    if end_ts >= pd.Timestamp("2026-01-01"):
        periods["OOS_2026_YTD"] = ("2026-01-01", end)
    return periods


def _print_summary(rows: list[dict[str, Any]], limit: int) -> None:
    by_candidate: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_candidate.setdefault(row["candidate"], {})[row["period"]] = row
    ranked = sorted(
        by_candidate.items(),
        key=lambda item: float(item[1].get("OOS_ALL", {}).get("score", -999.0)),
        reverse=True,
    )

    print("\n=== Top100 OOS ranking ===")
    print("candidate                 gate  score  ret%    PF    Shp   Cal   MDD    T  2025PF 2026PF")
    for label, periods in ranked[:limit]:
        all_row = periods.get("OOS_ALL", {})
        y2025 = periods.get("OOS_2025", {})
        y2026 = periods.get("OOS_2026_YTD", {})
        print(
            f"{label:<25} "
            f"{str(all_row.get('passes_gate', '')):<5} "
            f"{float(all_row.get('score', -999.0)):>6.1f} "
            f"{float(all_row.get('total_return_pct', 0.0) or 0.0):>6.1f} "
            f"{float(all_row.get('profit_factor', 0.0) or 0.0):>5.3f} "
            f"{float(all_row.get('sharpe_ratio', 0.0) or 0.0):>5.2f} "
            f"{float(all_row.get('calmar_ratio', 0.0) or 0.0):>5.2f} "
            f"{float(all_row.get('max_drawdown_pct', 0.0) or 0.0):>6.1f} "
            f"{int(float(all_row.get('total_trades', 0) or 0)):>4} "
            f"{float(y2025.get('profit_factor', 0.0) or 0.0):>6.3f} "
            f"{float(y2026.get('profit_factor', 0.0) or 0.0):>6.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize prev3y Top100 Crypto universe.")
    parser.add_argument("--rank-by", choices=sorted(RANK_BY_COLUMNS), default="market_cap")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--min-history-days", type=int, default=180)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    output = args.output or f"output/crypto_prev3y_{args.rank_by}_top100_optimize.csv"

    allowed_by_year, tradable, summary = _eligible_by_year(
        args.start_date,
        args.end_date,
        args.rank_by,
        args.top_n,
        args.min_history_days,
    )
    market_symbol = getattr(config, "CRYPTO_MARKET_SYMBOL", "BYBIT:BTCUSDT.P")
    symbols = set(tradable)
    if market_symbol in set(get_all_symbols()):
        symbols.add(market_symbol)
    if not tradable:
        raise RuntimeError("No eligible Top100 symbols. Check CMC rankings and Bybit OHLCV.")

    print(f"Universe rank_by={args.rank_by} tradable_union={len(tradable)} context={len(symbols)}")
    for item in summary:
        print(
            f"  {item['year']}: ranked={item['ranked']} "
            f"bybit_available={item['bybit_available']} eligible={item['eligible']}"
        )
    print("Building indicator/signals cache...")
    base = _build_inputs(symbols)

    periods = _periods(args.start_date, args.end_date)
    candidates = _candidates(args.quick)
    rows: list[dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, 1):
        print(f"[{idx:02d}/{len(candidates):02d}] {candidate.label}")
        saved = _apply_overrides(candidate.overrides)
        try:
            for period, (start, end) in periods.items():
                trades, metrics = _run_period(
                    base,
                    allowed_by_year,
                    start,
                    end,
                    candidate.profile_overrides,
                )
                rows.append(_row(candidate, period, start, end, trades, metrics, args.rank_by))
        finally:
            _restore_overrides(saved)

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    _print_summary(rows, args.limit)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
