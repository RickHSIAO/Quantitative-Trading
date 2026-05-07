"""Crypto OOS-first optimization harness.

This script evaluates candidate runtime overrides across:
  - IS:   2021-03-01 .. 2024-04-30
  - OOS:  2024-05-01 .. 2026-05-07
  - FULL: all available crypto history

The adoption gate is intentionally OOS-first.  IS is used to screen ideas,
while FULL is only a continuity check.
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
from src import risk as risk_mod
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


IS_START = "2021-03-01"
IS_END = "2024-04-30"
OOS_START = "2024-05-01"
OOS_END = "2026-05-07"

ROLLING_OOS_PERIODS = {
    "WF_2023": ("2023-01-01", "2023-12-31"),
    "WF_2024": ("2024-01-01", "2024-12-31"),
    "WF_2025_26": ("2025-01-01", "2026-05-07"),
}

OOS_BENCHMARK = {
    "annual_return_pct": 36.49,
    "total_return_pct": 87.17,
    "profit_factor": 1.346,
    "sharpe_ratio": 0.930,
    "max_drawdown_pct": -43.01,
    "win_rate": 0.4381,
    "trades_per_year_min": 70.0,
    "trades_per_year_max": 130.0,
}


@dataclass(frozen=True)
class Candidate:
    label: str
    overrides: dict[str, Any]
    profile_overrides: dict[str, Any] | None = None
    recompute_signals: bool = False


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
    saved = {name: _deepcopy_attr(name) for name in overrides if hasattr(config, name)}
    for name, value in overrides.items():
        if not hasattr(config, name):
            raise AttributeError(f"Unknown config override: {name}")
        setattr(config, name, copy.deepcopy(value))
    _patch_risk_params()
    return saved


def _restore_overrides(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(config, name, value)
    _patch_risk_params()


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

    return data, signals, type_map


def _slice_inputs(base: tuple[dict, dict, dict],
                  start: str | None,
                  end: str | None) -> tuple[dict, dict, dict]:
    base_data, base_signals, base_type_map = base
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map = dict(base_type_map)
    start_ts = pd.Timestamp(start) if start else None
    end_ts = pd.Timestamp(end) if end else None

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


def _run_crypto_period(base: tuple[dict, dict, dict],
                       start: str | None,
                       end: str | None,
                       profile_overrides: dict[str, Any] | None) -> dict[str, Any]:
    data, signals, type_map = _slice_inputs(base, start, end)
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    if profile_overrides:
        profile.update(copy.deepcopy(profile_overrides))

    _, results = run_silo_backtest(
        data,
        signals,
        type_map,
        {"Crypto": ["Crypto"]},
        config.SILO_CAPITAL,
        {"Crypto": profile},
    )
    metrics = dict(results["Crypto"]["metrics"])
    curve = results["Crypto"]["equity_curve"]
    if curve:
        d0 = pd.Timestamp(curve[0]["date"])
        d1 = pd.Timestamp(curve[-1]["date"])
        years = max((d1 - d0).days / 365.25, 0.01)
    else:
        years = 0.01
    metrics["trades_per_year"] = metrics.get("total_trades", 0) / years
    return metrics


def _score_oos(m: dict[str, Any]) -> float:
    dd = m.get("max_drawdown_pct", 0.0)
    dd_penalty = max(0.0, abs(dd) - abs(OOS_BENCHMARK["max_drawdown_pct"])) * 1.5
    trade_count = m.get("trades_per_year", 0.0)
    if trade_count < OOS_BENCHMARK["trades_per_year_min"]:
        trade_penalty = (OOS_BENCHMARK["trades_per_year_min"] - trade_count) * 0.25
    elif trade_count > OOS_BENCHMARK["trades_per_year_max"]:
        trade_penalty = (trade_count - OOS_BENCHMARK["trades_per_year_max"]) * 0.10
    else:
        trade_penalty = 0.0

    return (
        m.get("annual_return_pct", 0.0)
        + (m.get("profit_factor", 0.0) - OOS_BENCHMARK["profit_factor"]) * 40.0
        + (m.get("sharpe_ratio", 0.0) - OOS_BENCHMARK["sharpe_ratio"]) * 20.0
        - dd_penalty
        - trade_penalty
    )


def _passes_oos_gate(m: dict[str, Any]) -> bool:
    tpy = m.get("trades_per_year", 0.0)
    return (
        m.get("annual_return_pct", 0.0) >= OOS_BENCHMARK["annual_return_pct"]
        and m.get("profit_factor", 0.0) >= OOS_BENCHMARK["profit_factor"]
        and m.get("sharpe_ratio", 0.0) >= OOS_BENCHMARK["sharpe_ratio"]
        and m.get("max_drawdown_pct", -999.0) >= OOS_BENCHMARK["max_drawdown_pct"]
        and OOS_BENCHMARK["trades_per_year_min"] <= tpy <= OOS_BENCHMARK["trades_per_year_max"]
    )


def _annotate_robust_gate(rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["candidate"], {})[row["period"]] = row

    baseline = grouped.get("baseline_current", {})
    baseline_wf_scores = {
        period: _score_oos(row)
        for period, row in baseline.items()
        if period.startswith("WF_")
    }
    baseline_wf_avg = (
        sum(baseline_wf_scores.values()) / len(baseline_wf_scores)
        if baseline_wf_scores else 0.0
    )

    for candidate, by_period in grouped.items():
        is_row = by_period.get("IS", {})
        oos_row = by_period.get("OOS", {})
        full_row = by_period.get("FULL", {})
        wf_rows = [
            row for period, row in by_period.items()
            if period.startswith("WF_")
        ]
        wf_scores = {
            row["period"]: _score_oos(row)
            for row in wf_rows
        }
        wf_avg = (
            sum(wf_scores.values()) / len(wf_scores)
            if wf_scores else -999.0
        )
        wf_wins = sum(
            1 for period, score in wf_scores.items()
            if score >= baseline_wf_scores.get(period, score + 1.0)
        )
        wf_pf_all_ok = all(float(row.get("profit_factor", 0.0)) >= 1.0 for row in wf_rows)
        wf_dd_all_ok = all(float(row.get("max_drawdown_pct", -999.0)) >= -55.0 for row in wf_rows)

        checks = {
            "oos_gate": oos_row.get("passes_oos_gate") is True,
            "is_positive": float(is_row.get("total_return_pct", 0.0)) > 0.0,
            "is_pf_ok": float(is_row.get("profit_factor", 0.0)) >= 1.05,
            "full_cagr_ok": float(full_row.get("annual_return_pct", 0.0)) >= 20.0,
            "full_pf_ok": float(full_row.get("profit_factor", 0.0)) >= 1.20,
            "full_dd_ok": float(full_row.get("max_drawdown_pct", -999.0)) >= -50.0,
            "wf_avg_ok": wf_avg >= baseline_wf_avg,
            "wf_majority_ok": wf_wins >= 2,
            "wf_pf_ok": wf_pf_all_ok,
            "wf_dd_ok": wf_dd_all_ok,
        }
        passed = all(checks.values())
        failed = [name for name, ok in checks.items() if not ok]
        reason = "ok" if passed else ",".join(failed)

        for row in by_period.values():
            row["passes_robust_gate"] = passed if row["period"] == "OOS" else ""
            row["robust_gate_reason"] = reason if row["period"] == "OOS" else ""
            row["wf_avg_score"] = round(wf_avg, 3) if row["period"] == "OOS" else ""
            row["wf_wins_vs_baseline"] = wf_wins if row["period"] == "OOS" else ""


def _candidate_rows(candidate: Candidate, base: tuple[dict, dict, dict]) -> list[dict[str, Any]]:
    saved = _apply_overrides(candidate.overrides)
    try:
        effective_base = _build_inputs(use_vp=True) if candidate.recompute_signals else base
        periods = {
            "IS": (IS_START, IS_END),
            "OOS": (OOS_START, OOS_END),
            **ROLLING_OOS_PERIODS,
            "FULL": (None, None),
        }
        rows: list[dict[str, Any]] = []
        for period, (start, end) in periods.items():
            m = _run_crypto_period(effective_base, start, end, candidate.profile_overrides)
            rows.append({
                "candidate": candidate.label,
                "period": period,
                "start": start or "",
                "end": end or "",
                "total_return_pct": m.get("total_return_pct", 0.0),
                "annual_return_pct": m.get("annual_return_pct", 0.0),
                "total_trades": m.get("total_trades", 0),
                "trades_per_year": round(m.get("trades_per_year", 0.0), 2),
                "win_rate": m.get("win_rate", 0.0),
                "profit_factor": m.get("profit_factor", 0.0),
                "sharpe_ratio": m.get("sharpe_ratio", 0.0),
                "calmar_ratio": m.get("calmar_ratio", 0.0),
                "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
                "avg_r_multiple": m.get("avg_r_multiple", 0.0),
                "oos_score": round(_score_oos(m), 3) if period == "OOS" else "",
                "passes_oos_gate": _passes_oos_gate(m) if period == "OOS" else "",
                "passes_robust_gate": "",
                "robust_gate_reason": "",
                "wf_avg_score": "",
                "wf_wins_vs_baseline": "",
                "overrides": repr(candidate.overrides),
                "profile_overrides": repr(candidate.profile_overrides or {}),
            })
        return rows
    finally:
        _restore_overrides(saved)


def _crypto_dict(name: str, value: Any) -> dict[str, Any]:
    current = copy.deepcopy(getattr(config, name))
    current["Crypto"] = value
    return current


def _candidates() -> list[Candidate]:
    base_profile = config.STRATEGY_PROFILES["Crypto"]
    base_params = copy.deepcopy(config.STRAT_PARAMS_BY_CLASS)

    def stops(trend: tuple[float, float], vp: tuple[float, float]) -> dict[str, Any]:
        params = copy.deepcopy(base_params)
        params.setdefault("Crypto", {})
        params["Crypto"]["trend"] = trend
        params["Crypto"]["combined"] = trend
        params["Crypto"]["vp"] = vp
        return {"STRAT_PARAMS_BY_CLASS": params}

    trend_2x_225r = stops((2.0, 2.25), (1.5, 1.5))
    trend_2x_25r = stops((2.0, 2.5), (1.5, 1.5))
    trend_225x_225r = stops((2.25, 2.25), (1.5, 1.5))
    trend_25x_2r = stops((2.5, 2.0), (1.5, 1.5))

    risk5 = {
        "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.05),
        "MAX_RISK_PCT": 0.06,
    }
    risk7 = {
        "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.07),
        "MAX_RISK_PCT": 0.08,
    }
    score4 = {
        "MIN_ENTRY_SCORE_BY_CLASS": _crypto_dict("MIN_ENTRY_SCORE_BY_CLASS", 4),
    }
    sym40 = {
        "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.40),
        "SYM_WR_MIN_TRADES_BY_CLASS": _crypto_dict("SYM_WR_MIN_TRADES_BY_CLASS", 3),
        "SYM_WR_WINDOW_BY_CLASS": _crypto_dict("SYM_WR_WINDOW_BY_CLASS", 20),
    }

    return [
        Candidate("baseline_current", {}),
        Candidate("score4", score4),
        Candidate("hold21", {
            "MAX_HOLD_DAYS_BY_CLASS": _crypto_dict("MAX_HOLD_DAYS_BY_CLASS", 21),
        }),
        Candidate("hold45", {
            "MAX_HOLD_DAYS_BY_CLASS": _crypto_dict("MAX_HOLD_DAYS_BY_CLASS", 45),
        }),
        Candidate("pos30", {}, {"max_position_pct": 0.30}),
        Candidate("pos50", {}, {"max_position_pct": 0.50}),
        Candidate("cap8", {}, {"max_total_positions": 8}),
        Candidate("cap12", {}, {"max_total_positions": 12}),
        Candidate("sym_wr_40_3_20", sym40),
        Candidate("sym_wr_45_5_30", {
            "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.45),
            "SYM_WR_MIN_TRADES_BY_CLASS": _crypto_dict("SYM_WR_MIN_TRADES_BY_CLASS", 5),
            "SYM_WR_WINDOW_BY_CLASS": _crypto_dict("SYM_WR_WINDOW_BY_CLASS", 30),
        }),
        Candidate("sym_filter_off", {
            "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.0),
        }),
        Candidate("btc_moat_full", {
            "CRYPTO_BTC_MOAT_MODE": "full",
        }),
        Candidate("tsl_15r", {
            "TSL_TIGHT_AFTER_R_BY_CLASS": _crypto_dict("TSL_TIGHT_AFTER_R_BY_CLASS", 1.5),
        }),
        Candidate("tsl_25r", {
            "TSL_TIGHT_AFTER_R_BY_CLASS": _crypto_dict("TSL_TIGHT_AFTER_R_BY_CLASS", 2.5),
        }),
        Candidate("stops_trend_25x_2r", trend_25x_2r),
        Candidate("stops_trend_2x_225r", trend_2x_225r),
        Candidate("stops_trend_2x_25r", trend_2x_25r),
        Candidate("stops_trend_225x_225r", trend_225x_225r),
        Candidate("risk5pct", risk5),
        Candidate("risk7pct", risk7),
        Candidate("hold21_sym40", {
            "MAX_HOLD_DAYS_BY_CLASS": _crypto_dict("MAX_HOLD_DAYS_BY_CLASS", 21),
            "SYM_MIN_WINRATE_BY_CLASS": _crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.40),
            "SYM_WR_MIN_TRADES_BY_CLASS": _crypto_dict("SYM_WR_MIN_TRADES_BY_CLASS", 3),
            "SYM_WR_WINDOW_BY_CLASS": _crypto_dict("SYM_WR_WINDOW_BY_CLASS", 20),
        }),
        Candidate("cap8_pos30_risk5", {
            "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.05),
            "MAX_RISK_PCT": 0.06,
        }, {
            "max_total_positions": 8,
            "max_position_pct": 0.30,
        }),
        Candidate("cap12_pos50_risk7", {
            **risk7,
        }, {
            "max_total_positions": 12,
            "max_position_pct": 0.50,
        }),
        Candidate("trend_2x25r_score4", {**trend_2x_25r, **score4}),
        Candidate("trend_2x25r_sym40", {**trend_2x_25r, **sym40}),
        Candidate("trend_2x25r_risk5", {**trend_2x_25r, **risk5}),
        Candidate("trend_2x25r_pos30", trend_2x_25r, {"max_position_pct": 0.30}),
        Candidate("trend_2x25r_cap8", trend_2x_25r, {"max_total_positions": 8}),
        Candidate("trend_2x25r_cap8_pos30", trend_2x_25r, {
            "max_total_positions": 8,
            "max_position_pct": 0.30,
        }),
        Candidate("trend_2x25r_cap8_risk5", {**trend_2x_25r, **risk5}, {
            "max_total_positions": 8,
        }),
        Candidate("trend_2x25r_btc_full", {
            **trend_2x_25r,
            "CRYPTO_BTC_MOAT_MODE": "full",
        }),
        Candidate("trend_2x225r_risk5", {**trend_2x_225r, **risk5}),
        Candidate("trend_225x225r_risk5", {**trend_225x_225r, **risk5}),
        Candidate("trend_225x225r_pos50", trend_225x_225r, {"max_position_pct": 0.50}),
        Candidate("trend_225x225r_risk7", {**trend_225x_225r, **risk7}),
        Candidate("trend_225x225r_pos50_risk7", {**trend_225x_225r, **risk7}, {
            "max_position_pct": 0.50,
        }),
        Candidate("trend_225x225r_cap12", trend_225x_225r, {"max_total_positions": 12}),
        Candidate("trend_225x225r_sym40", {**trend_225x_225r, **sym40}),
        Candidate("trend_225x225r_score4", {**trend_225x_225r, **score4}),
    ]


def _local_grid_candidates() -> list[Candidate]:
    base_params = copy.deepcopy(config.STRAT_PARAMS_BY_CLASS)

    def stops(trend: tuple[float, float], vp: tuple[float, float]) -> dict[str, Any]:
        params = copy.deepcopy(base_params)
        params.setdefault("Crypto", {})
        params["Crypto"]["trend"] = trend
        params["Crypto"]["combined"] = trend
        params["Crypto"]["vp"] = vp
        return {"STRAT_PARAMS_BY_CLASS": params}

    candidates = [Candidate("baseline_current", {})]
    for atr_mult in (1.75, 2.0, 2.25, 2.5):
        for rr in (1.75, 2.0, 2.25, 2.5, 2.75):
            for score in (3, 4):
                overrides = stops((atr_mult, rr), (1.5, 1.5))
                if score != 3:
                    overrides.update({
                        "MIN_ENTRY_SCORE_BY_CLASS": _crypto_dict(
                            "MIN_ENTRY_SCORE_BY_CLASS", score
                        ),
                    })
                label = f"grid_t{atr_mult:g}x_rr{rr:g}_s{score}"
                candidates.append(Candidate(label, overrides))

    # A small VP-specific neighborhood: keep trend baseline, vary VP exits.
    for vp_atr, vp_rr in ((1.25, 1.25), (1.25, 1.5), (1.5, 1.75), (1.75, 1.5)):
        overrides = stops((2.0, 2.0), (vp_atr, vp_rr))
        candidates.append(Candidate(f"grid_vp{vp_atr:g}x_rr{vp_rr:g}", overrides))

    t175_rr225 = stops((1.75, 2.25), (1.5, 1.5))
    risk5 = {
        "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.05),
        "MAX_RISK_PCT": 0.06,
    }
    risk45 = {
        "DEFAULT_RISK_PCT_BY_CLASS": _crypto_dict("DEFAULT_RISK_PCT_BY_CLASS", 0.045),
        "MAX_RISK_PCT": 0.055,
    }
    for pos_pct in (0.25, 0.30, 0.35):
        candidates.append(Candidate(
            f"grid_t1.75x_rr2.25_s3_pos{int(pos_pct * 100)}",
            t175_rr225,
            {"max_position_pct": pos_pct},
        ))
    candidates.extend([
        Candidate("grid_t1.75x_rr2.25_s3_risk5", {**t175_rr225, **risk5}),
        Candidate("grid_t1.75x_rr2.25_s3_risk45", {**t175_rr225, **risk45}),
        Candidate("grid_t1.75x_rr2.25_s3_pos30_risk5", {**t175_rr225, **risk5}, {
            "max_position_pct": 0.30,
        }),
        Candidate("grid_t1.75x_rr2.25_s3_pos35_risk45", {**t175_rr225, **risk45}, {
            "max_position_pct": 0.35,
        }),
    ])

    return candidates


def _print_summary(rows: list[dict[str, Any]], limit: int) -> None:
    oos_rows = [row for row in rows if row["period"] == "OOS"]
    oos_rows.sort(key=lambda row: float(row["oos_score"]), reverse=True)

    print("\n=== OOS ranking ===")
    print("label                         robust oos   score  WFavg W  CAGR    PF    Sharpe  DD      T/yr  reason")
    for row in oos_rows[:limit]:
        print(
            f"{row['candidate']:<29} "
            f"{str(row['passes_robust_gate']):<6} "
            f"{str(row['passes_oos_gate']):<5} "
            f"{float(row['oos_score']):>6.2f} "
            f"{float(row['wf_avg_score']):>6.2f} "
            f"{str(row['wf_wins_vs_baseline']):>1} "
            f"{row['annual_return_pct']:>6.2f} "
            f"{row['profit_factor']:>5.3f} "
            f"{row['sharpe_ratio']:>7.3f} "
            f"{row['max_drawdown_pct']:>7.2f} "
            f"{row['trades_per_year']:>6.1f}  "
            f"{row['robust_gate_reason']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto OOS-first optimizer")
    parser.add_argument("--quick", action="store_true",
                        help="run only baseline and the first few conservative candidates")
    parser.add_argument("--local-grid", action="store_true",
                        help="run a focused local grid around Crypto stop/RR/score settings")
    parser.add_argument("--limit", type=int, default=8,
                        help="number of ranked OOS rows to print")
    parser.add_argument("--output", default="output/crypto_oos_optimize.csv",
                        help="CSV path for all IS/OOS/FULL results")
    args = parser.parse_args()

    print("Building Crypto indicator/signals cache...")
    base = _build_inputs(use_vp=True)
    candidates = _local_grid_candidates() if args.local_grid else _candidates()
    if args.quick:
        keep = {
            "baseline_current", "score4", "hold21", "pos30",
            "sym_wr_40_3_20", "sym_wr_45_5_30", "risk5pct",
        }
        candidates = [cand for cand in candidates if cand.label in keep]

    rows: list[dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, 1):
        print(f"[{idx:02d}/{len(candidates):02d}] {candidate.label}")
        rows.extend(_candidate_rows(candidate, base))

    _annotate_robust_gate(rows)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    _print_summary(rows, args.limit)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
