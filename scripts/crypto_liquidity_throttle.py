"""EXP-006 Crypto PIT universe liquidity throttle test.

Sweeps the minimum 90-day median dollar-volume filter for the Bybit-only
point-in-time universe. Strategy signals, parameters, costs, and sizing are
unchanged.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import crypto_point_in_time_universe as pit


DEFAULT_START = "2024-05-01"
DEFAULT_END = "2026-05-07"


def _run_variant(mode: str,
                 threshold: float,
                 data: dict,
                 signals: dict,
                 type_map: dict,
                 rankings,
                 start: str,
                 end: str,
                 min_history_days: int) -> dict[str, Any]:
    if mode == "static_pit_top100":
        as_of = (pit.pd.Timestamp(start) - pit.pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        selection = pit._select_from_rankings(
            mode,
            rankings,
            data,
            as_of,
            start,
            end,
            min_history_days,
            threshold,
        )
        if selection.status != "ok":
            return _empty_row(mode, threshold, selection.status, len(selection.symbols), selection.notes)
        trades, metrics = pit._run_universe(
            data,
            signals,
            type_map,
            start,
            end,
            pit._date_allowed_static(start, end, selection.symbols),
        )
        return _row(mode, threshold, selection.status, len(selection.symbols), trades, metrics, selection.notes)

    if mode == "rolling_pit_top100_quarterly":
        selections = pit._quarter_selections(
            rankings,
            data,
            start,
            end,
            min_history_days,
            threshold,
        )
        ok = selections and all(sel.status == "ok" for sel in selections)
        if not ok:
            status = "incomplete_rolling_universe"
            notes = "; ".join(f"{sel.rebalance_date}:{sel.status}" for sel in selections)
            return _empty_row(mode, threshold, status, 0, notes)
        trades, metrics = pit._run_universe(
            data,
            signals,
            type_map,
            start,
            end,
            pit._date_allowed_rolling(start, end, selections),
        )
        avg_symbols = int(np.mean([len(sel.symbols) for sel in selections]))
        return _row(
            mode,
            threshold,
            "ok",
            avg_symbols,
            trades,
            metrics,
            "Quarterly PIT universe with liquidity throttle.",
        )

    raise ValueError(f"Unknown mode: {mode}")


def _empty_row(mode: str, threshold: float, status: str, universe_symbols: int, notes: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "min_90d_dollar_volume": threshold,
        "status": status,
        "total_return": "",
        "annual_return": "",
        "MDD": "",
        "PF": "",
        "Sharpe": "",
        "Calmar": "",
        "win_rate": "",
        "avg_R": "",
        "trades": "",
        "universe_symbols": universe_symbols,
        "number_of_symbols_traded": 0,
        "top_contributors": "",
        "worst_contributors": "",
        "notes": notes,
    }


def _row(mode: str,
         threshold: float,
         status: str,
         universe_symbols: int,
         trades: list[Any],
         metrics: dict[str, Any],
         notes: str) -> dict[str, Any]:
    top, worst, traded_symbols = pit._symbol_contributors(trades)
    return {
        "mode": mode,
        "min_90d_dollar_volume": threshold,
        "status": status,
        "total_return": metrics.get("total_return_pct", ""),
        "annual_return": metrics.get("annual_return_pct", ""),
        "MDD": metrics.get("max_drawdown_pct", ""),
        "PF": metrics.get("profit_factor", ""),
        "Sharpe": metrics.get("sharpe_ratio", ""),
        "Calmar": metrics.get("calmar_ratio", ""),
        "win_rate": (metrics.get("win_rate", "") * 100.0 if metrics.get("win_rate", "") != "" else ""),
        "avg_R": metrics.get("avg_r_multiple", ""),
        "trades": metrics.get("total_trades", ""),
        "universe_symbols": universe_symbols,
        "number_of_symbols_traded": traded_symbols,
        "top_contributors": top,
        "worst_contributors": worst,
        "notes": notes,
    }


def _parse_thresholds(text: str) -> list[float]:
    return [float(part.strip()) for part in text.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EXP-006 liquidity throttle sweep.")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--ranking-csv", default=pit.DEFAULT_RANKING_CSV)
    parser.add_argument("--min-history-days", type=int, default=180)
    parser.add_argument(
        "--thresholds",
        default="0,1000000,5000000,10000000,25000000,50000000",
        help="Comma-separated 90-day median dollar-volume thresholds.",
    )
    parser.add_argument("--output", default="output/crypto_liquidity_throttle.csv")
    args = parser.parse_args()

    rankings = pit._load_rankings(Path(args.ranking_csv))
    raw_data = pit._load_all_crypto_data()
    data, signals, type_map = pit._build_signals(raw_data)
    thresholds = _parse_thresholds(args.thresholds)

    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        for mode in ("static_pit_top100", "rolling_pit_top100_quarterly"):
            row = _run_variant(
                mode,
                threshold,
                data,
                signals,
                type_map,
                rankings,
                args.start_date,
                args.end_date,
                args.min_history_days,
            )
            rows.append(row)
            print(
                f"{mode:<30} threshold={threshold:>12.0f} "
                f"return={row['total_return']} PF={row['PF']} "
                f"Sharpe={row['Sharpe']} MDD={row['MDD']} "
                f"trades={row['trades']} symbols={row['number_of_symbols_traded']}"
            )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
