from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from apps.forward_record.alert_conditions import (
    AlertConditionResult,
    check_alpha_gap,
    check_data_source_failure,
    check_forbidden_field_violation,
    check_review_006b_trigger,
    check_runner_missing_rows,
    check_stop_gate,
    check_warning_gate_streak,
    dated_path_from_template,
)
from apps.monitor.alerts import Alert
from apps.monitor.channels.base import ChannelResult
from apps.monitor.channels.discord import send_discord_alerts
from apps.monitor.config import ChannelConfig, load_monitor_config


ALERT_LOG_DIR = Path("outputs/forward_record/alerts")
REVIEW_NUMBERS_PATH = Path("docs/research/review_packets/REVIEW-009_NUMBERS.json")
MONITOR_CONFIG_PATH = Path("configs/monitor.yaml")
FORWARD_RECORD_CONFIG_PATH = Path("configs/forward_record.yaml")


def run_forward_alerting(
    record_date: str,
    *,
    review_numbers_path: Path = REVIEW_NUMBERS_PATH,
    forward_record_config_path: Path = FORWARD_RECORD_CONFIG_PATH,
    monitor_config_path: Path = MONITOR_CONFIG_PATH,
    alert_log_dir: Path = ALERT_LOG_DIR,
    live_alerts: bool = False,
    force_dry_run: bool = True,
    warning_streak_days: int = 3,
    alpha_gap_threshold: float = 0.05,
) -> dict[str, Any]:
    paths = _resolve_runtime_paths(review_numbers_path, forward_record_config_path, record_date)
    stats = _read_json(paths["primary"]["forward_stats"])
    conditions = evaluate_alert_conditions(
        record_date,
        paths,
        stats,
        alert_log_dir=alert_log_dir,
        warning_streak_days=warning_streak_days,
        alpha_gap_threshold=alpha_gap_threshold,
    )
    triggered = [condition for condition in conditions if condition.triggered]
    monitor_config = load_monitor_config(monitor_config_path)
    discord_channel = _discord_channel(monitor_config.alerts.channels)
    alert_dry_run = True if force_dry_run or not live_alerts else discord_channel.dry_run
    effective_channel = replace(discord_channel, dry_run=alert_dry_run)
    alerts = [_condition_to_alert(condition, monitor_config, record_date) for condition in triggered]
    discord_results: list[dict[str, Any]] = []
    if alerts:
        result = send_discord_alerts(
            config=monitor_config,
            channel=effective_channel,
            alerts=alerts,
            test_send=False,
        )
        discord_results.append(result.to_dict())

    safety_fields = _safety_fields()
    alert_log = {
        "record_date": record_date,
        "run_ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dry_run": alert_dry_run,
        "live_alerts_requested": bool(live_alerts),
        "health_check": run_daily_health_check(paths),
        "alerts_evaluated": [condition.to_dict() for condition in conditions],
        "alerts_sent": [condition.to_dict() for condition in triggered],
        "discord_results": discord_results,
        "dry_run_preview": [alert.to_dict() for alert in alerts] if alert_dry_run else [],
        "review_006b_trigger_ready": bool(stats.get("review_006b_trigger_ready")),
        **safety_fields,
    }
    alert_log_dir.mkdir(parents=True, exist_ok=True)
    alert_log_path = alert_log_dir / f"{record_date}_alert_log.json"
    alert_log_path.write_text(json.dumps(_json_safe(alert_log), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    alert_log["alert_log_path"] = str(alert_log_path)
    return alert_log


def evaluate_alert_conditions(
    record_date: str,
    paths: dict[str, Any],
    stats: dict[str, Any],
    *,
    alert_log_dir: Path = ALERT_LOG_DIR,
    warning_streak_days: int = 3,
    alpha_gap_threshold: float = 0.05,
) -> list[AlertConditionResult]:
    previous_date = _previous_yyyymmdd(record_date)
    previous_alert_log = alert_log_dir / f"{previous_date}_alert_log.json"
    safety = _safety_fields()
    return [
        check_runner_missing_rows(record_date, paths["primary"]["positions"]),
        check_stop_gate(stats),
        check_warning_gate_streak(record_date, paths["primary"]["forward_stats"], warning_streak_days),
        check_alpha_gap(record_date, paths["primary"]["positions"], paths["shadow"].get("positions", Path("__missing_shadow__")), alpha_gap_threshold),
        check_data_source_failure(record_date, paths["primary"]["forward_stats"], paths["log"]),
        check_review_006b_trigger(stats, previous_alert_log),
        check_forbidden_field_violation(safety),
    ]


def resolve_forward_output_paths(review_numbers_path: Path, record_date: str) -> dict[str, Any]:
    numbers = _read_json(review_numbers_path)
    outputs = numbers.get("outputs", {})
    primary = {key: dated_path_from_template(Path(value), record_date) for key, value in outputs.get("primary", {}).items()}
    shadow = {key: dated_path_from_template(Path(value), record_date) for key, value in outputs.get("shadow", {}).items()}
    log = dated_path_from_template(Path(outputs.get("log", f"outputs/logs/prev3y_crypto/{record_date}_forward_record.log")), record_date)
    return {
        "review_numbers": review_numbers_path,
        "primary": primary,
        "shadow": shadow,
        "log": log,
    }


def resolve_forward_output_paths_from_config(config_path: Path, record_date: str) -> dict[str, Any]:
    raw = _load_forward_record_config(config_path)
    outputs = raw.get("output_paths", {})
    primary = {key: dated_path_from_template(Path(value), record_date) for key, value in outputs.get("primary", {}).items()}
    shadow = {key: dated_path_from_template(Path(value), record_date) for key, value in outputs.get("shadow", {}).items()}
    log = dated_path_from_template(Path(outputs.get("log", f"outputs/logs/prev3y_crypto/{{date}}_forward_record.log")), record_date)
    return {
        "forward_record_config": config_path,
        "primary": primary,
        "shadow": shadow,
        "log": log,
    }


def run_daily_health_check(paths: dict[str, Any]) -> dict[str, Any]:
    primary = paths["primary"]
    log_path = paths["log"]
    return {
        "primary_positions_present": _file_nonempty(primary.get("positions")),
        "forward_stats_present": _file_nonempty(primary.get("forward_stats")),
        "overlay_check_present": _file_nonempty(primary.get("overlay_check")),
        "log_present": _file_nonempty(log_path),
        "runner_exit_success": _runner_exit_success(log_path),
    }


def _condition_to_alert(condition: AlertConditionResult, monitor_config: Any, record_date: str) -> Alert:
    return Alert(
        timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        severity=condition.severity,
        category=f"FORWARD_RECORD_{condition.condition_id}",
        message=condition.message or condition.detail,
        dedupe_key=f"forward_record:{condition.condition_id}:{record_date}",
        source="forward_record",
        action_required=condition.action_required,
        paper_execution_status=monitor_config.paper_execution_status,
        live_trading_status=monitor_config.live_trading_status,
    )


def _discord_channel(channels: tuple[ChannelConfig, ...]) -> ChannelConfig:
    for channel in channels:
        if channel.type == "discord":
            return channel
    return ChannelConfig(type="discord", enabled=False, dry_run=True)


def _safety_fields() -> dict[str, str]:
    return {
        "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
        "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
        "FORBIDDEN_bybit_write": "NOT_ATTEMPTED",
    }


    return json.loads(path.read_text(encoding="utf-8"))



def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_runtime_paths(review_numbers_path: Path, forward_record_config_path: Path, record_date: str) -> dict[str, Any]:
    if forward_record_config_path != FORWARD_RECORD_CONFIG_PATH:
        return resolve_forward_output_paths_from_config(forward_record_config_path, record_date)
    if review_numbers_path != REVIEW_NUMBERS_PATH:
        return resolve_forward_output_paths(review_numbers_path, record_date)
    if forward_record_config_path.exists():
        return resolve_forward_output_paths_from_config(forward_record_config_path, record_date)
    return resolve_forward_output_paths(review_numbers_path, record_date)


def _file_nonempty(path: Path | None) -> bool:
    return bool(path and path.exists() and path.stat().st_size > 0)


def _runner_exit_success(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return "status=REVIEW_READY" in text or "status=REVIEW" in text


def _previous_yyyymmdd(date: str) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date, "%Y%m%d").date()
    return (d - timedelta(days=1)).strftime("%Y%m%d")


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _load_forward_record_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(text)
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"forward record config must be a mapping: {path}")
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, out)]
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value:
            parent[key] = value
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return out
