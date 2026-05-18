from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.monitor.alerts import dedupe_alerts, make_sample_alert, summarize_alerts
from apps.monitor.channels import dispatch_alerts
from apps.monitor.config import load_monitor_config
from apps.monitor.heartbeat import hook_event_from_heartbeat, sample_heartbeat, write_heartbeat_parquet
from apps.monitor.log_scanner import scan_logs
from apps.monitor.report import (
    build_review_numbers,
    build_review_packet,
    build_setup_log,
    build_task005a_delivery_log,
    build_task005a_numbers,
    build_task005a_packet,
)
from apps.monitor.safety import scan_monitor_safety
from apps.monitor.schema import validate_alerts_jsonl, validate_heartbeat_parquet


def run_task005(output_date: str, config_path: Path, test_send: bool = False) -> dict:
    repo_root = Path(".").resolve()
    config = load_monitor_config(config_path)
    timestamp = _timestamp_for_output_date(output_date)
    alerts = dedupe_alerts(scan_logs(config, timestamp) + [make_sample_alert(config, timestamp)])
    alert_counts = summarize_alerts(alerts)
    heartbeat_rows = [
        sample_heartbeat(
            config,
            timestamp=timestamp,
            warning_count=alert_counts.get("WARNING", 0),
            critical_count=alert_counts.get("CRITICAL", 0),
        )
    ]
    hook_event = hook_event_from_heartbeat(heartbeat_rows[0])

    output_paths = {
        "heartbeat": config.logging.output_heartbeat / f"{output_date}_heartbeat.parquet",
        "alerts": config.logging.output_alerts_dir / f"{output_date}.jsonl",
        "setup_log": config.logging.output_log_dir / f"{output_date}_monitor_setup.log",
        "review_packet": Path("docs/research/review_packets/REVIEW-005_PACKET.md"),
        "review_numbers": Path("docs/research/review_packets/REVIEW-005_NUMBERS.json"),
    }
    task005a_output_paths = {
        "delivery_log": config.logging.output_log_dir / f"{output_date}_task005a_alert_channel.log",
        "review_packet": Path("docs/research/review_packets/REVIEW-005a_PACKET.md"),
        "review_numbers": Path("docs/research/review_packets/REVIEW-005a_NUMBERS.json"),
        "alerts": output_paths["alerts"],
    }

    write_heartbeat_parquet(output_paths["heartbeat"], heartbeat_rows)
    channel_results = dispatch_alerts(config, alerts, output_paths["alerts"], test_send=test_send)
    heartbeat_validation = validate_heartbeat_parquet(output_paths["heartbeat"])
    alerts_validation = validate_alerts_jsonl(output_paths["alerts"])
    safety_scan = scan_monitor_safety(repo_root)

    # Two-pass write so missing-output gates evaluate the final artifact set.
    _write_review_artifacts(output_date, config, output_paths, heartbeat_validation, alerts_validation, safety_scan, hook_event)
    numbers = _write_review_artifacts(
        output_date,
        config,
        output_paths,
        heartbeat_validation,
        alerts_validation,
        safety_scan,
        hook_event,
    )
    task005a_numbers = _write_task005a_review_artifacts(
        output_date,
        config,
        task005a_output_paths,
        channel_results,
        safety_scan,
        test_send,
    )
    task005a_numbers = _write_task005a_review_artifacts(
        output_date,
        config,
        task005a_output_paths,
        channel_results,
        safety_scan,
        test_send,
    )
    status = "REVIEW_READY" if numbers["status"] == "REVIEW_READY" and task005a_numbers["status"] == "REVIEW_READY" else "FAIL"
    return {
        "status": status,
        "errors": _errors_from_numbers(numbers) + _errors_from_numbers(task005a_numbers),
        "outputs": {
            **{key: str(path) for key, path in output_paths.items()},
            **{f"task005a_{key}": str(path) for key, path in task005a_output_paths.items()},
        },
        "reproducibility_hash": numbers["reproducibility_hash"],
        "task005a_reproducibility_hash": task005a_numbers["reproducibility_hash"],
        "paper_execution_status": numbers["paper_execution_status"],
        "live_trading_status": numbers["live_trading_status"],
    }


def _write_review_artifacts(
    output_date: str,
    config,
    output_paths: dict[str, Path],
    heartbeat_validation: dict,
    alerts_validation: dict,
    safety_scan: dict,
    hook_event: dict,
) -> dict:
    numbers = build_review_numbers(
        output_date,
        config,
        output_paths,
        heartbeat_validation,
        alerts_validation,
        safety_scan,
        hook_event,
    )
    output_paths["review_packet"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["review_numbers"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["setup_log"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["review_packet"].write_text(build_review_packet(numbers), encoding="utf-8")
    output_paths["review_numbers"].wri