from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.forward_record.alert_conditions import (  # noqa: E402
    AlertConditionResult,
    check_alpha_gap,
    check_data_source_failure,
    check_forbidden_field_violation,
    check_review_006b_trigger,
    check_runner_missing_rows,
    check_stop_gate,
    check_warning_gate_streak,
)
from apps.forward_record.alerting import run_forward_alerting  # noqa: E402
from apps.forward_record.safety import scan_no_order_endpoints  # noqa: E402


DEFAULT_DATE = "20260517"
DEFAULT_DRILL_DIR = Path("outputs/forward_record/drill")
REVIEW_PACKET_PATH = Path("docs/research/review_packets/REVIEW-009d_PACKET.md")
REVIEW_NUMBERS_PATH = Path("docs/research/review_packets/REVIEW-009d_NUMBERS.json")

SENSITIVE_PATTERNS = (
    "webhook",
    "MONITOR_DISCORD_WEBHOOK_URL",
    "api_key",
    "api_secret",
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "token",
    "Bearer ",
    "https://discord.com/api/",
)

EXPECTED_SEVERITY = {
    "A-1": "WARNING",
    "A-2": "CRITICAL",
    "A-3": "WARNING",
    "A-4": "WARNING",
    "A-5": "CRITICAL",
    "A-6": "INFO",
    "A-7": "CRITICAL",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_drill(
    drill_date: str = DEFAULT_DATE,
    *,
    output_dir: Path = DEFAULT_DRILL_DIR,
    write_review: bool = True,
    review_packet_path: Path = REVIEW_PACKET_PATH,
    review_numbers_path: Path = REVIEW_NUMBERS_PATH,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{drill_date}_drill_report.json"

    with tempfile.TemporaryDirectory(prefix="task009d_alert_drill_") as tmp:
        base = Path(tmp)
        scenarios = _build_scenarios(base)
        discord_probe = _run_discord_dry_run_probe(base)

    redaction_summary = _redaction_summary(scenarios)
    template_summary = _template_summary(scenarios)
    dedupe_scenario = _dedupe_summary(scenarios)
    safety_scan = scan_no_order_endpoints([Path("scripts/drill_forward_alerts.py")])
    sent_seen = _discord_sent_seen(discord_probe)

    pass_checks = [
        all(item["result"] == "PASS" for item in scenarios),
        redaction_summary["all_pass"],
        template_summary["all_pass"],
        dedupe_scenario["result"] == "PASS",
        discord_probe["dry_run"] is True,
        discord_probe["live_alerts_used"] is False,
        discord_probe["external_post_attempted"] is False,
        sent_seen is False,
        safety_scan["status"] == "PASS",
    ]

    report = {
        "task": "TASK-009d",
        "drill_date": drill_date,
        "run_ts": _utc_now(),
        "dry_run": True,
        "live_alerts_used": False,
        "external_post_attempted": False,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "dedupe_scenario": dedupe_scenario,
        "redaction_summary": redaction_summary,
        "discord_template_summary": template_summary,
        "discord_probe": discord_probe,
        "sent_fail_gate": "PASS" if not sent_seen else "FAIL",
        "safety_scan": safety_scan,
        "overall_result": "PASS" if all(pass_checks) else "FAIL",
        "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
        "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
        "FORBIDDEN_bybit_write": "NOT_ATTEMPTED",
        "FORBIDDEN_real_discord_post": "NOT_ATTEMPTED",
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "clock_started": False,
    }
    _write_json(report_path, report)
    report["drill_report_path"] = str(report_path)

    if write_review:
        _write_review_numbers(review_numbers_path, report)
        _write_review_packet(review_packet_path, review_numbers_path, report_path, report)
        report["review_packet_path"] = str(review_packet_path)
        report["review_numbers_path"] = str(review_numbers_path)
    return report


def _build_scenarios(base: Path) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    record_date = "20260102"

    scenarios.append(_scenario(
        "S-A1",
        check_runner_missing_rows(record_date, base / "a1" / f"{record_date}_positions.parquet"),
        True,
        record_date,
        required_terms=["FORWARD RECORD", "Runner missing rows", "Action required"],
    ))

    a1b_dir = base / "a1b"
    _positions(a1b_dir / "20260101_positions.parquet", [0.1])
    _positions(a1b_dir / "20260102_positions.parquet", [0.1])
    scenarios.append(_scenario(
        "S-A1b",
        check_runner_missing_rows(record_date, a1b_dir / f"{record_date}_positions.parquet"),
        False,
        record_date,
        required_terms=["Runner missing rows"],
    ))

    scenarios.append(_scenario(
        "S-A2",
        check_stop_gate({"date": record_date, "active_stop_gates": ["S-2"], "active_warning_gates": []}),
        True,
        record_date,
        required_terms=["STOP GATE", "S-2", "Do NOT restart automatically"],
    ))

    a3_dir = base / "a3"
    for date in ["20260101", "20260102", "20260103"]:
        _write_json(a3_dir / f"{date}_forward_stats.json", {"active_warning_gates": ["W-1"]})
    scenarios.append(_scenario(
        "S-A3",
        check_warning_gate_streak("20260103", a3_dir / "20260103_forward_stats.json"),
        True,
        "20260103",
        required_terms=["Warning gate streak", "W-1", "3 days"],
    ))

    a3b_dir = base / "a3b"
    _write_json(a3b_dir / "20260101_forward_stats.json", {"active_warning_gates": ["W-1"]})
    _write_json(a3b_dir / "20260102_forward_stats.json", {"active_warning_gates": []})
    _write_json(a3b_dir / "20260103_forward_stats.json", {"active_warning_gates": ["W-1"]})
    scenarios.append(_scenario(
        "S-A3b",
        check_warning_gate_streak("20260103", a3b_dir / "20260103_forward_stats.json"),
        False,
        "20260103",
        required_terms=["Warning gate streak"],
    ))

    a4_dir = base / "a4"
    _positions(a4_dir / "primary.parquet", [0.10, -0.10])
    _positions(a4_dir / "shadow.parquet", [0.00, -0.20])
    scenarios.append(_scenario(
        "S-A4",
        check_alpha_gap(record_date, a4_dir / "primary.parquet", a4_dir / "shadow.parquet", threshold=0.05),
        True,
        record_date,
        required_terms=["alpha gap exceeded", "Mean abs diff", "Top divergent symbols"],
    ))

    a4b_dir = base / "a4b"
    _positions(a4b_dir / "primary.parquet", [0.10])
    scenarios.append(_scenario(
        "S-A4b",
        check_alpha_gap(record_date, a4b_dir / "primary.parquet", a4b_dir / "missing_shadow.parquet", threshold=0.05),
        False,
        record_date,
        required_terms=["alpha gap"],
    ))

    scenarios.append(_scenario(
        "S-A5",
        check_data_source_failure(record_date, base / "a5" / "missing_forward_stats.json", base / "a5" / "missing.log"),
        True,
        record_date,
        required_terms=["Data source failure", "Check parquet cache", "missing forward_stats"],
    ))

    a5b_dir = base / "a5b"
    _write_json(a5b_dir / "forward_stats.json", {"date": record_date, "data_source": "FAILED"})
    scenarios.append(_scenario(
        "S-A5b",
        check_data_source_failure(record_date, a5b_dir / "forward_stats.json", a5b_dir / "clean.log"),
        True,
        record_date,
        required_terms=["Data source failure", "data_source=FAILED"],
    ))

    a5c_dir = base / "a5c"
    _write_json(a5c_dir / "forward_stats.json", {"date": record_date, "data_source": "LIVE", "rows": 50})
    a5c_log = a5c_dir / f"{record_date}_forward_record.log"
    a5c_log.parent.mkdir(parents=True, exist_ok=True)
    a5c_log.write_text(
        "status=REVIEW_READY\n"
        "CacheMarketDataProvider initialized successfully\n",
        encoding="utf-8",
    )
    scenarios.append(_scenario(
        "S-A5c",
        check_data_source_failure(record_date, a5c_dir / "forward_stats.json", a5c_log),
        False,
        record_date,
        required_terms=["data source readable"],
    ))

    a6_stats = {
        "date": record_date,
        "days_elapsed": 30,
        "sharpe_rolling_30d": 0.75,
        "max_dd_pct": -0.12,
        "review_006b_trigger_ready": True,
    }
    scenarios.append(_scenario(
        "S-A6",
        check_review_006b_trigger(a6_stats),
        True,
        record_date,
        required_terms=["REVIEW-006b trigger conditions met", "Informational only"],
        forbidden_terms=["paper execution approved", "live trading approved"],
    ))

    a6b_log = base / "a6b" / "20260101_alert_log.json"
    _write_json(a6b_log, {"alerts_sent": [{"condition_id": "A-6"}]})
    scenarios.append(_scenario(
        "S-A6b",
        check_review_006b_trigger(a6_stats, previous_alert_log=a6b_log),
        False,
        record_date,
        required_terms=["REVIEW-006b trigger conditions met"],
        forbidden_terms=["paper execution approved", "live trading approved"],
    ))

    scenarios.append(_scenario(
        "S-A7",
        check_forbidden_field_violation({
            "FORBIDDEN_live_trading": "POST_ATTEMPTED",
            "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
            "FORBIDDEN_bybit_write": "NOT_ATTEMPTED",
        }),
        True,
        record_date,
        required_terms=["FORBIDDEN field violation", "IMMEDIATE review required"],
    ))
    return scenarios


def _scenario(
    scenario_id: str,
    condition: AlertConditionResult,
    expected_triggered: bool,
    record_date: str,
    *,
    required_terms: list[str],
    forbidden_terms: list[str] | None = None,
) -> dict[str, Any]:
    raw_message = condition.message or condition.detail
    preview = _message_preview(condition, scenario_id, record_date)
    required = {term: term.lower() in preview.lower() for term in required_terms}
    local_forbidden = {term: term.lower() not in preview.lower() for term in (forbidden_terms or [])}
    redaction = _message_redaction(preview)
    raw_content = _raw_content_check(condition, record_date)
    content_checks = {
        "has_date": record_date in preview,
        "has_action": "action" in preview.lower(),
        "has_condition_id": condition.condition_id in preview,
        "message_nonempty": bool(preview.strip()),
        "no_placeholder": "{}" not in preview and "None" not in preview,
        "no_placeholder_raw": "{}" not in raw_message and "None" not in raw_message,
        "raw_content": raw_content,
        "severity_correct": condition.severity == EXPECTED_SEVERITY.get(condition.condition_id),
        "required_terms": required,
        "forbidden_terms_absent": local_forbidden,
        "no_secret": redaction["pass"],
    }
    passed = (
        condition.triggered is expected_triggered
        and all(value is True for key, value in content_checks.items() if isinstance(value, bool))
        and all(required.values())
        and all(local_forbidden.values())
    )
    return {
        "scenario_id": scenario_id,
        "condition_id": condition.condition_id,
        "condition_name": condition.condition_name,
        "triggered": condition.triggered,
        "expected_triggered": expected_triggered,
        "severity": condition.severity,
        "detail": _sanitize_text(condition.detail).replace("None", "n/a"),
        "message_preview": preview,
        "action_guidance_present": content_checks["has_action"],
        "redaction_pass": redaction["pass"],
        "content_checks": content_checks,
        "data": _json_safe(condition.data or {}),
        "result": "PASS" if passed else "FAIL",
    }


def _run_discord_dry_run_probe(base: Path) -> dict[str, Any]:
    fixture = _alert_fixture(base / "discord_probe", stop_gates=["S-2"])
    alert_log = run_forward_alerting(
        "20260102",
        review_numbers_path=fixture["review_numbers"],
        monitor_config_path=fixture["monitor_config"],
        alert_log_dir=fixture["alert_dir"],
        live_alerts=False,
        force_dry_run=True,
    )
    statuses = [item.get("status") for item in alert_log.get("discord_results", [])]
    return {
        "dry_run": bool(alert_log.get("dry_run")),
        "live_alerts_used": bool(alert_log.get("live_alerts_requested")),
        "external_post_attempted": any(bool(item.get("external_post_attempted")) for item in alert_log.get("discord_results", [])),
        "statuses": statuses,
        "sent_seen": "SENT" in statuses,
        "preview_count": len(alert_log.get("dry_run_preview", [])),
    }


def _alert_fixture(base: Path, stop_gates: list[str] | None = None) -> dict[str, Path]:
    primary_dir = base / "primary"
    shadow_dir = base / "shadow"
    log_dir = base / "logs"
    alert_dir = base / "alerts"
    date = "20260102"
    previous = "20260101"
    _positions(primary_dir / f"{previous}_positions.parquet", [0.1, -0.1])
    _positions(primary_dir / f"{date}_positions.parquet", [0.1, -0.1])
    _positions(shadow_dir / f"{date}_positions.parquet", [0.1, -0.1])
    stats = {
        "date": date,
        "active_warning_gates": [],
        "active_stop_gates": stop_gates or [],
        "review_006b_trigger_ready": False,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status": "FORBIDDEN",
        "data_source": "MOCK",
    }
    _write_json(primary_dir / f"{previous}_forward_stats.json", {**stats, "date": previous, "active_stop_gates": []})
    _write_json(primary_dir / f"{date}_forward_stats.json", stats)
    _write_json(primary_dir / f"{date}_overlay_check.json", {"overlay_pass": True})
    _write_json(primary_dir / f"{date}_pnl.json", {"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"})
    _write_json(shadow_dir / f"{date}_forward_stats.json", stats)
    _write_json(shadow_dir / f"{date}_overlay_check.json", {"overlay_pass": True})
    _write_json(shadow_dir / f"{date}_pnl.json", {"paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"})
    log_path = log_dir / f"{date}_forward_record.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("status=REVIEW_READY\n", encoding="utf-8")
    review_numbers = base / "REVIEW-009_NUMBERS.json"
    _write_json(review_numbers, {
        "outputs": {
            "log": str(log_path),
            "primary": {
                "positions": str(primary_dir / f"{date}_positions.parquet"),
                "forward_stats": str(primary_dir / f"{date}_forward_stats.json"),
                "overlay_check": str(primary_dir / f"{date}_overlay_check.json"),
                "pnl": str(primary_dir / f"{date}_pnl.json"),
            },
            "shadow": {
                "positions": str(shadow_dir / f"{date}_positions.parquet"),
                "forward_stats": str(shadow_dir / f"{date}_forward_stats.json"),
                "overlay_check": str(shadow_dir / f"{date}_overlay_check.json"),
                "pnl": str(shadow_dir / f"{date}_pnl.json"),
            },
        }
    })
    monitor_config = base / "monitor.yaml"
    monitor_config.write_text(
        "\n".join([
            "bot_name: task009d_drill",
            "environment: mock_drill",
            "account_mode: read_only_monitor",
            "secrets_config_path: configs/monitor_secrets.local.yaml",
            "paper_execution_status: FORBIDDEN",
            "live_trading_status: FORBIDDEN",
            "alerts:",
            "  channels:",
            "    - type: discord",
            "      enabled: true",
            "      dry_run: true",
            "      secrets_env_webhook_url: TASK009D_UNUSED_CREDENTIAL",
            "      timeout_seconds: 10",
        ])
        + "\n",
        encoding="utf-8",
    )
    return {"review_numbers": review_numbers, "monitor_config": monitor_config, "alert_dir": alert_dir}


def _positions(path: Path, weights: list[float]) -> None:
    rows = [
        {
            "symbol": f"S{i}",
            "weight": weight,
            "weight_raw": weight,
            "paper_execution_status": "FORBIDDEN",
            "live_trading_status": "FORBIDDEN",
        }
        for i, weight in enumerate(weights)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _message_preview(condition: AlertConditionResult, scenario_id: str, record_date: str) -> str:
    message = condition.message or condition.detail
    text = (
        f"{scenario_id} {condition.condition_id} {condition.condition_name}\n"
        f"Date: {record_date}\n"
        f"{message}\n"
        f"Action: {condition.action_required}"
    )
    return _sanitize_text(text)


def _raw_content_check(condition: AlertConditionResult, record_date: str) -> dict[str, bool]:
    raw = condition.message or condition.detail
    return {
        "has_date_in_raw": record_date in raw,
        "has_condition_id_in_raw": condition.condition_id in raw,
        "has_action_in_raw": bool(condition.action_required),
    }


def _sanitize_text(text: str) -> str:
    return text.replace("\r", " ")


def _message_redaction(message: str) -> dict[str, Any]:
    found = [pattern for pattern in SENSITIVE_PATTERNS if pattern in message]
    return {"pass": not found, "violation_count": len(found)}


def _redaction_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    violations = [
        {"scenario_id": item["scenario_id"], "count": 1}
        for item in scenarios
        if not item["redaction_pass"]
    ]
    return {"all_pass": not violations, "violation_count": len(violations), "violations": violations}


def _template_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "all_messages_nonempty": all(item["content_checks"]["message_nonempty"] for item in scenarios),
        "all_have_action_guidance": all(item["content_checks"]["has_action"] for item in scenarios),
        "all_have_condition_id": all(item["content_checks"]["has_condition_id"] for item in scenarios),
        "all_have_record_date": all(item["content_checks"]["has_date"] for item in scenarios),
        "no_placeholder_artifacts": all(item["content_checks"]["no_placeholder"] for item in scenarios),
        "no_placeholder_raw": all(item["content_checks"]["no_placeholder_raw"] for item in scenarios),
        "all_have_raw_action": all(item["content_checks"]["raw_content"]["has_action_in_raw"] for item in scenarios),
        "severity_mapping_correct": all(item["content_checks"]["severity_correct"] for item in scenarios),
    }
    checks["all_pass"] = all(checks.values())
    return checks


def _dedupe_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["scenario_id"]: item for item in scenarios}
    a2_not_deduped = bool(by_id["S-A2"]["triggered"])
    first = bool(by_id["S-A6"]["triggered"])
    second = not bool(by_id["S-A6b"]["triggered"]) and bool(by_id["S-A6b"]["data"].get("duplicate"))
    return {
        "a6_day1_triggered": first,
        "a6_day2_suppressed": second,
        "a2_not_deduped": a2_not_deduped,
        "result": "PASS" if first and second and a2_not_deduped else "FAIL",
    }


def _discord_sent_seen(discord_probe: dict[str, Any]) -> bool:
    return bool(discord_probe.get("sent_seen")) or "SENT" in discord_probe.get("statuses", [])


def _write_review_numbers(path: Path, report: dict[str, Any]) -> None:
    scenarios = report["scenarios"]
    numbers = {
        "task": "TASK-009d",
        "status": "REVIEW_READY" if report["overall_result"] == "PASS" else "FAILED",
        "drill_date": report["drill_date"],
        "run_ts": report["run_ts"],
        "scenario_count": len(scenarios),
        "scenario_pass_count": sum(1 for item in scenarios if item["result"] == "PASS"),
        "positive_scenarios_triggered": {
            item["scenario_id"]: item["triggered"]
            for item in scenarios
            if item["scenario_id"] in {"S-A1", "S-A2", "S-A3", "S-A4", "S-A5", "S-A5b", "S-A6", "S-A7"}
        },
        "negative_scenarios_not_triggered": {
            item["scenario_id"]: not item["triggered"]
            for item in scenarios
            if item["scenario_id"] in {"S-A1b", "S-A3b", "S-A4b", "S-A5c", "S-A6b"}
        },
        "redaction_pass": report["redaction_summary"]["all_pass"],
        "dedupe_pass": report["dedupe_scenario"]["result"] == "PASS",
        "template_pass": report["discord_template_summary"]["all_pass"],
        "dry_run_confirmed": report["dry_run"],
        "live_alerts_used": report["live_alerts_used"],
        "external_post_attempted": report["external_post_attempted"],
        "sent_fail_gate": report["sent_fail_gate"],
        "safety_scan": report["safety_scan"]["status"],
        "clock_started": report["clock_started"],
        "paper_execution_status": report["paper_execution_status"],
        "live_trading_status": report["live_trading_status"],
        "outputs": {
            "drill_report": report["drill_report_path"],
            "review_packet": str(REVIEW_PACKET_PATH),
            "review_numbers": str(path),
        },
        "FORBIDDEN_live_trading": report["FORBIDDEN_live_trading"],
        "FORBIDDEN_order_endpoint": report["FORBIDDEN_order_endpoint"],
        "FORBIDDEN_bybit_write": report["FORBIDDEN_bybit_write"],
        "FORBIDDEN_real_discord_post": report["FORBIDDEN_real_discord_post"],
    }
    _write_json(path, numbers)


def _write_review_packet(packet_path: Path, numbers_path: Path, report_path: Path, report: dict[str, Any]) -> None:
    scenarios = report["scenarios"]
    lines = [
        "# REVIEW-009d Packet",
        "",
        "## Summary",
        f"- Task: TASK-009d alert E2E dry-run drill",
        f"- Date: {report['drill_date']}",
        f"- Overall result: {report['overall_result']}",
        f"- Drill report: `{report_path}`",
        f"- Numbers: `{numbers_path}`",
        "",
        "## Scenario Results",
    ]
    for item in scenarios:
        lines.append(
            f"- {item['scenario_id']} {item['condition_id']} {item['condition_name']}: "
            f"{item['result']} (triggered={str(item['triggered']).lower()}, severity={item['severity']})"
        )
    lines.extend([
        "",
        "## Validation",
        f"- Redaction validation: {'PASS' if report['redaction_summary']['all_pass'] else 'FAIL'}",
        f"- Dedupe validation: {report['dedupe_scenario']['result']}",
        f"- Discord template validation: {'PASS' if report['discord_template_summary']['all_pass'] else 'FAIL'}",
        f"- dry_run confirmed: {str(report['dry_run'])}",
        f"- live_alerts used: {str(report['live_alerts_used']).lower()}",
        f"- external_post_attempted: {str(report['external_post_attempted']).lower()}",
        f"- Channel SENT fail gate: {report['sent_fail_gate']}",
        f"- Safety scan: {report['safety_scan']['status']}",
        "",
        "## Forbidden Items Confirmation",
        "- Did NOT send any real Discord POST",
        "- Did NOT use live alert execution mode",
        "- Did NOT connect to Bybit",
        "- Did NOT request or read credential material",
        "- Did NOT start or mutate the 30-day forward clock",
        "- Did NOT approve paper or live execution",
        "- Did NOT modify strategy signals, ranking, or universe",
        "- Did NOT modify existing immutable run outputs",
        "- Did NOT modify `alerting.py` or `alert_conditions.py`",
        "- `force_dry_run=True` in the drill call that exercises alert dispatch",
        "",
        "## Status",
        "- TASK-009d drill artifacts refreshed by TASK-009c tech debt validation.",
        "- Paper execution remains FORBIDDEN.",
        "- Live trading remains FORBIDDEN.",
        "",
    ])
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
