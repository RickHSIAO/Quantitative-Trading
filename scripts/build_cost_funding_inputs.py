from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.costs.symbol_mapping import to_funding_symbol, to_perp_symbol


BASELINE_RUN_ID = "20260513_run008"
DEFAULT_POSITIONS = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
DEFAULT_BASELINE = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
DEFAULT_UNIVERSE = Path("data/crypto/universe_membership.parquet")
DEFAULT_FUNDING = Path("data/crypto/funding_rates.parquet")
DEFAULT_REPORT_DIR = Path("outputs/data_quality/funding_coverage")
DEFAULT_LOG_DIR = Path("outputs/logs/cost_inputs")
DEFAULT_CACHE_DIR = Path("data/cache/funding/bybit_api")
BYBIT_FUNDING_API = "https://api.bybit.com/v5/market/funding/history"
BYBIT_INSTRUMENTS_API = "https://api.bybit.com/v5/market/instruments-info"
RANDOM_SEED = 0

FUNDING_COLUMNS = [
    "timestamp",
    "symbol",
    "exchange",
    "funding_rate",
    "interval_hours",
    "source",
    "is_proxy",
]


@dataclass(frozen=True)
class FundingSourceStatus:
    local_sources: list[str]
    bybit_api_smoke_status: str
    bybit_api_url: str


@dataclass
class ApiMetrics:
    request_count: int = 0
    cache_hit_count: int = 0
    retry_count: int = 0
    api_error_count: int = 0
    symbols_failed_count: int = 0


def main() -> int:
    args = parse_args()
    if args.phase2_dryrun:
        return run_phase2_dryrun(args)
    if args.phase2_full_fetch:
        return run_phase2_full_fetch(args)

    run_date = args.run_date
    report_path = args.report_dir / f"{run_date}_funding_coverage_report.csv"
    summary_path = args.report_dir / f"{run_date}_funding_coverage_summary.json"
    log_path = args.log_dir / f"{run_date}_build.log"

    args.report_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)

    source_status = discover_funding_sources(args.api_smoke)
    funding_df = None
    funding_schema_errors: list[str] = []
    if args.funding_path.exists():
        funding_df = pd.read_parquet(args.funding_path)
        funding_schema_errors = validate_funding_rates_schema(funding_df)

    coverage_report, summary = build_coverage_report(
        positions_path=args.positions,
        baseline_path=args.baseline,
        funding_df=funding_df if not funding_schema_errors else None,
    )
    summary.update({
        "baseline_run_id": BASELINE_RUN_ID,
        "funding_rates_path": str(args.funding_path),
        "funding_rates_exists": args.funding_path.exists(),
        "funding_schema_errors": funding_schema_errors,
        "funding_source_primary": primary_funding_source(source_status),
        "funding_source_candidates": source_status.local_sources,
        "bybit_api_smoke_status": source_status.bybit_api_smoke_status,
        "bybit_api_url": source_status.bybit_api_url,
        "phase1_status": determine_phase1_status(summary, source_status, funding_schema_errors),
    })

    coverage_report.to_csv(report_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_build_log(log_path, summary, args)

    print(json.dumps({
        "status": summary["phase1_status"],
        "coverage_report": str(report_path),
        "coverage_summary": str(summary_path),
        "build_log": str(log_path),
    }, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TASK-002a Phase 1 cost/funding input scaffolding.")
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--funding-path", type=Path, default=DEFAULT_FUNDING)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--run-date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--phase2-dryrun", action="store_true")
    parser.add_argument("--phase2-full-fetch", action="store_true")
    parser.add_argument("--dryrun-start", default="2024-04-01T00:00:00Z")
    parser.add_argument("--dryrun-end", default="2024-04-07T23:59:59Z")
    parser.add_argument("--dryrun-buffer-days", type=int, default=1)
    parser.add_argument("--full-start", default="2024-04-01T00:00:00Z")
    parser.add_argument("--full-end", default="2026-04-30T23:59:59Z")
    parser.add_argument("--full-fetch-start", default="2024-03-31T00:00:00Z")
    parser.add_argument("--full-fetch-end", default="2026-05-01T00:00:00Z")
    parser.add_argument("--full-window-days", type=int, default=50)
    parser.add_argument("--request-interval-seconds", type=float, default=0.5)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument(
        "--api-smoke",
        action="store_true",
        help="Check whether Bybit public funding-history API returns a sample BTCUSDT record.",
    )
    return parser.parse_args()


def run_phase2_dryrun(args: argparse.Namespace) -> int:
    random.seed(RANDOM_SEED)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    run_date = args.run_date
    report_path = args.report_dir / f"{run_date}_phase2_dryrun_coverage_report.csv"
    summary_path = args.report_dir / f"{run_date}_phase2_dryrun_coverage_summary.json"
    log_path = args.log_dir / f"{run_date}_phase2_dryrun.log"
    dryrun_parquet_path = args.report_dir / f"{run_date}_phase2_dryrun_funding_rates.parquet"

    dry_start = parse_utc(args.dryrun_start)
    dry_end = parse_utc(args.dryrun_end)
    fetch_start = dry_start - timedelta(days=args.dryrun_buffer_days)
    fetch_end = dry_end + timedelta(days=args.dryrun_buffer_days)

    positions = pd.read_parquet(args.positions)
    universe = pd.read_parquet(args.universe)
    dry_symbols = choose_dryrun_symbols(positions, dry_start, dry_end)
    mapping_result = pit_symbol_mapping_integration(universe)

    metrics = ApiMetrics()
    api_errors: list[dict[str, Any]] = []
    symbol_failures: list[dict[str, Any]] = []
    cache_files: list[Path] = []
    frames: list[pd.DataFrame] = []

    for perp_symbol in dry_symbols:
        raw_symbol = to_funding_symbol(perp_symbol)
        try:
            interval_hours, instrument_cache = fetch_interval_hours(
                raw_symbol=raw_symbol,
                args=args,
                metrics=metrics,
                api_errors=api_errors,
            )
            if instrument_cache is not None:
                cache_files.append(instrument_cache)
            payload, funding_cache = fetch_funding_history(
                raw_symbol=raw_symbol,
                start=fetch_start,
                end=fetch_end,
                args=args,
                metrics=metrics,
                api_errors=api_errors,
            )
            if funding_cache is not None:
                cache_files.append(funding_cache)
            frames.append(parse_funding_payload(payload, raw_symbol, interval_hours, dry_start, dry_end))
        except Exception as exc:
            symbol_failures.append({"symbol": perp_symbol, "error": f"{type(exc).__name__}: {exc}"})

    metrics.symbols_failed_count = len(symbol_failures)
    funding_df = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=FUNDING_COLUMNS)
    )
    funding_df = normalize_funding_schema(funding_df)
    schema_errors = validate_funding_rates_schema(funding_df)
    dryrun_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    write_funding_rates_parquet(funding_df, dryrun_parquet_path)

    position_report, position_summary = build_scope_coverage(
        scope_name="active_position",
        active_pairs=active_position_pairs(positions, dry_start, dry_end),
        funding_df=funding_df,
        start=dry_start,
        end=dry_end,
    )
    pit_report, pit_summary = build_scope_coverage(
        scope_name="active_pit",
        active_pairs=active_pit_pairs(universe, dry_start, dry_end),
        funding_df=funding_df,
        start=dry_start,
        end=dry_end,
    )
    coverage_report = pd.concat([position_report, pit_report], ignore_index=True)
    coverage_report.to_csv(report_path, index=False)

    live_diff = live_diff_check(funding_df, args, metrics, api_errors, sample_size=10)
    unit_check = funding_unit_check(funding_df)
    raw_cache_hash = hash_paths(sorted(set(cache_files), key=str))
    data_snapshot_hash = hash_paths([args.positions, args.baseline, args.universe, dryrun_parquet_path])
    phase_status = determine_phase2_dryrun_status(
        schema_errors=schema_errors,
        mapping_result=mapping_result,
        metrics=metrics,
        live_diff=live_diff,
        symbol_failures=symbol_failures,
    )

    summary = {
        "baseline_run_id": BASELINE_RUN_ID,
        "phase_status": phase_status,
        "dryrun_start_utc": format_utc(dry_start),
        "dryrun_end_utc": format_utc(dry_end),
        "fetch_start_utc": format_utc(fetch_start),
        "fetch_end_utc": format_utc(fetch_end),
        "dryrun_symbols": dry_symbols,
        "dryrun_raw_symbols": [to_funding_symbol(symbol) for symbol in dry_symbols],
        "dryrun_funding_rates_path": str(dryrun_parquet_path),
        "formal_funding_rates_written": False,
        "schema_errors": schema_errors,
        "funding_unit_check": unit_check,
        "mapping_integration": mapping_result,
        "coverage": {
            "active_position": position_summary,
            "active_pit": pit_summary,
        },
        "live_diff_check": live_diff,
        "request_count": metrics.request_count,
        "cache_hit_count": metrics.cache_hit_count,
        "retry_count": metrics.retry_count,
        "api_error_count": metrics.api_error_count,
        "symbols_failed_count": metrics.symbols_failed_count,
        "api_errors": api_errors[:50],
        "symbol_failures": symbol_failures,
        "raw_cache_snapshot_hash": raw_cache_hash,
        "data_snapshot_hash": data_snapshot_hash,
        "git_commit": git_rev_parse(),
        "notes": [
            "Phase 2 dry-run only; no TASK-002 stress executed.",
            "No fake funding or average-value funding was generated.",
            "Dry-run parquet is not the formal data/crypto/funding_rates.parquet.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_phase2_dryrun_log(log_path, summary)

    print(json.dumps({
        "status": phase_status,
        "dryrun_funding_rates": str(dryrun_parquet_path),
        "coverage_report": str(report_path),
        "coverage_summary": str(summary_path),
        "build_log": str(log_path),
    }, indent=2, sort_keys=True))
    return 0


def run_phase2_full_fetch(args: argparse.Namespace) -> int:
    random.seed(RANDOM_SEED)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.funding_path.parent.mkdir(parents=True, exist_ok=True)

    run_date = args.run_date
    report_path = args.report_dir / f"{run_date}_phase2_full_coverage_report.csv"
    summary_path = args.report_dir / f"{run_date}_phase2_full_coverage_summary.json"
    log_path = args.log_dir / f"{run_date}_phase2_full_fetch.log"
    prior_funding_hash = hash_paths([args.funding_path]) if args.funding_path.exists() else None

    active_start = parse_utc(args.full_start)
    active_end = parse_utc(args.full_end)
    fetch_start = parse_utc(args.full_fetch_start)
    fetch_end = parse_utc(args.full_fetch_end)

    positions = pd.read_parquet(args.positions)
    universe = pd.read_parquet(args.universe)
    mapping_result = pit_symbol_mapping_integration(universe)
    pit_symbols = sorted(universe["symbol"].dropna().astype(str).unique())

    metrics = ApiMetrics()
    api_errors: list[dict[str, Any]] = []
    symbol_failures: list[dict[str, Any]] = []
    interval_unclear_symbols: list[dict[str, Any]] = []
    cache_files: list[Path] = []
    frames: list[pd.DataFrame] = []

    total_symbols = len(pit_symbols)
    for index, perp_symbol in enumerate(pit_symbols, start=1):
        if index == 1 or index % 25 == 0:
            print(f"[phase2-full] fetching {index}/{total_symbols}: {perp_symbol}", flush=True)
        raw_symbol = to_funding_symbol(perp_symbol)
        try:
            symbol_df, symbol_cache_files, interval_issue = fetch_full_symbol_funding(
                raw_symbol=raw_symbol,
                active_start=active_start,
                active_end=active_end,
                fetch_start=fetch_start,
                fetch_end=fetch_end,
                args=args,
                metrics=metrics,
                api_errors=api_errors,
            )
            cache_files.extend(symbol_cache_files)
            if interval_issue is not None:
                interval_unclear_symbols.append({"symbol": perp_symbol, "issue": interval_issue})
            if not symbol_df.empty:
                frames.append(symbol_df)
        except Exception as exc:
            symbol_failures.append({"symbol": perp_symbol, "error": f"{type(exc).__name__}: {exc}"})

    metrics.symbols_failed_count = len(symbol_failures)
    funding_df = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=FUNDING_COLUMNS)
    )
    funding_df = normalize_funding_schema(funding_df)
    schema_errors = validate_funding_rates_schema(funding_df)
    write_funding_rates_parquet(funding_df, args.funding_path)
    funding_parquet_hash = hash_paths([args.funding_path])

    position_report, position_summary = build_scope_coverage(
        scope_name="active_position",
        active_pairs=active_position_pairs(positions, active_start, active_end),
        funding_df=funding_df,
        start=active_start,
        end=active_end,
    )
    pit_report, pit_summary = build_scope_coverage(
        scope_name="active_pit",
        active_pairs=active_pit_pairs(universe, active_start, active_end),
        funding_df=funding_df,
        start=active_start,
        end=active_end,
    )
    coverage_report = pd.concat([position_report, pit_report], ignore_index=True)
    coverage_report.to_csv(report_path, index=False)

    live_diff = live_diff_check_by_year(funding_df, args, metrics, api_errors, sample_size=30, min_per_year=5)
    unit_check = funding_unit_check(funding_df)
    outlier_summary = funding_outlier_summary(funding_df)
    continuity_summary = continuity_gap_summary(funding_df, active_start, active_end)
    raw_cache_hash = hash_paths(sorted(set(cache_files), key=str))
    data_snapshot_hash = hash_paths([args.positions, args.baseline, args.universe, args.funding_path])
    phase_status = determine_phase2_full_status(
        schema_errors=schema_errors,
        mapping_result=mapping_result,
        interval_unclear_symbols=interval_unclear_symbols,
        live_diff=live_diff,
        active_pit_coverage=pit_summary["coverage_real_pct"],
    )
    task_status = phase_status

    summary = {
        "baseline_run_id": BASELINE_RUN_ID,
        "phase_status": phase_status,
        "task_002a_overall_status": task_status,
        "active_start_utc": format_utc(active_start),
        "active_end_utc": format_utc(active_end),
        "fetch_start_utc": format_utc(fetch_start),
        "fetch_end_utc": format_utc(fetch_end),
        "symbols_requested_count": len(pit_symbols),
        "symbols_with_funding_rows_count": int(funding_df["symbol"].nunique()) if not funding_df.empty else 0,
        "funding_rows_count": int(len(funding_df)),
        "formal_funding_rates_path": str(args.funding_path),
        "formal_funding_rates_written": True,
        "funding_rates_parquet_hash": funding_parquet_hash,
        "idempotency": {
            "previous_funding_rates_parquet_hash": prior_funding_hash,
            "current_funding_rates_parquet_hash": funding_parquet_hash,
            "hash_consistent_with_previous": (
                None if prior_funding_hash is None else prior_funding_hash == funding_parquet_hash
            ),
        },
        "schema_errors": schema_errors,
        "funding_unit_check": unit_check,
        "mapping_integration": mapping_result,
        "coverage": {
            "active_position": position_summary,
            "active_pit": pit_summary,
        },
        "failed_symbols": symbol_failures,
        "interval_unclear_symbols": interval_unclear_symbols,
        "missing_symbols": missing_symbol_summary(coverage_report),
        "live_diff_check": live_diff,
        "outlier_summary": outlier_summary,
        "continuity_gap_summary": continuity_summary,
        "request_count": metrics.request_count,
        "cache_hit_count": metrics.cache_hit_count,
        "retry_count": metrics.retry_count,
        "api_error_count": metrics.api_error_count,
        "symbols_failed_count": metrics.symbols_failed_count,
        "api_errors": api_errors[:100],
        "raw_cache_snapshot_hash": raw_cache_hash,
        "data_snapshot_hash": data_snapshot_hash,
        "git_commit": git_rev_parse(),
        "notes": [
            "Controlled full fetch only; TASK-002 stress was not executed.",
            "No fake, proxy, average, historical-mean, or random funding rows were generated.",
            "TASK-002 remains BLOCKED pending REVIEW-002a_phase2_full.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_phase2_full_log(log_path, summary)

    print(json.dumps({
        "status": phase_status,
        "task_002a_overall_status": task_status,
        "funding_rates": str(args.funding_path),
        "coverage_report": str(report_path),
        "coverage_summary": str(summary_path),
        "build_log": str(log_path),
    }, indent=2, sort_keys=True))
    return 0


def parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ms(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def choose_dryrun_symbols(positions: pd.DataFrame, dry_start: datetime, dry_end: datetime) -> list[str]:
    positions = positions.copy()
    positions["date"] = pd.to_datetime(positions["date"]).dt.tz_localize("UTC")
    dry_positions = positions[
        (positions["date"] >= pd.Timestamp(dry_start))
        & (positions["date"] <= pd.Timestamp(dry_end))
    ]
    active_all = set(positions["symbol"].dropna().astype(str).unique())
    preferred = [
        "BYBIT:BTCUSDT.P",
        "BYBIT:ETHUSDT.P",
        "BYBIT:1000PEPEUSDT.P",
        "BYBIT:RLUSDUSDT.P",
    ]
    selected = [symbol for symbol in preferred if symbol in active_all]
    for symbol in sorted(dry_positions["symbol"].dropna().astype(str).unique()):
        if len(selected) >= 4:
            break
        if symbol not in selected:
            selected.append(symbol)
    if len(selected) < 4:
        for symbol in sorted(active_all):
            if len(selected) >= 4:
                break
            if symbol not in selected:
                selected.append(symbol)
    return selected[:4]


def pit_symbol_mapping_integration(universe: pd.DataFrame) -> dict[str, Any]:
    symbols = sorted(universe["symbol"].dropna().astype(str).unique())
    failures: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            raw = to_funding_symbol(symbol)
            round_trip = to_perp_symbol(raw)
            if round_trip != symbol:
                failures.append({"symbol": symbol, "error": f"round_trip={round_trip}"})
        except Exception as exc:
            failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "total_symbols": len(symbols),
        "passed_symbols": len(symbols) - len(failures),
        "failed_symbols": len(failures),
        "failures": failures[:50],
    }


def fetch_interval_hours(
    raw_symbol: str,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> tuple[int, Path | None]:
    params = {"category": "linear", "symbol": raw_symbol}
    cache_path = cache_path_for(args.cache_dir, "instruments_info", raw_symbol, params)
    payload = request_json_cached(BYBIT_INSTRUMENTS_API, params, cache_path, args, metrics, api_errors)
    rows = payload.get("result", {}).get("list", [])
    if not rows:
        raise ValueError(f"instruments-info returned no rows for {raw_symbol}")
    funding_interval_minutes = int(rows[0]["fundingInterval"])
    if funding_interval_minutes <= 0 or funding_interval_minutes % 60 != 0:
        raise ValueError(f"unsupported fundingInterval={funding_interval_minutes} for {raw_symbol}")
    return int(funding_interval_minutes / 60), cache_path


def fetch_funding_history(
    raw_symbol: str,
    start: datetime,
    end: datetime,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> tuple[dict[str, Any], Path | None]:
    params = {
        "category": "linear",
        "symbol": raw_symbol,
        "startTime": ms(start),
        "endTime": ms(end),
        "limit": 200,
    }
    cache_path = cache_path_for(args.cache_dir, "funding_history", raw_symbol, params)
    payload = request_json_cached(BYBIT_FUNDING_API, params, cache_path, args, metrics, api_errors)
    return payload, cache_path


def fetch_full_symbol_funding(
    raw_symbol: str,
    active_start: datetime,
    active_end: datetime,
    fetch_start: datetime,
    fetch_end: datetime,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[Path], str | None]:
    cache_files: list[Path] = []
    interval_issue: str | None = None
    interval_hours: int | None = None
    try:
        interval_hours, instrument_cache = fetch_interval_hours(raw_symbol, args, metrics, api_errors)
        if instrument_cache is not None:
            cache_files.append(instrument_cache)
    except Exception as exc:
        interval_issue = f"instruments-info unavailable: {type(exc).__name__}: {exc}"

    window_days = choose_window_days(interval_hours, args.full_window_days)
    frames: list[pd.DataFrame] = []
    current = fetch_start
    while current <= fetch_end:
        window_end = min(fetch_end, current + timedelta(days=window_days) - timedelta(milliseconds=1))
        payload, funding_cache = fetch_funding_history(raw_symbol, current, window_end, args, metrics, api_errors)
        if funding_cache is not None:
            cache_files.append(funding_cache)
        frames.append(parse_funding_payload(payload, raw_symbol, interval_hours or 0, active_start, active_end))
        current = window_end + timedelta(milliseconds=1)

    symbol_df = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=FUNDING_COLUMNS)
    )
    if interval_hours is None and not symbol_df.empty:
        inferred = infer_interval_hours(symbol_df)
        if inferred is None:
            interval_issue = (interval_issue or "") + "; unable to infer interval from funding timestamps"
        else:
            symbol_df["interval_hours"] = inferred
            if interval_issue is not None:
                interval_issue = None
    return symbol_df, cache_files, interval_issue


def choose_window_days(interval_hours: int | None, max_window_days: int) -> int:
    if interval_hours is None or interval_hours <= 0:
        return min(30, max_window_days)
    target_days = int((150 * interval_hours) / 24)
    return max(1, min(max_window_days, target_days))


def infer_interval_hours(symbol_df: pd.DataFrame) -> int | None:
    if len(symbol_df) < 2:
        return None
    timestamps = pd.to_datetime(symbol_df["timestamp"], utc=True).sort_values()
    diffs = timestamps.diff().dropna().dt.total_seconds() / 3600
    if diffs.empty:
        return None
    rounded = diffs.round().astype(int)
    mode = rounded.mode()
    if mode.empty or int(mode.iloc[0]) <= 0:
        return None
    return int(mode.iloc[0])


def request_json_cached(
    url: str,
    params: dict[str, Any],
    cache_path: Path,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    if cache_path.exists():
        metrics.cache_hit_count += 1
        return json.loads(cache_path.read_text(encoding="utf-8"))

    payload = request_json_live(url, params, args, metrics, api_errors)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def request_json_live(
    url: str,
    params: dict[str, Any],
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    import requests

    retryable_retcodes = {10000, 10006, 10016, 10018}
    last_error: str | None = None
    for attempt in range(args.max_retries + 1):
        if attempt > 0:
            metrics.retry_count += 1
            delay = min(16.0, 2.0 ** (attempt - 1)) + random.uniform(0.0, 0.2)
            time.sleep(delay)
        elif args.request_interval_seconds > 0:
            time.sleep(args.request_interval_seconds)

        metrics.request_count += 1
        try:
            response = requests.get(url, params=params, timeout=20)
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                api_errors.append({"url": url, "params": params, "attempt": attempt, "error": last_error})
                metrics.api_error_count += 1
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("retCode") != 0:
                last_error = f"retCode={payload.get('retCode')} retMsg={payload.get('retMsg')}"
                api_errors.append({"url": url, "params": params, "attempt": attempt, "error": last_error})
                metrics.api_error_count += 1
                if payload.get("retCode") not in retryable_retcodes:
                    raise RuntimeError(last_error)
                continue
            return payload
        except RuntimeError:
            raise
        except requests.HTTPError as exc:  # pragma: no cover - network-dependent
            status = exc.response.status_code if exc.response is not None else None
            last_error = f"HTTPError status={status}: {exc}"
            api_errors.append({"url": url, "params": params, "attempt": attempt, "error": last_error})
            metrics.api_error_count += 1
            raise RuntimeError(last_error) from exc
        except (requests.Timeout, requests.ConnectionError) as exc:  # pragma: no cover - network-dependent
            last_error = f"{type(exc).__name__}: {exc}"
            api_errors.append({"url": url, "params": params, "attempt": attempt, "error": last_error})
            metrics.api_error_count += 1
            continue
        except Exception as exc:  # pragma: no cover - network-dependent
            last_error = f"{type(exc).__name__}: {exc}"
            api_errors.append({"url": url, "params": params, "attempt": attempt, "error": last_error})
            metrics.api_error_count += 1
            continue
    raise RuntimeError(last_error or "request failed")


def cache_path_for(cache_dir: Path, endpoint_name: str, raw_symbol: str, params: dict[str, Any]) -> Path:
    param_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    if endpoint_name == "funding_history":
        return (
            cache_dir
            / endpoint_name
            / "linear"
            / raw_symbol
            / f"{params['startTime']}_{params['endTime']}_limit{params['limit']}_{param_hash}.json"
        )
    return cache_dir / endpoint_name / "linear" / raw_symbol / f"{param_hash}.json"


def parse_funding_payload(
    payload: dict[str, Any],
    raw_symbol: str,
    interval_hours: int,
    dry_start: datetime,
    dry_end: datetime,
) -> pd.DataFrame:
    rows = payload.get("result", {}).get("list", [])
    parsed = []
    for row in rows:
        timestamp = pd.to_datetime(int(row["fundingRateTimestamp"]), unit="ms", utc=True)
        if timestamp < pd.Timestamp(dry_start) or timestamp > pd.Timestamp(dry_end):
            continue
        parsed.append({
            "timestamp": timestamp,
            "symbol": to_perp_symbol(raw_symbol),
            "exchange": "bybit_perp",
            "funding_rate": float(row["fundingRate"]),
            "interval_hours": interval_hours,
            "source": "bybit_api",
            "is_proxy": False,
        })
    return pd.DataFrame(parsed, columns=FUNDING_COLUMNS)


def normalize_funding_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        out = pd.DataFrame(columns=FUNDING_COLUMNS)
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        out["symbol"] = out["symbol"].astype("string")
        out["exchange"] = out["exchange"].astype("string")
        out["funding_rate"] = out["funding_rate"].astype("float64")
        out["interval_hours"] = out["interval_hours"].astype("int16")
        out["source"] = out["source"].astype("string")
        out["is_proxy"] = out["is_proxy"].astype("bool")
        return out
    out = df[FUNDING_COLUMNS].drop_duplicates(["timestamp", "symbol"]).sort_values(["symbol", "timestamp"])
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["symbol"] = out["symbol"].astype("string")
    out["exchange"] = out["exchange"].astype("string")
    out["funding_rate"] = out["funding_rate"].astype("float64")
    out["interval_hours"] = out["interval_hours"].astype("int16")
    out["source"] = out["source"].astype("string")
    out["is_proxy"] = out["is_proxy"].astype("bool")
    return out.reset_index(drop=True)


def write_funding_rates_parquet(df: pd.DataFrame, path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema([
        ("timestamp", pa.timestamp("ns", tz="UTC")),
        ("symbol", pa.string()),
        ("exchange", pa.string()),
        ("funding_rate", pa.float64()),
        ("interval_hours", pa.int16()),
        ("source", pa.string()),
        ("is_proxy", pa.bool_()),
    ])
    table = pa.Table.from_pandas(df[FUNDING_COLUMNS], schema=schema, preserve_index=False)
    pq.write_table(table, path, version="2.6")


def active_position_pairs(positions: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    pairs = positions[["date", "symbol"]].copy()
    pairs["date"] = pd.to_datetime(pairs["date"]).dt.tz_localize("UTC").dt.normalize()
    return pairs[
        (pairs["date"] >= pd.Timestamp(start).normalize())
        & (pairs["date"] <= pd.Timestamp(end).normalize())
    ].drop_duplicates().sort_values(["date", "symbol"])


def active_pit_pairs(universe: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    pairs = universe.loc[universe["is_member"], ["date", "symbol"]].copy()
    pairs["date"] = pd.to_datetime(pairs["date"]).dt.tz_localize("UTC").dt.normalize()
    return pairs[
        (pairs["date"] >= pd.Timestamp(start).normalize())
        & (pairs["date"] <= pd.Timestamp(end).normalize())
    ].drop_duplicates().sort_values(["date", "symbol"])


def build_scope_coverage(
    scope_name: str,
    active_pairs: pd.DataFrame,
    funding_df: pd.DataFrame,
    start: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    coverage = active_pairs.copy().assign(
        coverage_scope=scope_name,
        has_funding=False,
        is_proxy=False,
        source="missing",
        funding_events_count=0,
        expected_events_count=3,
        continuity_gap_count=3,
    )
    if not funding_df.empty:
        funding = funding_df.copy()
        funding["date"] = pd.to_datetime(funding["timestamp"], utc=True).dt.normalize()
        funding = funding[
            (funding["timestamp"] >= pd.Timestamp(start))
            & (funding["timestamp"] <= pd.Timestamp(end))
        ]
        intervals = funding.groupby("symbol")["interval_hours"].agg(
            lambda values: int(values.mode().iloc[0]) if not values.mode().empty and int(values.mode().iloc[0]) > 0 else 8
        )
        coverage["expected_events_count"] = coverage["symbol"].map(
            lambda symbol: int(24 / int(intervals.get(symbol, 8))) if int(intervals.get(symbol, 8)) > 0 else 3
        )
        grouped = funding.groupby(["date", "symbol"], as_index=False).agg(
            has_funding=("funding_rate", "size"),
            has_real=("is_proxy", lambda values: bool((~values).any())),
            has_proxy=("is_proxy", "any"),
            source=("source", lambda values: ";".join(sorted(set(map(str, values))))),
        )
        grouped["funding_events_count"] = grouped["has_funding"].astype(int)
        grouped["has_funding"] = grouped["has_funding"] > 0
        grouped["is_proxy"] = grouped["has_proxy"] & ~grouped["has_real"]
        coverage = coverage.drop(columns=["has_funding", "is_proxy", "source", "funding_events_count", "continuity_gap_count"]).merge(
            grouped[["date", "symbol", "has_funding", "is_proxy", "source", "funding_events_count"]],
            on=["date", "symbol"],
            how="left",
        )
        coverage["has_funding"] = coverage["has_funding"].fillna(False).astype(bool)
        coverage["is_proxy"] = coverage["is_proxy"].fillna(False).astype(bool)
        coverage["source"] = coverage["source"].fillna("missing")
        coverage["funding_events_count"] = coverage["funding_events_count"].fillna(0).astype(int)
        coverage["continuity_gap_count"] = (
            coverage["expected_events_count"] - coverage["funding_events_count"]
        ).clip(lower=0).astype(int)

    total = int(len(coverage))
    real = int((coverage["has_funding"] & ~coverage["is_proxy"]).sum())
    proxy = int((coverage["has_funding"] & coverage["is_proxy"]).sum())
    missing = int((~coverage["has_funding"]).sum())
    summary = {
        "symbol_days": total,
        "real_funded_symbol_days": real,
        "proxy_symbol_days": proxy,
        "missing_symbol_days": missing,
        "coverage_real_pct": pct(real, total),
        "coverage_proxy_pct": pct(proxy, total),
        "coverage_missing_pct": pct(missing, total),
        "continuity_gap_symbol_days": int((coverage["continuity_gap_count"] > 0).sum()),
        "continuity_gap_events": int(coverage["continuity_gap_count"].sum()),
    }
    coverage["date"] = coverage["date"].dt.strftime("%Y-%m-%d")
    return coverage[
        [
            "coverage_scope",
            "date",
            "symbol",
            "has_funding",
            "is_proxy",
            "source",
            "funding_events_count",
            "expected_events_count",
            "continuity_gap_count",
        ]
    ], summary


def funding_unit_check(funding_df: pd.DataFrame) -> dict[str, Any]:
    if funding_df.empty:
        return {"status": "NO_ROWS", "max_abs_funding_rate": None}
    max_abs = float(funding_df["funding_rate"].abs().max())
    return {
        "status": "PASS" if max_abs < 0.1 else "NEED_CLARIFICATION",
        "max_abs_funding_rate": max_abs,
        "note": "Funding rates are parsed as decimals from Bybit fundingRate strings.",
    }


def live_diff_check(
    funding_df: pd.DataFrame,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
    sample_size: int,
) -> dict[str, Any]:
    if funding_df.empty:
        return {"status": "NO_ROWS", "sample_count": 0, "max_abs_diff": None, "failures": []}
    sample = funding_df.head(sample_size)
    failures: list[dict[str, Any]] = []
    diffs: list[float] = []
    for _, row in sample.iterrows():
        timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime()
        raw_symbol = to_funding_symbol(str(row["symbol"]))
        params = {
            "category": "linear",
            "symbol": raw_symbol,
            "startTime": ms(timestamp - timedelta(hours=1)),
            "endTime": ms(timestamp + timedelta(hours=1)),
            "limit": 200,
        }
        try:
            payload = request_json_live(BYBIT_FUNDING_API, params, args, metrics, api_errors)
            rows = payload.get("result", {}).get("list", [])
            expected_ms = ms(timestamp)
            matches = [item for item in rows if int(item["fundingRateTimestamp"]) == expected_ms]
            if not matches:
                failures.append({"symbol": str(row["symbol"]), "timestamp": format_utc(timestamp), "error": "no exact timestamp match"})
                continue
            live_rate = float(matches[0]["fundingRate"])
            diff = abs(live_rate - float(row["funding_rate"]))
            diffs.append(diff)
            if diff >= 1e-9:
                failures.append({
                    "symbol": str(row["symbol"]),
                    "timestamp": format_utc(timestamp),
                    "stored": float(row["funding_rate"]),
                    "live": live_rate,
                    "diff": diff,
                })
        except Exception as exc:
            failures.append({"symbol": str(row["symbol"]), "timestamp": format_utc(timestamp), "error": f"{type(exc).__name__}: {exc}"})
    max_diff = max(diffs) if diffs else None
    return {
        "status": "PASS" if not failures and len(diffs) == len(sample) else "FAIL",
        "sample_count": int(len(sample)),
        "matched_count": int(len(diffs)),
        "max_abs_diff": max_diff,
        "threshold": 1e-9,
        "failures": failures[:20],
    }


def live_diff_check_by_year(
    funding_df: pd.DataFrame,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
    sample_size: int,
    min_per_year: int,
) -> dict[str, Any]:
    if funding_df.empty:
        return {"status": "NO_ROWS", "sample_count": 0, "matched_count": 0, "max_abs_diff": None, "failures": []}
    df = funding_df.copy()
    df["year"] = pd.to_datetime(df["timestamp"], utc=True).dt.year
    samples = []
    per_year_counts: dict[str, int] = {}
    for year in [2024, 2025, 2026]:
        year_df = df[df["year"].eq(year)].sort_values(["symbol", "timestamp"])
        count = min(min_per_year, len(year_df))
        per_year_counts[str(year)] = int(count)
        if count > 0:
            indices = evenly_spaced_indices(len(year_df), count)
            samples.append(year_df.iloc[indices])
    sample = pd.concat(samples, ignore_index=True) if samples else df.head(0)
    if len(sample) < sample_size:
        used = set(zip(sample["symbol"], sample["timestamp"]))
        remaining = df[~df.apply(lambda row: (row["symbol"], row["timestamp"]) in used, axis=1)].sort_values(["symbol", "timestamp"])
        need = min(sample_size - len(sample), len(remaining))
        if need > 0:
            sample = pd.concat([sample, remaining.iloc[evenly_spaced_indices(len(remaining), need)]], ignore_index=True)
    result = live_diff_check_for_sample(sample.head(sample_size), args, metrics, api_errors)
    result["per_year_sample_count"] = per_year_counts
    return result


def live_diff_check_for_sample(
    sample: pd.DataFrame,
    args: argparse.Namespace,
    metrics: ApiMetrics,
    api_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    diffs: list[float] = []
    for _, row in sample.iterrows():
        timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime()
        raw_symbol = to_funding_symbol(str(row["symbol"]))
        params = {
            "category": "linear",
            "symbol": raw_symbol,
            "startTime": ms(timestamp - timedelta(hours=1)),
            "endTime": ms(timestamp + timedelta(hours=1)),
            "limit": 200,
        }
        try:
            payload = request_json_live(BYBIT_FUNDING_API, params, args, metrics, api_errors)
            expected_ms = ms(timestamp)
            matches = [
                item
                for item in payload.get("result", {}).get("list", [])
                if int(item["fundingRateTimestamp"]) == expected_ms
            ]
            if not matches:
                failures.append({"symbol": str(row["symbol"]), "timestamp": format_utc(timestamp), "error": "no exact timestamp match"})
                continue
            live_rate = float(matches[0]["fundingRate"])
            diff = abs(live_rate - float(row["funding_rate"]))
            diffs.append(diff)
            if diff >= 1e-9:
                failures.append({
                    "symbol": str(row["symbol"]),
                    "timestamp": format_utc(timestamp),
                    "stored": float(row["funding_rate"]),
                    "live": live_rate,
                    "diff": diff,
                })
        except Exception as exc:
            failures.append({"symbol": str(row["symbol"]), "timestamp": format_utc(timestamp), "error": f"{type(exc).__name__}: {exc}"})
    return {
        "status": "PASS" if not failures and len(diffs) == len(sample) else "FAIL",
        "sample_count": int(len(sample)),
        "matched_count": int(len(diffs)),
        "max_abs_diff": max(diffs) if diffs else None,
        "threshold": 1e-9,
        "failures": failures[:30],
    }


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    if count <= 0:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [0]
    return sorted({round(i * (length - 1) / (count - 1)) for i in range(count)})


def funding_outlier_summary(funding_df: pd.DataFrame, threshold: float = 0.01) -> dict[str, Any]:
    if funding_df.empty:
        return {"threshold_abs": threshold, "outlier_count": 0, "top_outliers": []}
    outliers = funding_df[funding_df["funding_rate"].abs() >= threshold].copy()
    outliers["abs_funding_rate"] = outliers["funding_rate"].abs()
    top = outliers.sort_values("abs_funding_rate", ascending=False).head(50).copy()
    if not top.empty:
        top["timestamp"] = top["timestamp"].astype(str)
    return {
        "threshold_abs": threshold,
        "outlier_count": int(len(outliers)),
        "max_abs_funding_rate": float(funding_df["funding_rate"].abs().max()) if not funding_df.empty else None,
        "top_outliers": top[["timestamp", "symbol", "funding_rate", "interval_hours", "source"]].to_dict(orient="records"),
    }


def continuity_gap_summary(funding_df: pd.DataFrame, start: datetime, end: datetime) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    if funding_df.empty:
        return {"symbols_with_gaps": 0, "gap_count": 0, "top_gaps": []}
    for symbol, group in funding_df.groupby("symbol"):
        interval = int(group["interval_hours"].mode().iloc[0])
        timestamps = pd.to_datetime(group["timestamp"], utc=True).sort_values()
        if len(timestamps) < 2 or interval <= 0:
            continue
        expected_delta = timedelta(hours=interval)
        diffs = timestamps.diff().dropna()
        for ts, delta in zip(timestamps.iloc[1:], diffs):
            if delta > expected_delta * 1.5:
                missing_events = int(round(delta / expected_delta)) - 1
                gaps.append({
                    "symbol": symbol,
                    "gap_end_timestamp": str(ts),
                    "gap_hours": float(delta.total_seconds() / 3600),
                    "expected_interval_hours": interval,
                    "estimated_missing_events": max(1, missing_events),
                })
    gap_df = pd.DataFrame(gaps)
    return {
        "symbols_with_gaps": int(gap_df["symbol"].nunique()) if not gap_df.empty else 0,
        "gap_count": int(len(gaps)),
        "estimated_missing_events": int(gap_df["estimated_missing_events"].sum()) if not gap_df.empty else 0,
        "top_gaps": gaps[:50],
        "checked_start_utc": format_utc(start),
        "checked_end_utc": format_utc(end),
    }


def missing_symbol_summary(coverage_report: pd.DataFrame) -> dict[str, Any]:
    missing = coverage_report[~coverage_report["has_funding"]].copy()
    if missing.empty:
        return {"top_missing_symbols": [], "missing_symbol_count": 0}
    counts = (
        missing.groupby(["coverage_scope", "symbol"])
        .size()
        .reset_index(name="missing_symbol_days")
        .sort_values(["coverage_scope", "missing_symbol_days", "symbol"], ascending=[True, False, True])
    )
    return {
        "missing_symbol_count": int(counts["symbol"].nunique()),
        "top_missing_symbols": counts.head(100).to_dict(orient="records"),
    }


def determine_phase2_full_status(
    schema_errors: list[str],
    mapping_result: dict[str, Any],
    interval_unclear_symbols: list[dict[str, Any]],
    live_diff: dict[str, Any],
    active_pit_coverage: float,
) -> str:
    if schema_errors or mapping_result["failed_symbols"] > 0 or interval_unclear_symbols:
        return "NEED_CLARIFICATION"
    if live_diff["status"] != "PASS":
        return "NEED_CLARIFICATION"
    if active_pit_coverage >= 80.0:
        return "READY_FOR_TASK_002_REVIEW"
    if active_pit_coverage >= 50.0:
        return "PROXY_ONLY"
    return "BLOCKED_BY_DATA"


def write_phase2_full_log(log_path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"random_seed={RANDOM_SEED}",
        f"baseline_run_id={BASELINE_RUN_ID}",
        f"phase_status={summary['phase_status']}",
        f"task_002a_overall_status={summary['task_002a_overall_status']}",
        f"request_count={summary['request_count']}",
        f"cache_hit_count={summary['cache_hit_count']}",
        f"retry_count={summary['retry_count']}",
        f"api_error_count={summary['api_error_count']}",
        f"symbols_failed_count={summary['symbols_failed_count']}",
        f"raw_cache_snapshot_hash={summary['raw_cache_snapshot_hash']}",
        f"data_snapshot_hash={summary['data_snapshot_hash']}",
        f"funding_rates_parquet_hash={summary['funding_rates_parquet_hash']}",
        f"git_commit={summary['git_commit']}",
        "NOTE: Controlled full fetch only; TASK-002 stress was not executed.",
        "NOTE: TASK-002 remains BLOCKED pending REVIEW-002a_phase2_full.",
        "NOTE: No proxy, average, or fake funding rows were generated.",
        json.dumps(summary, indent=2, sort_keys=True),
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def determine_phase2_dryrun_status(
    schema_errors: list[str],
    mapping_result: dict[str, Any],
    metrics: ApiMetrics,
    live_diff: dict[str, Any],
    symbol_failures: list[dict[str, Any]],
) -> str:
    if mapping_result["failed_symbols"] > 0 or schema_errors:
        return "NEED_CLARIFICATION"
    if metrics.symbols_failed_count > 0:
        return "BLOCKED_BY_DATA"
    if live_diff["status"] not in {"PASS", "NO_ROWS"}:
        return "NEED_CLARIFICATION"
    return "READY_TO_REVIEW_PHASE2_DRYRUN"


def write_phase2_dryrun_log(log_path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"random_seed={RANDOM_SEED}",
        f"baseline_run_id={BASELINE_RUN_ID}",
        f"phase_status={summary['phase_status']}",
        f"request_count={summary['request_count']}",
        f"cache_hit_count={summary['cache_hit_count']}",
        f"retry_count={summary['retry_count']}",
        f"api_error_count={summary['api_error_count']}",
        f"symbols_failed_count={summary['symbols_failed_count']}",
        f"raw_cache_snapshot_hash={summary['raw_cache_snapshot_hash']}",
        f"data_snapshot_hash={summary['data_snapshot_hash']}",
        f"git_commit={summary['git_commit']}",
        "NOTE: Phase 2 dry-run only; formal data/crypto/funding_rates.parquet was not written.",
        "NOTE: TASK-002 stress was not executed and TASK-002 remains blocked.",
        "NOTE: No proxy, average, or fake funding rows were generated.",
        json.dumps(summary, indent=2, sort_keys=True),
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_funding_rates_schema(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if list(df.columns) != FUNDING_COLUMNS:
        errors.append(f"columns must be exactly {FUNDING_COLUMNS}, got {list(df.columns)}")
        return errors

    timestamp_dtype = df["timestamp"].dtype
    if not isinstance(timestamp_dtype, pd.DatetimeTZDtype):
        errors.append(f"timestamp must be timezone-aware datetime64[ns, UTC], got {timestamp_dtype}")
    else:
        timezone = getattr(timestamp_dtype, "tz", None)
        if str(timezone) != "UTC":
            errors.append(f"timestamp timezone must be UTC, got {timezone}")

    symbol_ok = df["symbol"].astype("string").str.match(r"^BYBIT:[A-Z0-9]+USDT\.P$", na=False)
    if not bool(symbol_ok.all()):
        errors.append("symbol must match BYBIT:XXXUSDT.P for every row")

    if not pd.api.types.is_string_dtype(df["exchange"].dtype):
        errors.append(f"exchange must be string dtype, got {df['exchange'].dtype}")
    if not pd.api.types.is_float_dtype(df["funding_rate"].dtype):
        errors.append(f"funding_rate must be float dtype, got {df['funding_rate'].dtype}")
    if not pd.api.types.is_integer_dtype(df["interval_hours"].dtype):
        errors.append(f"interval_hours must be integer dtype, got {df['interval_hours'].dtype}")
    if not pd.api.types.is_string_dtype(df["source"].dtype):
        errors.append(f"source must be string dtype, got {df['source'].dtype}")
    if not pd.api.types.is_bool_dtype(df["is_proxy"].dtype):
        errors.append(f"is_proxy must be bool dtype, got {df['is_proxy'].dtype}")

    if df[FUNDING_COLUMNS].isna().any().any():
        errors.append("funding_rates.parquet must not contain nulls in required columns")
    return errors


def build_coverage_report(
    positions_path: Path,
    baseline_path: Path,
    funding_df: pd.DataFrame | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    positions = pd.read_parquet(positions_path)
    baseline = pd.read_csv(baseline_path, parse_dates=["date"])
    active_dates = baseline.loc[baseline["gross_exposure"] > 0, "date"].dt.normalize()
    active_start = active_dates.min()
    active_end = active_dates.max()

    active_pairs = positions.copy()
    active_pairs["date"] = pd.to_datetime(active_pairs["date"]).dt.normalize()
    active_pairs = active_pairs[active_pairs["date"].isin(active_dates)]
    active_pairs = active_pairs[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])

    coverage = active_pairs.assign(has_funding=False, is_proxy=False, source="missing")
    if funding_df is not None and not funding_df.empty:
        funding = funding_df.copy()
        funding["date"] = pd.to_datetime(funding["timestamp"], utc=True).dt.tz_convert(None).dt.normalize()
        funding = funding[
            funding["date"].between(active_start, active_end)
            & funding["symbol"].isin(active_pairs["symbol"].unique())
        ]
        grouped = funding.groupby(["date", "symbol"], as_index=False).agg(
            has_funding=("funding_rate", "size"),
            has_real=("is_proxy", lambda values: bool((~values).any())),
            has_proxy=("is_proxy", "any"),
            source=("source", lambda values: ";".join(sorted(set(map(str, values))))),
        )
        grouped["has_funding"] = grouped["has_funding"] > 0
        grouped["is_proxy"] = grouped["has_proxy"] & ~grouped["has_real"]
        coverage = coverage.drop(columns=["has_funding", "is_proxy", "source"]).merge(
            grouped[["date", "symbol", "has_funding", "is_proxy", "source"]],
            on=["date", "symbol"],
            how="left",
        )
        coverage["has_funding"] = coverage["has_funding"].fillna(False).astype(bool)
        coverage["is_proxy"] = coverage["is_proxy"].fillna(False).astype(bool)
        coverage["source"] = coverage["source"].fillna("missing")

    total = int(len(coverage))
    real_mask = coverage["has_funding"] & ~coverage["is_proxy"]
    proxy_mask = coverage["has_funding"] & coverage["is_proxy"]
    missing_mask = ~coverage["has_funding"]
    top_missing = (
        coverage.loc[missing_mask, "symbol"]
        .value_counts()
        .head(20)
        .rename_axis("symbol")
        .reset_index(name="missing_symbol_days")
        .to_dict(orient="records")
    )
    summary = {
        "active_period_start": active_start.strftime("%Y-%m-%d"),
        "active_period_end": active_end.strftime("%Y-%m-%d"),
        "total_pit_symbol_days_active": total,
        "funded_symbol_days_active": int(real_mask.sum()),
        "proxy_symbol_days_active": int(proxy_mask.sum()),
        "missing_symbol_days_active": int(missing_mask.sum()),
        "coverage_real_pct": pct(int(real_mask.sum()), total),
        "coverage_proxy_pct": pct(int(proxy_mask.sum()), total),
        "coverage_total_pct": pct(int((real_mask | proxy_mask).sum()), total),
        "top_missing_symbols": top_missing,
    }
    coverage["date"] = coverage["date"].dt.strftime("%Y-%m-%d")
    return coverage[["date", "symbol", "has_funding", "is_proxy", "source"]], summary


def discover_funding_sources(api_smoke: bool) -> FundingSourceStatus:
    local_sources: list[str] = []
    db_path = Path("data/trading.db")
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
                ).fetchall()
            ]
        local_sources.extend(f"data/trading.db:{table}" for table in tables if "fund" in table.lower())

    for pattern in [
        "data/cache/funding/**/*",
        "data/crypto/funding_*.parquet",
        "data/crypto/*funding*.csv",
        "data/crypto/*funding*.parquet",
    ]:
        local_sources.extend(str(path) for path in Path().glob(pattern) if path.is_file())

    api_status = "not_run"
    if api_smoke:
        api_status = smoke_test_bybit_api()
    return FundingSourceStatus(
        local_sources=sorted(set(local_sources)),
        bybit_api_smoke_status=api_status,
        bybit_api_url=BYBIT_FUNDING_API,
    )


def smoke_test_bybit_api() -> str:
    try:
        import requests
    except ImportError:
        return "requests_not_installed"
    try:
        response = requests.get(
            BYBIT_FUNDING_API,
            params={"category": "linear", "symbol": "BTCUSDT", "limit": 1},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - network-dependent smoke check
        return f"failed:{type(exc).__name__}:{exc}"

    if payload.get("retCode") != 0:
        return f"failed:retCode={payload.get('retCode')}:{payload.get('retMsg')}"
    rows = payload.get("result", {}).get("list", [])
    if not rows:
        return "failed:empty_result"
    return "ok"


def determine_phase1_status(
    summary: dict[str, Any],
    source_status: FundingSourceStatus,
    schema_errors: list[str],
) -> str:
    if schema_errors:
        return "NEED_CLARIFICATION"
    if summary["coverage_real_pct"] >= 80.0:
        return "READY_TO_IMPLEMENT"
    if summary["coverage_proxy_pct"] > 0:
        return "PROXY_ONLY"
    if source_status.bybit_api_smoke_status == "ok":
        return "READY_TO_IMPLEMENT"
    return "BLOCKED_BY_DATA"


def primary_funding_source(source_status: FundingSourceStatus) -> str:
    if source_status.local_sources:
        return source_status.local_sources[0]
    if source_status.bybit_api_smoke_status == "ok":
        return "bybit_api"
    return "none_local"


def write_build_log(log_path: Path, summary: dict[str, Any], args: argparse.Namespace) -> None:
    config_hash = hash_paths([Path("data/crypto/fees.yaml"), Path("configs/cost_stress.yaml")])
    data_snapshot_hash = hash_paths([args.positions, args.baseline])
    git_commit = git_rev_parse()
    lines = [
        f"random_seed={RANDOM_SEED}",
        f"config_hash={config_hash}",
        f"data_snapshot_hash={data_snapshot_hash}",
        f"git_commit={git_commit}",
        f"baseline_run_id={BASELINE_RUN_ID}",
        f"funding_source={summary['funding_source_primary']}",
        f"funding_proxy_pct={summary['coverage_proxy_pct']}",
        f"phase1_status={summary['phase1_status']}",
        f"funding_rates_exists={summary['funding_rates_exists']}",
        f"bybit_api_smoke_status={summary['bybit_api_smoke_status']}",
        "NOTE: Phase 1 does not execute TASK-002 stress.",
        "NOTE: Missing symbol-days are not filled and no formal proxy funding was generated.",
        "NOTE: Rows with is_proxy=true must be excluded from TASK-002 formal fail gate.",
        json.dumps(summary, indent=2, sort_keys=True),
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def hash_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        if path.exists():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
    return digest.hexdigest()


def git_rev_parse() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "UNKNOWN"
    return result.stdout.strip()


def pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100.0, 6)


if __name__ == "__main__":
    raise SystemExit(main())
