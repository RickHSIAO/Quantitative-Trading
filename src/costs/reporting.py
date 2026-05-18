from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_outputs(
    daily: pd.DataFrame,
    positions_cost: pd.DataFrame,
    summary: dict[str, Any],
    log_text: str,
    output_date: str,
    output_dir: str | Path = "outputs/backtests/prev3y_crypto",
    log_dir: str | Path = "outputs/logs/prev3y_crypto",
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    logs = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    paths = {
        "daily_csv": out_dir / f"{output_date}_cost_stress.csv",
        "summary_json": out_dir / f"{output_date}_cost_stress_summary.json",
        "positions_parquet": out_dir / f"{output_date}_cost_stress_positions_cost.parquet",
        "log": logs / f"{output_date}_cost_stress.log",
    }

    daily.to_csv(paths["daily_csv"], index=False)
    positions_cost.to_parquet(paths["positions_parquet"], index=False)
    paths["summary_json"].write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["log"].write_text(log_text, encoding="utf-8")
    return paths


def build_log_text(summary: dict[str, Any]) -> str:
    lines = [
        "TASK-002 cost stress v2",
        f"baseline_run_id={summary.get('baseline_run_id')}",
        f"readiness_status={summary.get('readiness_status')}",
        f"verdict={summary.get('verdict')}",
        f"git_commit={summary.get('git_commit')}",
        f"random_seed={summary.get('random_seed')}",
        f"config_hash={summary.get('input_hashes', {}).get('cost_stress_yaml')}",
        f"data_snapshot_hash={summary.get('data_snapshot_hash')}",
        f"funding_rates_parquet_hash={summary.get('input_hashes', {}).get('funding_rates_parquet')}",
        f"scenarios_count={len(summary.get('scenarios', {}))}",
        f"interval_distribution_used={summary.get('interval_hours_distribution')}",
        f"no_cost_baseline_max_diff_vs_run008={summary.get('no_cost_baseline_max_diff_vs_run008')}",
        "",
        "methodology:",
        json.dumps(summary.get("methodology", {}), indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "cost_policy:",
        json.dumps(summary.get("cost_policy", {}), indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "funding_audit_samples:",
        json.dumps(summary.get("funding_audit_samples", []), indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "fail_warning_gates:",
        json.dumps(summary.get("fail_warning_gates", {}), indent=2, sort_keys=True, ensure_ascii=False),
    ]
    return "\n".join(lines) + "\n"
