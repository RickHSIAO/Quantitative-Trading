from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from apps.monitor.channels.base import ChannelResult
from apps.monitor.config import MonitorConfig
from apps.monitor.safety import PROCESS_CONTROL_GATE


def build_review_numbers(
    output_date: str,
    config: MonitorConfig,
    output_paths: dict[str, Path],
    heartbeat_validation: dict[str, Any],
    alerts_validation: dict[str, Any],
    safety_scan: dict[str, Any],
    hook_event: dict[str, Any],
) -> dict[str, Any]:
    fail_gates = {
        "missing_outputs": any(not path.exists() for path in output_paths.values()),
        "test_failure": False,
        "schema_mismatch": heartbeat_validation["status"] != "PASS" or alerts_validation["status"] != "PASS",
        "api_key_permission_violation": bool(safety_scan["gates"]["api_key_permission_violation"]),
        "secret_in_vcs": bool(safety_scan["gates"]["secret_in_vcs"]),
        "order_submission_code_present": bool(safety_scan["gates"]["order_submission_code_present"]),
        PROCESS_CONTROL_GATE: bool(safety_scan["gates"][PROCESS_CONTROL_GATE]),
        "heartbeat_schema_invalid": heartbeat_validation["status"] != "PASS",
        "alerts_schema_invalid": alerts_validation["status"] != "PASS",
    }
    payload: dict[str, Any] = {
        "task": "TASK-005 VPS Bot Monitor",
        "run_date": output_date,
        "status": "REVIEW_READY" if not any(fail_gates.values()) else "FAIL",
        "analysis_basis": "local monitor sample output only; no paper or live execution",
        "bot_name": config.bot_name,
        "environment": config.environment,
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
        "read_only_api_boundary": {
            "account_mode": config.account_mode,
            "exchange_connection_made": False,
            "api_key_requested": False,
            "secrets_source": "environment_or_local_ignored_config_only",
            "secrets_written_to_repo": False,
            "secrets_written_to_logs": False,
            "secrets_written_to_outputs": False,
        },
        "output_paths": {key: str(path) for key, path in output_paths.items()},
        "heartbeat_schema": heartbeat_validation,
        "alerts_schema": alerts_validation,
        "safety_scan": safety_scan,
        "fail_gates": fail_gates,
        "warning_gates": {
            "single_channel_only": len(config.alerts.channels) == 1,
            "no_recovery_alert": False,
            "no_pnl_floor_check": False,
            "dedup_window_too_long": config.alerts.dedup_window_minutes > 30,
            "heartbeat_interval_too_long": config.heartbeat.interval_seconds > 120,
        },
        "monitor_hook_integration": {
            "mode": "local_stub",
            "side_effect_free": True,
            "sample_event": hook_event,
        },
        "git_commit": _git_commit(),
    }
    payload["reproducibility_hash"] = _canonical_hash(payload)
    return payload


def build_review_packet(numbers: dict[str, Any]) -> str:
    gates = numbers["fail_gates"]
    warning_gates = numbers["warning_gates"]
    return "\n".join([
        "# REVIEW-005 Packet - TASK-005 VPS Bot Monitor",
        "",
        "Analysis basis: local monitoring, logging, and alerting sample output only.",
        "No exchange connection, paper execution, or live trading approval is implied.",
        "",
        "## Scope",
        "- Created isolated `apps/monitor/` modules and a TASK-005 runner.",
        "- Generated local heartbeat parquet, alerts JSONL, setup log, and review numbers.",
        "- Monitor boundaries are observer-only and do not include trading actions or process-control actions.",
        "",
        "## Outputs",
        f"- Heartbeat rows: {numbers['heartbeat_schema']['row_count']} ({numbers['heartbeat_schema']['status']})",
        f"- Alert rows: {numbers['alerts_schema']['row_count']} ({numbers['alerts_schema']['status']})",
        f"- Setup log: `{numbers['output_paths']['setup_log']}`",
        "",
        "## Safety",
        f"- Safety scan: {numbers['safety_scan']['status']}",
        f"- Read-only boundary: exchange_connection_made={numbers['read_only_api_boundary']['exchange_connection_made']}, "
        f"api_key_requested={numbers['read_only_api_boundary']['api_key_requested']}",
        f"- Paper execution: {numbers['paper_execution_status']}",
        f"- Live trading: {numbers['live_trading_status']}",
        "",
        "## Fail Gates",
        *[f"- {name}: {str(value).lower()}" for name, value in gates.items()],
        "",
        "## Warning Gates",
        *[f"- {name}: {str(value).lower()}" for name, value in warning_gates.items()],
        "",
        "## Reproducibility",
        f"- reproducibility_hash: `{numbers['reproducibility_hash']}`",
        f"- git_commit: `{numbers['git_commit']}`",
        f"- output_date: `{numbers['run_date']}`",
    ]) + "\n"


def build_setup_log(numbers: dict[str, Any]) -> str:
    return "\n".join([
        "TASK-005 VPS Bot Monitor",
        f"run_date={numbers['run_date']}",
        f"status={numbers['status']}",
        "scope=monitoring/logging/alerting only",
        f"paper_execution_status={numbers['paper_execution_status']}",
        f"live_trading_status={numbers['live_trading_status']}",
        f"reproducibility_hash={numbers['reproducibility_hash']}",
        "",
        "fail_gates:",
        json.dumps(numbers["fail_gates"], indent=2, sort_keys=True),
        "",
        "safety_scan:",
        json.dumps(numbers["safety_scan"], indent=2, sort_keys=True),
        "",
        "heartbeat_schema:",
        json.dumps(numbers["heartbeat_schema"], indent=2, sort_keys=True),
        "",
        "alerts_schema:",
        json.dumps(numbers["alerts_schema"], indent=2, sort_keys=True),
    ]) + "\n"


def build_task005a_numbers(
    output_date: str,
    config: MonitorConfig,
    output_paths: dict[str, Path],
    channel_results: list[ChannelResult],
    safety_scan: dict[str, Any],
    test_send: bool,
) -> dict[str, Any]:
    result_rows = [result.to_dict() for result in channel_results]
    enabled_channels = [result.channel for result in channel_results if result.enabled]
    external_channels = [channel for channel in enabled_channe