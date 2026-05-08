"""Overfit checks for Crypto previous-lookback Top100 candidates.

The goal is to test whether the current Top100 improvements survive checks
that were not used to choose the candidates:

1. Nested walk-forward candidate selection:
   select the best frozen candidate on past years, then evaluate the next
   unseen period.

2. Neighborhood stability:
   perturb the volume Top-N universe and symbol win-rate threshold around the
   current best candidate.

This script is intentionally research-only. It does not modify the production
strategy configuration.
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scripts import crypto_prev3y_top100_optimize as opt
from scripts.crypto_prev3y_market_cap_universe_backtest import RANK_BY_COLUMNS
from src.database import get_all_symbols, load_prices


DEFAULT_END = "2026-05-07"


@dataclass(frozen=True)
class UniverseKey:
    rank_by: str
    top_n: int
    lookback_years: int = 3
    min_history_days: int = 180

    @property
    def label(self) -> str:
        metric = "volume" if self.rank_by == "volume_24h" else "mcap"
        return f"{metric}_top{self.top_n}_lb{self.lookback_years}"


@dataclass(frozen=True)
class FrozenCandidate:
    label: str
    universe: UniverseKey
    overrides: dict[str, Any]
    profile_overrides: dict[str, Any] | None = None


def _to_bybit_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    if s.startswith("BYBIT:") and s.endswith(".P"):
        return s
    if s.endswith("USDT"):
        return f"BYBIT:{s}.P"
    return f"BYBIT:{s}USDT.P"


def _ranked_universe(year: int, universe: UniverseKey) -> pd.DataFrame:
    if universe.rank_by not in RANK_BY_COLUMNS:
        raise ValueError(f"rank_by must be one of: {', '.join(RANK_BY_COLUMNS)}")
    rank_col = RANK_BY_COLUMNS[universe.rank_by]
    start = f"{year - universe.lookback_years}-01-01"
    end = f"{year - 1}-12-31"
    conn = sqlite3.connect(config.DB_PATH)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='crypto_market_cap_rankings'"
        ).fetchone()
        if exists is None:
            return pd.DataFrame()
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
            params=(start, end, int(universe.top_n)),
        )
    finally:
        conn.close()
    if df.empty:
        return df
    df["bybit_symbol"] = df["symbol"].map(_to_bybit_symbol)
    return df


def _eligible_by_year(start: str,
                      end: str,
                      universe: UniverseKey) -> tuple[dict[int, set[str]], set[str], list[dict[str, Any]]]:
    available = set(get_all_symbols())
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    allowed_by_year: dict[int, set[str]] = {}
    all_symbols: set[str] = set()
    summary: list[dict[str, Any]] = []
    history_cache: dict[str, pd.DataFrame] = {}

    for year in range(start_ts.year, end_ts.year + 1):
        ranked = _ranked_universe(year, universe)
        year_start = pd.Timestamp(f"{year}-01-01")
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
            if len(df.loc[df.index < year_start]) < universe.min_history_days:
                continue
            eligible.add(sym)
        allowed_by_year[year] = eligible
        all_symbols.update(eligible)
        summary.append({
            "universe": universe.label,
            "year": year,
            "ranked": int(len(ranked)),
            "bybit_available": int(len(set(bybit_available))),
            "eligible": int(len(eligible)),
        })
    return allowed_by_year, all_symbols, summary


def _prepare_universe_cache(start: str,
                            end: str,
                            universe: UniverseKey) -> dict[str, Any]:
    allowed_by_year, tradable, summary = _eligible_by_year(start, end, universe)
    if not tradable:
        raise RuntimeError(f"No tradable symbols for {universe.label}")
    symbols = set(tradable)
    market_symbol = getattr(config, "CRYPTO_MARKET_SYMBOL", "BYBIT:BTCUSDT.P")
    if market_symbol in set(get_all_symbols()):
        symbols.add(market_symbol)
    print(f"Building cache: {universe.label} tradable={len(tradable)} context={len(symbols)}")
    base = opt._build_inputs(symbols)
    return {
        "universe": universe,
        "allowed_by_year": allowed_by_year,
        "tradable": tradable,
        "summary": summary,
        "base": base,
    }


def _run_candidate(cache: dict[str, Any],
                   candidate: FrozenCandidate,
                   period: str,
                   start: str,
                   end: str) -> dict[str, Any]:
    saved = opt._apply_overrides(candidate.overrides)
    try:
        trades, metrics = opt._run_period(
            cache["base"],
            cache["allowed_by_year"],
            start,
            end,
            candidate.profile_overrides,
        )
    finally:
        opt._restore_overrides(saved)

    row = opt._row(
        opt.Candidate(candidate.label, candidate.overrides, candidate.profile_overrides),
        period,
        start,
        end,
        trades,
        metrics,
        candidate.universe.rank_by,
    )
    row["universe"] = candidate.universe.label
    row["top_n"] = candidate.universe.top_n
    row["lookback_years"] = candidate.universe.lookback_years
    row["min_history_days"] = candidate.universe.min_history_days
    row["profile_overrides"] = repr(candidate.profile_overrides or {})
    return row


def _frozen_candidates() -> list[FrozenCandidate]:
    mcap100 = UniverseKey("market_cap", 100)
    volume100 = UniverseKey("volume_24h", 100)
    return [
        FrozenCandidate("mcap_baseline", mcap100, {}),
        FrozenCandidate("mcap_cap8", mcap100, {}, {"max_total_positions": 8}),
        FrozenCandidate("volume_baseline", volume100, {}),
        FrozenCandidate("volume_sym_filter_off", volume100, {
            "SYM_MIN_WINRATE_BY_CLASS": opt._crypto_dict("SYM_MIN_WINRATE_BY_CLASS", 0.0),
        }),
        FrozenCandidate("volume_stops_t1.75_rr2", volume100, opt._stops((1.75, 2.0), (1.5, 1.5))),
    ]


def _score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("score", -999.0))
    except (TypeError, ValueError):
        return -999.0


def _passes(row: dict[str, Any]) -> bool:
    value = row.get("passes_gate", False)
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _nested_splits(end_date: str) -> list[dict[str, str]]:
    splits = [
        {
            "split": "select_2022_2023_test_2024H2",
            "train_start": "2022-01-01",
            "train_end": "2023-12-31",
            "test_start": "2024-05-01",
            "test_end": "2024-12-31",
        },
        {
            "split": "select_2022_2024_test_2025",
            "train_start": "2022-01-01",
            "train_end": "2024-12-31",
            "test_start": "2025-01-01",
            "test_end": "2025-12-31",
        },
    ]
    if pd.Timestamp(end_date) >= pd.Timestamp("2026-01-01"):
        splits.append({
            "split": "select_2022_2025_test_2026YTD",
            "train_start": "2022-01-01",
            "train_end": "2025-12-31",
            "test_start": "2026-01-01",
            "test_end": end_date,
        })
    return splits


def run_nested(end_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = _frozen_candidates()
    global_start = "2022-01-01"
    caches: dict[UniverseKey, dict[str, Any]] = {}
    for universe in sorted({c.universe for c in candidates}, key=lambda u: u.label):
        caches[universe] = _prepare_universe_cache(global_start, end_date, universe)

    candidate_rows: list[dict[str, Any]] = []
    nested_rows: list[dict[str, Any]] = []
    universe_rows: list[dict[str, Any]] = [
        rec for cache in caches.values() for rec in cache["summary"]
    ]

    for split in _nested_splits(end_date):
        train_rows: list[dict[str, Any]] = []
        test_rows: list[dict[str, Any]] = []
        for candidate in candidates:
            cache = caches[candidate.universe]
            train = _run_candidate(
                cache,
                candidate,
                f"{split['split']}|TRAIN",
                split["train_start"],
                split["train_end"],
            )
            test = _run_candidate(
                cache,
                candidate,
                f"{split['split']}|TEST",
                split["test_start"],
                split["test_end"],
            )
            train_rows.append(train)
            test_rows.append(test)
            candidate_rows.extend([train, test])

        selected_train = max(train_rows, key=_score)
        selected_test = next(
            row for row in test_rows
            if row["candidate"] == selected_train["candidate"]
        )
        nested_rows.append({
            "split": split["split"],
            "train_start": split["train_start"],
            "train_end": split["train_end"],
            "test_start": split["test_start"],
            "test_end": split["test_end"],
            "selected_candidate": selected_train["candidate"],
            "selected_universe": selected_train["universe"],
            "train_score": selected_train["score"],
            "train_total_return_pct": selected_train["total_return_pct"],
            "train_profit_factor": selected_train["profit_factor"],
            "train_sharpe_ratio": selected_train["sharpe_ratio"],
            "train_max_drawdown_pct": selected_train["max_drawdown_pct"],
            "train_passes_gate": selected_train["passes_gate"],
            "test_score": selected_test["score"],
            "test_total_return_pct": selected_test["total_return_pct"],
            "test_annual_return_pct": selected_test["annual_return_pct"],
            "test_max_drawdown_pct": selected_test["max_drawdown_pct"],
            "test_profit_factor": selected_test["profit_factor"],
            "test_sharpe_ratio": selected_test["sharpe_ratio"],
            "test_calmar_ratio": selected_test["calmar_ratio"],
            "test_total_trades": selected_test["total_trades"],
            "test_passes_gate": selected_test["passes_gate"],
            "overfit_flag": bool(_passes(selected_train) and not _passes(selected_test)),
        })
        print(
            f"{split['split']}: selected={selected_train['candidate']} "
            f"train_score={selected_train['score']} "
            f"test_ret={selected_test['total_return_pct']} "
            f"test_pf={selected_test['profit_factor']} "
            f"test_pass={selected_test['passes_gate']}"
        )
    return candidate_rows, nested_rows, universe_rows


def _stability_candidates(top_ns: list[int],
                          thresholds: list[float],
                          lookbacks: list[int]) -> list[FrozenCandidate]:
    out: list[FrozenCandidate] = []
    for lookback in lookbacks:
        for top_n in top_ns:
            universe = UniverseKey("volume_24h", int(top_n), lookback_years=int(lookback))
            for threshold in thresholds:
                if threshold <= 0:
                    label = f"volume_top{top_n}_lb{lookback}_sym_off"
                else:
                    label = f"volume_top{top_n}_lb{lookback}_sym_{threshold:.2f}".replace(".", "p")
                out.append(FrozenCandidate(label, universe, {
                    "SYM_MIN_WINRATE_BY_CLASS": opt._crypto_dict("SYM_MIN_WINRATE_BY_CLASS", float(threshold)),
                }))
    return out


def run_stability(end_date: str,
                  top_ns: list[int],
                  thresholds: list[float],
                  lookbacks: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    periods = {
        "OOS_ALL": ("2024-05-01", end_date),
        "OOS_2024H2": ("2024-05-01", "2024-12-31"),
        "OOS_2025": ("2025-01-01", "2025-12-31"),
    }
    if pd.Timestamp(end_date) >= pd.Timestamp("2026-01-01"):
        periods["OOS_2026YTD"] = ("2026-01-01", end_date)

    candidates = _stability_candidates(top_ns, thresholds, lookbacks)
    caches: dict[UniverseKey, dict[str, Any]] = {}
    for universe in sorted({c.universe for c in candidates}, key=lambda u: (u.lookback_years, u.top_n)):
        caches[universe] = _prepare_universe_cache("2024-05-01", end_date, universe)

    rows: list[dict[str, Any]] = []
    universe_rows: list[dict[str, Any]] = [
        rec for cache in caches.values() for rec in cache["summary"]
    ]
    for idx, candidate in enumerate(candidates, 1):
        print(f"stability [{idx:02d}/{len(candidates):02d}] {candidate.label}")
        cache = caches[candidate.universe]
        for period, (start, end) in periods.items():
            rows.append(_run_candidate(cache, candidate, period, start, end))
    return rows, universe_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _parse_float_list(text: str) -> list[float]:
    return [float(part.strip()) for part in text.split(",") if part.strip()]


def _parse_int_list(text: str) -> list[int]:
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def _print_stability_summary(rows: list[dict[str, Any]]) -> None:
    all_rows = [row for row in rows if row["period"] == "OOS_ALL"]
    all_rows.sort(key=_score, reverse=True)
    print("\n=== Stability OOS_ALL ranking ===")
    print("candidate                    ret%    PF    Shp   MDD   pass  2024PF 2025PF 2026PF")
    by_candidate: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_candidate.setdefault(row["candidate"], {})[row["period"]] = row
    for row in all_rows[:12]:
        periods = by_candidate[row["candidate"]]
        print(
            f"{row['candidate']:<28} "
            f"{float(row.get('total_return_pct', 0) or 0):>6.1f} "
            f"{float(row.get('profit_factor', 0) or 0):>5.3f} "
            f"{float(row.get('sharpe_ratio', 0) or 0):>5.2f} "
            f"{float(row.get('max_drawdown_pct', 0) or 0):>6.1f} "
            f"{str(row.get('passes_gate')):<5} "
            f"{float(periods.get('OOS_2024H2', {}).get('profit_factor', 0) or 0):>6.3f} "
            f"{float(periods.get('OOS_2025', {}).get('profit_factor', 0) or 0):>6.3f} "
            f"{float(periods.get('OOS_2026YTD', {}).get('profit_factor', 0) or 0):>6.3f}"
        )


def _suffix(text: str) -> str:
    if not text:
        return ""
    return text if text.startswith("_") else f"_{text}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Top100 overfit checks.")
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--top-ns", default="75,100,125")
    parser.add_argument("--thresholds", default="0,0.35,0.40,0.45")
    parser.add_argument("--lookbacks", default="3")
    parser.add_argument("--skip-nested", action="store_true")
    parser.add_argument("--skip-stability", action="store_true")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--suffix", default="", help="Suffix for output CSV filenames.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    suffix = _suffix(args.suffix)
    if not args.skip_nested:
        candidate_rows, nested_rows, universe_rows = run_nested(args.end_date)
        _write_csv(out_dir / f"crypto_top100_candidate_periods{suffix}.csv", candidate_rows)
        _write_csv(out_dir / f"crypto_top100_nested_walk_forward{suffix}.csv", nested_rows)
        _write_csv(out_dir / f"crypto_top100_nested_universe_summary{suffix}.csv", universe_rows)
        print(f"\nSaved nested outputs to {out_dir}")

    if not args.skip_stability:
        stability_rows, universe_rows = run_stability(
            args.end_date,
            _parse_int_list(args.top_ns),
            _parse_float_list(args.thresholds),
            _parse_int_list(args.lookbacks),
        )
        _write_csv(out_dir / f"crypto_top100_stability_grid{suffix}.csv", stability_rows)
        _write_csv(out_dir / f"crypto_top100_stability_universe_summary{suffix}.csv", universe_rows)
        _print_stability_summary(stability_rows)
        print(f"\nSaved stability outputs to {out_dir}")


if __name__ == "__main__":
    main()
