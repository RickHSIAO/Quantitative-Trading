"""Forward monitor for the frozen Crypto Top125 volume candidate.

The candidate is intentionally frozen after EXP-010:

  - universe: previous 3-year average CMC volume_24h Top125
  - symbol WR threshold: 0.35
  - strategy parameters: current baseline

Default forward start is 2026-05-08.  Do not use this script to tune the
candidate on the forward period; it is only a recurring monitor.
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scripts import crypto_prev3y_top100_optimize as opt
from scripts import crypto_top100_overfit_checks as checks


DEFAULT_START = "2026-05-08"
DEFAULT_MIN_TRADES = 50
DEFAULT_MIN_DAYS = 90


def _latest_crypto_date() -> str:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT MAX(date) FROM prices WHERE asset_type='Crypto'"
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        raise RuntimeError("No Crypto prices in local DB.")
    return str(row[0])


def _candidate(top_n: int,
               lookback_years: int,
               sym_wr_threshold: float) -> checks.FrozenCandidate:
    universe = checks.UniverseKey(
        "volume_24h",
        int(top_n),
        lookback_years=int(lookback_years),
        min_history_days=180,
    )
    return checks.FrozenCandidate(
        f"forward_volume_top{top_n}_lb{lookback_years}_sym_{sym_wr_threshold:.2f}".replace(".", "p"),
        universe,
        {
            "SYM_MIN_WINRATE_BY_CLASS": opt._crypto_dict(
                "SYM_MIN_WINRATE_BY_CLASS",
                float(sym_wr_threshold),
            ),
        },
    )


def _monitor_status(metrics: dict[str, Any],
                    start: str,
                    end: str,
                    min_trades: int,
                    min_days: int) -> tuple[str, str]:
    trades = int(metrics.get("total_trades", 0) or 0)
    days = max((pd.Timestamp(end) - pd.Timestamp(start)).days + 1, 0)
    if days < min_days and trades < min_trades:
        return (
            "pending",
            f"forward sample too small: days={days}/{min_days}, trades={trades}/{min_trades}",
        )

    pf = float(metrics.get("profit_factor", 0.0) or 0.0)
    sharpe = float(metrics.get("sharpe_ratio", 0.0) or 0.0)
    mdd = float(metrics.get("max_drawdown_pct", -999.0) or -999.0)
    if pf >= 1.15 and sharpe >= 0.70 and mdd >= -40.0:
        return "pass", "forward thresholds passed"
    if pf < 1.0 or mdd < -45.0:
        return "fail", "forward PF below 1.0 or MDD worse than -45%"
    return "watch", "forward sample mature but below promotion thresholds"


def _trade_rows(trades: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in trades:
        rows.append({
            "symbol": t.symbol,
            "strategy": t.strategy,
            "direction": t.direction,
            "asset_type": t.asset_type,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date or "",
            "entry_price": t.entry_price,
            "exit_price": t.exit_price if t.exit_price is not None else "",
            "quantity": t.quantity,
            "pnl": t.pnl if t.pnl is not None else "",
            "return_pct": t.return_pct if t.return_pct is not None else "",
            "holding_days": t.holding_days if t.holding_days is not None else "",
            "r_multiple": t.r_multiple if t.r_multiple is not None else "",
            "exit_reason": t.exit_reason or "",
        })
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor frozen Top125 volume forward candidate.")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default="")
    parser.add_argument("--top-n", type=int, default=125)
    parser.add_argument("--lookback-years", type=int, default=3)
    parser.add_argument("--sym-wr-threshold", type=float, default=0.35)
    parser.add_argument("--min-trades", type=int, default=DEFAULT_MIN_TRADES)
    parser.add_argument("--min-days", type=int, default=DEFAULT_MIN_DAYS)
    parser.add_argument("--summary-output", default="output/crypto_top100_forward_monitor_summary.csv")
    parser.add_argument("--trades-output", default="output/crypto_top100_forward_monitor_trades.csv")
    args = parser.parse_args()

    end = args.end_date or _latest_crypto_date()
    if pd.Timestamp(end) < pd.Timestamp(args.start_date):
        raise RuntimeError(f"end-date {end} is before forward start {args.start_date}")

    candidate = _candidate(args.top_n, args.lookback_years, args.sym_wr_threshold)
    cache = checks._prepare_universe_cache(args.start_date, end, candidate.universe)
    saved = opt._apply_overrides(candidate.overrides)
    try:
        trades, metrics = opt._run_period(
            cache["base"],
            cache["allowed_by_year"],
            args.start_date,
            end,
            candidate.profile_overrides,
        )
    finally:
        opt._restore_overrides(saved)

    status, reason = _monitor_status(
        metrics,
        args.start_date,
        end,
        args.min_trades,
        args.min_days,
    )
    summary = {
        "candidate": candidate.label,
        "status": status,
        "status_reason": reason,
        "start_date": args.start_date,
        "end_date": end,
        "top_n": args.top_n,
        "lookback_years": args.lookback_years,
        "sym_wr_threshold": args.sym_wr_threshold,
        "eligible_symbols": len(cache["tradable"]),
        "total_return_pct": metrics.get("total_return_pct", ""),
        "annual_return_pct": metrics.get("annual_return_pct", ""),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", ""),
        "profit_factor": metrics.get("profit_factor", ""),
        "sharpe_ratio": metrics.get("sharpe_ratio", ""),
        "calmar_ratio": metrics.get("calmar_ratio", ""),
        "win_rate": (metrics.get("win_rate", "") * 100.0 if metrics.get("win_rate", "") != "" else ""),
        "avg_r_multiple": metrics.get("avg_r_multiple", ""),
        "total_trades": metrics.get("total_trades", ""),
        "min_trades_for_decision": args.min_trades,
        "min_days_for_decision": args.min_days,
    }

    _write_csv(Path(args.summary_output), [summary])
    _write_csv(Path(args.trades_output), _trade_rows(list(trades)))

    print("\nFrozen Top100 forward monitor")
    print(f"candidate: {summary['candidate']}")
    print(f"period: {args.start_date} -> {end}")
    print(f"eligible symbols: {summary['eligible_symbols']}")
    print(
        f"status: {status} ({reason}) | "
        f"return={summary['total_return_pct']} PF={summary['profit_factor']} "
        f"Sharpe={summary['sharpe_ratio']} MDD={summary['max_drawdown_pct']} "
        f"trades={summary['total_trades']}"
    )
    print(f"Saved: {args.summary_output}")
    print(f"Saved: {args.trades_output}")


if __name__ == "__main__":
    main()
