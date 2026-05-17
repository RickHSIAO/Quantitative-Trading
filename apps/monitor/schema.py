from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


HEARTBEAT_COLUMNS = [
    "timestamp",
    "bot_name",
    "environment",
    "status",
    "equity",
    "nav",
    "active_positions",
    "last_order_timestamp",
    "api_latency_ms",
    "process_alive",
    "paper_execution_status",
    "live_trading_status",
    "warning_count",
    "critical_count",
]

ALERT_COLUMNS = [
    "timestamp",
    "severity",
    "category",
    "message",
    "dedupe_key",
    "source",
    "action_required",
    "paper_execution_status",
    "live_trading_status",
]

VALID_HEARTBEAT_STATUS = {"OK", "WARNING", "CRITICAL", "UNKNOWN"}
VALID_ALERT_SEVERITY = {"INFO", "WARNING", "CRITICAL"}


def validate_heartbeat_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for index, row in enumerate(rows):
        missing = [column for column in HEARTBEAT_COLUMNS if column not in row]
        if missing:
            errors.append(f"row {index} missing columns: {missing}")
            continue
        if str(row["status"]) not in VALID_HEARTBEAT_STATUS:
            errors.append(f"row {index} invalid status: {row['status']}")
        for numeric in ["equity", "nav", "api_latency_ms"]:
            try:
                float(row[numeric])
            except (TypeError, ValueError):
                errors.append(f"row {index} invalid numeric column: {numeric}")
        for integer in ["active_positions", "warning_count", "critical_count"]:
            try:
                int(row[integer])
            except (TypeError, ValueError):
                errors.append(f"row {index} invalid integer column: {integer}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "row_count": len(rows)}


def validate_heartbeat_parquet(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "FAIL", "errors": [f"missing heartbeat parquet: {path}"], "row_count": 0}
    frame = pd.read_parquet(path)
    return validate_heartbeat_rows(frame.to_dict(orient="records"))


def validate_alert_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for index, row in enumerate(rows):
        missing = [column for column in ALERT_COLUMNS if column not in row]
        if missing:
            errors.append(f"row {index} missing columns: {missing}")
            continue
        if str(row["severity"]) not in VALID_ALERT_SEVERITY:
            errors.append(f"row {index} invalid severity: {row['severity']}")
        if not str(row["dedupe_key"]):
            errors.append(f"row {index} empty dedupe_key")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "row_count": len(rows)}


def validate_alerts_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "FAIL", "errors": [f"missing alerts jsonl: {path}"], "row_count": 0}
    rows = []
    errors = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: {exc}")
    result = validate_alert_rows(rows)
    result["errors"] = errors + result["errors"]
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result
