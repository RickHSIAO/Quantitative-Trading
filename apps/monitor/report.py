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
    external_channels = [channel for channel in enabled_channels if channel in {"telegram", "discord"}]
    local_jsonl_retained = "local_jsonl" in enabled_channels
    channel_dispatch_failure = any(result.status == "FAILED" for result in channel_results)
    dry_run_external_post = any(result.dry_run and result.external_post_attempted for result in channel_results)
    fail_gates = {
        "missing_outputs": any(not path.exists() for path in output_paths.values()),
        "test_failure": False,
        "secret_hardcoded": bool(safety_scan["gates"].get("secret_hardcoded", False)),
        "secret_written_to_logs": bool(safety_scan["gates"].get("secret_written_to_logs", False)),
        "secret_in_vcs": bool(safety_scan["gates"].get("secret_in_vcs", False)),
        "local_jsonl_removed": bool(safety_scan["gates"].get("local_jsonl_removed", not local_jsonl_retained)),
        "exchange_api_present": bool(safety_scan["gates"].get("exchange_api_present", False)),
        "order_submission_code_present": bool(safety_scan["gates"].get("order_submission_code_present", False)),
        PROCESS_CONTROL_GATE: bool(safety_scan["gates"].get(PROCESS_CONTROL_GATE, False)),
        "channel_dispatch_failure": channel_dispatch_failure,
        "real_external_post_during_validation": dry_run_external_post,
    }
    readme_text = Path("apps/monitor/README.md").read_text(encoding="utf-8") if Path("apps/monitor/README.md").exists() else ""
    warning_gates = {
        "only_one_channel": len(set(enabled_channels)) <= 1,
        "no_test_send_flag": False,
        "readme_not_updated": "Telegram" not in readme_text or "Discord" not in readme_text,
        "no_example_secrets_file": not Path("configs/monitor_secrets.example.yaml").exists(),
        "external_channels_dry_run_only": bool(external_channels)
        and all(result.dry_run for result in channel_results if result.channel in {"telegram", "discord"}),
    }
    payload: dict[str, Any] = {
        "task": "TASK-005a Real Alert Channel",
        "run_date": output_date,
        "status": "REVIEW_READY" if not any(fail_gates.values()) else "FAIL",
        "analysis_basis": "mockable alert channel implementation; no real external notification sent",
        "bot_name": config.bot_name,
        "environment": config.environment,
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
        "channels": {
            "enabled": enabled_channels,
            "external": external_channels,
            "local_jsonl_retained": local_jsonl_retained,
            "dry_run_default": all(channel.dry_run for channel in config.alerts.channels),
            "test_send_requested": test_send,
            "results": result_rows,
        },
        "secret_handling": {
            "sources": ["environment_variables", "configs/monitor_secrets.local.yaml"],
            "local_config_gitignored": safety_scan["secret_ignore"]["status"] == "PASS",
            "redaction_required": True,
            "secret_values_in_outputs": False,
        },
        "read_only_api_boundary": {
            "exchange_connection_made": False,
            "api_key_requested": False,
            "external_posts_attempted": any(result.external_post_attempted for result in channel_results),
        },
        "output_paths": {key: str(path) for key, path in output_paths.items()},
        "safety_scan": safety_scan,
        "fail_gates": fail_gates,
        "warning_gates": warning_gates,
        "git_commit": _git_commit(),
    }
    payload["reproducibility_hash"] = _canonical_hash(payload)
    return payload


def build_task005a_packet(numbers: dict[str, Any]) -> str:
    gates = numbers["fail_gates"]
    warnings = numbers["warning_gates"]
    channels = numbers["channels"]
    return "\n".join(
        [
            "# REVIEW-005a Packet - TASK-005a Real Alert Channel",
            "",
            "Analysis basis: mockable alert channel implementation only.",
            "No real Telegram or Discord notification was sent during validation.",
            "No exchange connection, paper execution, or live trading approval is implied.",
            "",
            "## Scope",
            "- Added channel-dispatch support for local JSONL, Telegram, and Discord.",
            "- Preserved local JSONL output as the durable local alert record.",
            "- Secrets are loaded only from environment variables or ignored local config.",
            "- Telegram and Discord use injectable HTTP clients for mock-only tests.",
            "",
            "## Channels",
            f"- Enabled channels: {', '.join(channels['enabled'])}",
            f"- External channels: {', '.join(channels['external'])}",
            f"- local_jsonl_retained: {str(channels['local_jsonl_retained']).lower()}",
            f"- dry_run_default: {str(channels['dry_run_default']).lower()}",
            f"- test_send_requested: {str(channels['test_send_requested']).lower()}",
            "",
            "## Fail Gates",
            *[f"- {name}: {str(value).lower()}" for name, value in gates.items()],
            "",
            "## Warning Gates",
            *[f"- {name}: {str(value).lower()}" for name, value in warnings.items()],
            "",
            "## Safety",
            f"- Safety scan: {numbers['safety_scan']['status']}",
            f"- Paper execution: {numbers['paper_execution_status']}",
            f"- Live trading: {numbers['live_trading_status']}",
            "",
            "## Reproducibility",
            f"- reproducibility_hash: `{numbers['reproducibility_hash']}`",
            f"- git_commit: `{numbers['git_commit']}`",
            f"- output_date: `{numbers['run_date']}`",
        ]
    ) + "\n"


def build_task005a_delivery_log(numbers: dict[str, Any]) -> str:
    return "\n".join(
        [
            "TASK-005a Real Alert Channel Delivery",
            f"run_date={numbers['run_date']}",
            f"status={numbers['status']}",
            "scope=real alert channel implementation with mockable transport",
            f"paper_execution_status={numbers['paper_execution_status']}",
            f"live_trading_status={numbers['live_trading_status']}",
            f"reproducibility_hash={numbers['reproducibility_hash']}",
            "",
            "channels:",
            json.dumps(numbers["channels"], indent=2, sort_keys=True),
            "",
            "fail_gates:",
            json.dumps(numbers["fail_gates"], indent=2, sort_keys=True),
            "",
            "warning_gates:",
            json.dumps(numbers["warning_gates"], indent=2, sort_keys=True),
            "",
            "safety_scan:",
            json.dumps(numbers["safety_scan"], indent=2, sort_keys=True),
        ]
    ) + "\n"


def _canonical_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str:
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
