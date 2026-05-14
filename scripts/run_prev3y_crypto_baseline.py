"""Run TASK-001 Prev3Y crypto universe baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.long_short import (
    BASELINE_SCHEMA as ENGINE_BASELINE_SCHEMA,
    POSITIONS_SCHEMA,
    run_daily_long_short_backtest,
)
from src.data.crypto_daily import (
    PRICE_SCHEMA,
    price_anomalies,
    sha256_file,
    sha256_files,
)
from src.data.prev3y_input_validator import DataRequirementError, validate_prev3y_inputs
from src.data_quality.missing import (
    DATA_QUALITY_SUMMARY_SCHEMA,
    aggregate_data_quality_events,
    apply_data_quality_policy,
    combine_data_quality_events,
    data_quality_policy,
    events_to_output,
    forced_holding_exclusion_events,
)
from src.metrics.performance import STATS_SCHEMA, compute_stats
from src.reporting.prev3y_benchmarks import BENCHMARK_COLUMNS_SCHEMA, apply_benchmarks
from src.signals.prev3y_momentum import build_prev3y_targets
from src.universe.prev3y_crypto import (
    UNIVERSE_SCHEMA,
    daily_universe_sizes,
    universe_anomalies,
)


CONFIG_PATH = Path("configs/prev3y_crypto.yaml")
PRICE_PATH = Path("data/crypto/prices_daily.parquet")
UNIVERSE_PATH = Path("data/crypto/universe_membership.parquet")
BACKTEST_DIR = Path("outputs/backtests/prev3y_crypto")
LOG_DIR = Path("outputs/logs/prev3y_crypto")
DATA_QUALITY_DIR = Path("outputs/data_quality/prev3y_crypto")
BASELINE_OUTPUT_SCHEMA = ENGINE_BASELINE_SCHEMA[:3] + BENCHMARK_COLUMNS_SCHEMA + ENGINE_BASELINE_SCHEMA[3:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--run-date", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    parser.add_argument("--repeat-check", type=int, default=2)
    args = parser.parse_args()

    config_path = Path(args.config)
    try:
        validated = validate_prev3y_inputs(config_path, PRICE_PATH, UNIVERSE_PATH)
    except DataRequirementError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    config = validated.config
    np.random.seed(int(config.get("random_seed", 42)))
    prices = validated.prices
    membership = validated.membership
    price_info = validated.price_info
    universe_info = validated.universe_info

    config_hash = sha256_file(config_path)
    data_snapshot_hash = sha256_files([PRICE_PATH, UNIVERSE_PATH])
    git_commit = git_head()
    data_quality = apply_data_quality_policy(prices, membership, config)
    result = run_once(config, data_quality)

    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    output_stem, output_note = resolve_output_stem(args.run_date)
    baseline_path = BACKTEST_DIR / f"{output_stem}_baseline.csv"
    positions_path = BACKTEST_DIR / f"{output_stem}_positions.parquet"
    stats_path = BACKTEST_DIR / f"{output_stem}_stats.json"
    log_path = LOG_DIR / f"{output_stem}.log"
    dq_summary_path = DATA_QUALITY_DIR / f"{output_stem}_data_quality_summary.csv"
    dq_aggregate_path = DATA_QUALITY_DIR / f"{output_stem}_data_quality_aggregate.json"
    if output_note:
        print(output_note, file=sys.stderr)

    result["baseline"].to_csv(baseline_path, index=False, date_format="%Y-%m-%d")
    result["positions"].to_parquet(positions_path, index=False)
    write_json(stats_path, result["stats"])
    events_to_output(result["data_quality_events"]).to_csv(dq_summary_path, index=False)
    write_json(dq_aggregate_path, result["data_quality_aggregate"])

    repeat_hashes = [hash_stats(result["stats"])]
    for _ in range(max(0, int(args.repeat_check) - 1)):
        repeated = run_once(config, data_quality)
        repeat_hashes.append(hash_stats(repeated["stats"]))
    reproducible = len(set(repeat_hashes)) == 1

    anomalies = (
        price_anomalies(prices)
        + universe_anomalies(membership, prices)
        + result["return_anomalies"]
    )
    write_log(
        log_path=log_path,
        config=config,
        config_hash=config_hash,
        data_snapshot_hash=data_snapshot_hash,
        git_commit=git_commit,
        price_info=price_info,
        universe_info=universe_info,
        baseline_path=baseline_path,
        positions_path=positions_path,
        stats_path=stats_path,
        dq_summary_path=dq_summary_path,
        dq_aggregate_path=dq_aggregate_path,
        baseline=result["baseline"],
        membership=data_quality.tradable_membership,
        metadata=result["metadata"],
        anomalies=anomalies,
        data_quality_events=result["data_quality_events"],
        data_quality_aggregate=result["data_quality_aggregate"],
        repeat_hashes=repeat_hashes,
        reproducible=reproducible,
        validation_warnings=validated.warnings,
        output_note=output_note,
    )

    print(json.dumps({
        "baseline": str(baseline_path),
        "positions": str(positions_path),
        "stats": str(stats_path),
        "log": str(log_path),
        "data_quality_summary": str(dq_summary_path),
        "data_quality_aggregate": str(dq_aggregate_path),
        "stats_hashes": repeat_hashes,
        "reproducible": reproducible,
        "stats": result["stats"],
        "data_quality": result["data_quality_aggregate"],
        "output_note": output_note,
    }, indent=2, sort_keys=True))


def run_once(config: dict[str, Any], data_quality) -> dict[str, Any]:
    targets = build_prev3y_targets(
        prices=data_quality.prices,
        membership=data_quality.signal_membership,
        start_date=str(config["start_date"]),
        end_date=str(config["end_date"]),
        lookback_days=int(config["lookback_days"]),
        rebalance_freq=str(config["rebalance_freq"]),
        top_n=int(config["top_n"]),
        bottom_n=int(config["bottom_n"]),
        ranking_method=str(config["ranking_method"]),
    )
    backtest = run_daily_long_short_backtest(
        prices=data_quality.prices,
        membership=data_quality.tradable_membership,
        targets=targets,
        start_date=str(config["start_date"]),
        end_date=str(config["end_date"]),
        entry_price=str(config["entry_price"]),
    )
    if backtest.return_anomalies:
        raise RuntimeError(
            "NEED_CLARIFICATION: data-quality filters still produced missing held-position returns; "
            "do not proceed to REVIEW until exclusions are reconciled."
        )
    forced_events = forced_holding_exclusion_events(
        backtest.positions,
        data_quality.holding_exclusion_reasons,
    )
    data_quality_events = combine_data_quality_events([data_quality.events, forced_events])
    data_quality_aggregate = aggregate_data_quality_events(data_quality_events)
    benchmarks = apply_benchmarks(
        baseline=backtest.baseline,
        prices=data_quality.prices,
        membership=data_quality.tradable_membership,
        start_date=str(config["start_date"]),
        end_date=str(config["end_date"]),
        entry_price=str(config["entry_price"]),
        benchmark_config=dict(config.get("benchmark", {})),
    )
    stats = compute_stats(benchmarks.baseline)
    metadata = build_run_metadata(
        config,
        data_quality.tradable_membership,
        targets,
        benchmarks.baseline,
        benchmarks.metadata,
        data_quality_aggregate,
    )
    stats.update(metadata)
    stats["methodology"]["benchmark_primary"] = metadata["benchmark_primary"]
    stats["data_quality_policy"] = data_quality_policy()
    return {
        "baseline": benchmarks.baseline,
        "positions": backtest.positions,
        "stats": stats,
        "metadata": metadata,
        "return_anomalies": backtest.return_anomalies,
        "data_quality_events": data_quality_events,
        "data_quality_aggregate": data_quality_aggregate,
    }


def resolve_output_stem(run_date: str) -> tuple[str, str]:
    candidates = [run_date] + [f"{run_date}_run{i:03d}" for i in range(1, 1000)]
    for idx, stem in enumerate(candidates):
        paths = [
            BACKTEST_DIR / f"{stem}_baseline.csv",
            BACKTEST_DIR / f"{stem}_positions.parquet",
            BACKTEST_DIR / f"{stem}_stats.json",
            LOG_DIR / f"{stem}.log",
            DATA_QUALITY_DIR / f"{stem}_data_quality_summary.csv",
            DATA_QUALITY_DIR / f"{stem}_data_quality_aggregate.json",
        ]
        if all(not path.exists() for path in paths):
            if idx == 0:
                return stem, ""
            return (
                stem,
                f"NOTE: same-day output files for {run_date} already exist; "
                f"using non-overwriting run stem {stem}.",
            )
    raise FileExistsError(f"Refusing to overwrite outputs: no available run slot for {run_date}")


def build_run_metadata(
    config: dict[str, Any],
    membership: pd.DataFrame,
    targets,
    baseline: pd.DataFrame,
    benchmark_metadata: dict[str, object] | None = None,
    data_quality_aggregate: dict[str, object] | None = None,
) -> dict[str, object]:
    sizes = daily_universe_sizes(membership, str(config["start_date"]), str(config["end_date"]))
    tradable_counts = [int(target.eligible_count) for target in targets]
    active = baseline[baseline["gross_exposure"].astype(float).gt(0)]
    full_days = int(len(baseline))
    active_days = int(active["date"].nunique())
    active_start = "" if active.empty else pd.Timestamp(active["date"].min()).strftime("%Y-%m-%d")
    active_end = "" if active.empty else pd.Timestamp(active["date"].max()).strftime("%Y-%m-%d")
    metadata = {
        "start_date": str(config["start_date"]),
        "end_date": str(config["end_date"]),
        "warmup_start_date": str(config["warmup_start_date"]),
        "effective_entry_price": str(config["entry_price"]),
        "rebalance_freq": str(config["rebalance_freq"]),
        "lookback_days": int(config["lookback_days"]),
        "top_n": int(config["top_n"]),
        "bottom_n": int(config["bottom_n"]),
        "average_universe_size": float(sizes.mean()),
        "average_number_of_tradable_symbols": float(np.mean(tradable_counts)) if tradable_counts else 0.0,
        "effective_trading_days": active_days,
        "effective_sample_start": active_start,
        "effective_sample_end": active_end,
        "effective_active_days": active_days,
        "effective_active_fraction": float(active_days / full_days) if full_days else 0.0,
        "reporting_active_definition": "gross_exposure > 0",
        "benchmark_definition": "primary cash benchmark with BTC and PIT equal-weight alternatives",
    }
    if benchmark_metadata:
        metadata.update(benchmark_metadata)
    if data_quality_aggregate:
        metadata.update(data_quality_aggregate)
    return metadata


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def hash_stats(stats: dict[str, Any]) -> str:
    data = json.dumps(stats, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def git_head() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip()
    except Exception:
        return "unknown"


def write_log(
    log_path: Path,
    config: dict[str, Any],
    config_hash: str,
    data_snapshot_hash: str,
    git_commit: str,
    price_info,
    universe_info,
    baseline_path: Path,
    positions_path: Path,
    stats_path: Path,
    dq_summary_path: Path,
    dq_aggregate_path: Path,
    baseline: pd.DataFrame,
    membership: pd.DataFrame,
    metadata: dict[str, object],
    anomalies: list[dict[str, object]],
    data_quality_events: pd.DataFrame,
    data_quality_aggregate: dict[str, object],
    repeat_hashes: list[str],
    reproducible: bool,
    validation_warnings: list[str],
    output_note: str,
) -> None:
    sizes = daily_universe_sizes(membership, str(config["start_date"]), str(config["end_date"]))
    lines = [
        f"random_seed={config.get('random_seed', 42)}",
        f"config_hash={config_hash}",
        f"data_snapshot_hash={data_snapshot_hash}",
        f"git_commit={git_commit}",
        "",
        "TASK-001 Prev3Y Crypto Universe Baseline",
        f"run_utc={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"config={CONFIG_PATH}",
        "NOTE: input gate passed before backtest; required parquet/config files existed and schema validation passed.",
        "NOTE: baseline runner refuses missing/schema-invalid inputs and does not create random, simulated, or synthetic data.",
        "NOTE: data source = validated pre-existing data/crypto parquet files; see docs/research/DATA_REQUIREMENTS_PREV3Y.md for acquisition requirements.",
        "NOTE: quote_volume is derived as close * volume because the local prices table has no stored turnover column.",
        "NOTE: universe_membership.parquet stores true membership rows only; missing date/symbol rows are false.",
        "NOTE: benchmark_return = benchmark_cash_return because TASK-001b sets primary benchmark to cash.",
        "NOTE: benchmark_eqw_return = the old run003 equal_weight_long_only benchmark.",
        "NOTE: benchmark_btc_return = BYBIT:BTCUSDT.P benchmark; missing BTC dates remain NaN and are never filled with zero.",
        "NOTE: portfolio_return is dated by price realization date; new rebalance weights enter on t+1 and earn returns from the next price interval.",
        "NOTE: when eligible names are fewer than top_n + bottom_n, the signal layer shrinks to balanced non-overlapping long/short pairs.",
        "NOTE: TASK-001d adds a data-quality exclusion layer; strategy signal formula, ranking method, benchmark definitions, costs, funding, slippage, and raw data are unchanged.",
        "NOTE: abnormal symbol-days are excluded from ranking candidates, holding candidates, and return calculation.",
        "NOTE: missing returns are never filled with zero, and prices are never forward-filled to create returns.",
        "NOTE: active period is defined exactly as gross_exposure > 0.",
        "NOTE: legacy stats fields ir/sharpe/sortino/max_dd/calmar/turnover_annual/hit_rate are full-period aliases; primary interpretation should use *_active.",
    ]
    if output_note:
        lines.append(output_note)
    lines.extend([
        "",
        "Reporting Sample:",
        f"- effective_sample_start={metadata['effective_sample_start']}",
        f"- effective_sample_end={metadata['effective_sample_end']}",
        f"- effective_active_days={metadata['effective_active_days']}",
        f"- effective_active_fraction={metadata['effective_active_fraction']:.6f}",
        f"- reporting_active_definition={metadata['reporting_active_definition']}",
        f"- benchmark_primary={metadata['benchmark_primary']}",
        f"- benchmark_return_equals={metadata['benchmark_return_equals']}",
        "",
        "Config:",
    ])
    lines.extend(f"- {key}: {value}" for key, value in sorted(config.items()))
    lines.extend([
        "",
        "Run Metadata:",
        f"- start_date={metadata['start_date']}",
        f"- end_date={metadata['end_date']}",
        f"- warmup_start_date={metadata['warmup_start_date']}",
        f"- effective_entry_price={metadata['effective_entry_price']}",
        f"- rebalance_freq={metadata['rebalance_freq']}",
        f"- lookback_days={metadata['lookback_days']}",
        f"- top_n={metadata['top_n']}",
        f"- bottom_n={metadata['bottom_n']}",
        f"- average_universe_size={metadata['average_universe_size']:.6f}",
        f"- average_number_of_tradable_symbols={metadata['average_number_of_tradable_symbols']:.6f}",
        f"- benchmark_definition={metadata['benchmark_definition']}",
        f"- benchmark_return_equals={metadata['benchmark_return_equals']}",
        "",
        "Benchmark Coverage:",
        f"- benchmark_cash_return=0.0 for every baseline date",
        f"- benchmark_btc_symbol={metadata['benchmark_btc_symbol']}",
        f"- benchmark_btc_start_date={metadata['benchmark_btc_start_date']}",
        f"- benchmark_btc_end_date={metadata['benchmark_btc_end_date']}",
        f"- benchmark_btc_missing_days_full={metadata['benchmark_btc_missing_days_full']}",
        f"- benchmark_btc_missing_days_active={metadata['benchmark_btc_missing_days_active']}",
        f"- ir_vs_btc_full_effective_days={metadata['ir_vs_btc_full_effective_days']}",
        f"- ir_vs_btc_active_effective_days={metadata['ir_vs_btc_active_effective_days']}",
        f"- benchmark_eqw_effective_days_full={metadata['benchmark_eqw_effective_days_full']}",
        f"- benchmark_eqw_effective_days_active={metadata['benchmark_eqw_effective_days_active']}",
        f"- eqw_benchmark_avg_symbols={metadata['eqw_benchmark_avg_symbols']:.6f}",
        f"- eqw_benchmark_min_symbols={metadata['eqw_benchmark_min_symbols']}",
        f"- eqw_benchmark_missing_days={metadata['eqw_benchmark_missing_days']}",
        "",
        "Data Snapshot:",
        f"- prices_daily.parquet rows={price_info.row_count} symbols={price_info.symbol_count} date_range={price_info.min_date}..{price_info.max_date} created={price_info.created}",
        f"- universe_membership.parquet rows={universe_info.row_count} symbols={universe_info.symbol_count} date_range={universe_info.min_date}..{universe_info.max_date} created={universe_info.created}",
        f"- average_universe_size_start_end={sizes.mean():.6f}",
        f"- warmup_start_date={config['warmup_start_date']}",
        f"- backtest_start_date={config['start_date']}",
        f"- backtest_end_date={config['end_date']}",
        f"- effective_trading_days={metadata['effective_trading_days']}",
        f"- total_calendar_rows={int(len(baseline))}",
        f"- validation_warnings={len(validation_warnings)}",
        "",
        "No-Trading/Missing-Day Handling:",
        "- Baseline uses a complete daily UTC calendar from start_date to end_date.",
        "- Dates without eligible signals or active positions are retained with zero portfolio return and zero exposure.",
        "- Individual symbol missing returns are not filled; affected symbol-days are excluded before return calculation.",
        "- A held symbol that becomes abnormal is removed before the day's return calculation; this removal is counted in turnover.",
        "- Volume <= 0 is warning-only; missing volume or quote_volume is a hard abnormal symbol-day.",
        "",
        "Data Quality Policy:",
        f"- data_quality_event_rows={int(len(data_quality_events))}",
        f"- dq_abnormal_symbol_days={data_quality_aggregate['dq_abnormal_symbol_days']}",
        f"- dq_excluded_from_ranking_candidates={data_quality_aggregate['dq_excluded_from_ranking_candidates']}",
        f"- dq_excluded_from_holding_days={data_quality_aggregate['dq_excluded_from_holding_days']}",
        f"- dq_forced_holding_exits={data_quality_aggregate['dq_forced_holding_exits']}",
        f"- dq_affected_symbols={data_quality_aggregate['dq_affected_symbols']}",
        f"- issue_counts={json.dumps(data_quality_aggregate['issue_counts'], sort_keys=True)}",
        f"- top_affected_symbols={json.dumps(data_quality_aggregate['top_affected_symbols'][:10], sort_keys=True)}",
        f"- data_quality_summary_csv={dq_summary_path}",
        f"- data_quality_aggregate_json={dq_aggregate_path}",
        "",
        "Schemas:",
    ])
    lines.extend(schema_lines("prices_daily.parquet", PRICE_SCHEMA))
    lines.extend(schema_lines("universe_membership.parquet", UNIVERSE_SCHEMA))
    lines.extend(schema_lines(baseline_path.name, BASELINE_OUTPUT_SCHEMA))
    lines.extend(schema_lines(positions_path.name, POSITIONS_SCHEMA))
    lines.extend(schema_lines(stats_path.name, STATS_SCHEMA))
    lines.extend(schema_lines(dq_summary_path.name, DATA_QUALITY_SUMMARY_SCHEMA))
    lines.extend([
        "",
        "Outputs:",
        f"- baseline_csv={baseline_path}",
        f"- positions_parquet={positions_path}",
        f"- stats_json={stats_path}",
        f"- data_quality_summary_csv={dq_summary_path}",
        f"- data_quality_aggregate_json={dq_aggregate_path}",
        "",
        "Reproducibility:",
        f"- stats_hashes={','.join(repeat_hashes)}",
        f"- repeat_stats_hash_identical={str(reproducible).lower()}",
    ])
    if validation_warnings:
        lines.append("")
        lines.append("Validation Warnings:")
        lines.extend(f"- {warning}" for warning in validation_warnings)
    lines.append("")
    lines.append("Data Anomalies:")
    if anomalies:
        for anomaly in anomalies[:200]:
            lines.append(
                f"- symbol={anomaly.get('symbol', '')} "
                f"date_range={anomaly.get('start_date', '')}..{anomaly.get('end_date', '')} "
                f"issue={anomaly.get('issue', '')}"
            )
        if len(anomalies) > 200:
            lines.append(f"- truncated_anomaly_rows={len(anomalies) - 200}")
    else:
        lines.append("- none")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def schema_lines(name: str, schema: list[dict[str, str]]) -> list[str]:
    lines = [f"- {name}"]
    for col in schema:
        lines.append(f"  - {col['name']}: {col['type']}; unit={col['unit']}")
    return lines


if __name__ == "__main__":
    main()
