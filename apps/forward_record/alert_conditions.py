from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class AlertConditionResult:
    condition_id: str
    condition_name: str
    triggered: bool
    severity: str
    detail: str
    message: str = ""
    action_required: str = "review_forward_record"
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.message is None:
            raise ValueError("AlertConditionResult.message must not be None; use empty string")
        if self.action_required is None:
            raise ValueError("AlertConditionResult.action_required must not be None")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["data"] = self.data or {}
        return payload


@dataclass(frozen=True)
class AlphaGapResult:
    skipped: bool
    mean_abs_diff: float | None
    threshold: float
    symbol_count: int
    unmatched_primary: int
    unmatched_shadow: int
    top_symbols: list[dict[str, Any]]


def last_n_calendar_dates(record_date: str, days: int) -> list[str]:
    end = datetime.strptime(record_date, "%Y%m%d").date()
    return [(end - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(days - 1, -1, -1)]


def dated_path_from_template(template: Path, date: str) -> Path:
    text = str(template)
    if "{date}" in text:
        return Path(text.replace("{date}", date))
    stem_date = _extract_yyyymmdd(text)
    if stem_date:
        path = Path(text)
        if stem_date in path.name:
            return path.with_name(path.name.replace(stem_date, date, 1))
        return Path(text.replace(stem_date, date, 1))
    return template


def check_runner_missing_rows(
    record_date: str,
    primary_positions_template: Path,
    lookback_days: int = 2,
) -> AlertConditionResult:
    missing: list[str] = []
    row_counts: dict[str, int | None] = {}
    for date in last_n_calendar_dates(record_date, lookback_days):
        path = dated_path_from_template(primary_positions_template, date)
        if not path.exists():
            missing.append(date)
            row_counts[date] = None
            continue
        rows = _parquet_row_count(path)
        row_counts[date] = rows
        if rows == 0:
            missing.append(date)
    triggered = len(missing) >= lookback_days
    return AlertConditionResult(
        condition_id="A-1",
        condition_name="runner_missing_rows",
        triggered=triggered,
        severity="WARNING",
        detail=f"missing_or_empty_dates={missing}; row_counts={row_counts}",
        message=(
            "[FORWARD RECORD] Runner missing rows\n"
            f"Date: {record_date}\n"
            f"Missing: {missing}\n"
            "Action required: Check VPS cron and runner log"
        ),
        action_required="check_vps_cron_and_runner_log",
        data={"missing_dates": missing, "row_counts": row_counts},
    )


def check_stop_gate(stats: dict[str, Any]) -> AlertConditionResult:
    stops = list(stats.get("active_stop_gates") or [])
    return AlertConditionResult(
        condition_id="A-2",
        condition_name="stop_gate_hit",
        triggered=bool(stops),
        severity="CRITICAL",
        detail=f"active_stop_gates={stops}",
        message=(
            "[FORWARD RECORD] STOP GATE triggered\n"
            f"Date: {stats.get('date', '')}\n"
            f"Gates: {stops}\n"
            "Action required: Rick decision required. Do NOT restart automatically."
        ),
        action_required="rick_decision_required_do_not_restart",
        data={"active_stop_gates": stops},
    )


def check_warning_gate_streak(
    record_date: str,
    forward_stats_template: Path,
    streak_days: int = 3,
) -> AlertConditionResult:
    by_date: dict[str, list[str]] = {}
    for date in last_n_calendar_dates(record_date, streak_days):
        path = dated_path_from_template(forward_stats_template, date)
        stats = _read_json_if_exists(path)
        by_date[date] = list(stats.get("active_warning_gates") or []) if stats else []
    common: set[str] | None = None
    for gates in by_date.values():
        current = set(gates)
        common = current if common is None else common & current
    streak_gates = sorted(common or [])
    triggered = bool(streak_gates)
    return AlertConditionResult(
        condition_id="A-3",
        condition_name="warning_gate_streak",
        triggered=triggered,
        severity="WARNING",
        detail=f"streak_days={streak_days}; streak_gates={streak_gates}; by_date={by_date}",
        message=(
            "[FORWARD RECORD] Warning gate streak\n"
            f"Date: {record_date}\n"
            f"Gates: {streak_gates} x {streak_days} days\n"
            "Action: Monitor closely"
        ),
        action_required="monitor_warning_gate_streak",
        data={"streak_days": streak_days, "streak_gates": streak_gates, "by_date": by_date},
    )


def compute_alpha_gap(primary_positions_path: Path, shadow_positions_path: Path, threshold: float = 0.05) -> AlphaGapResult:
    if not shadow_positions_path.exists():
        return AlphaGapResult(True, None, threshold, 0, 0, 0, [])
    primary = pd.read_parquet(primary_positions_path).loc[:, ["symbol", "weight_raw"]].copy()
    shadow = pd.read_parquet(shadow_positions_path).loc[:, ["symbol", "weight_raw"]].copy()
    merged = primary.merge(shadow, on="symbol", suffixes=("_primary", "_shadow"))
    if merged.empty:
        return AlphaGapResult(False, None, threshold, 0, len(primary), len(shadow), [])
    merged["abs_diff"] = (merged["weight_raw_primary"].astype(float) - merged["weight_raw_shadow"].astype(float)).abs()
    top = merged.nlargest(3, "abs_diff").loc[:, ["symbol", "abs_diff"]].to_dict(orient="records")
    primary_symbols = set(primary["symbol"].astype(str))
    shadow_symbols = set(shadow["symbol"].astype(str))
    return AlphaGapResult(
        skipped=False,
        mean_abs_diff=float(merged["abs_diff"].mean()),
        threshold=float(threshold),
        symbol_count=int(len(merged)),
        unmatched_primary=len(primary_symbols - shadow_symbols),
        unmatched_shadow=len(shadow_symbols - primary_symbols),
        top_symbols=top,
    )


def check_alpha_gap(
    record_date: str,
    primary_positions_path: Path,
    shadow_positions_path: Path,
    threshold: float = 0.05,
) -> AlertConditionResult:
    gap = compute_alpha_gap(primary_positions_path, shadow_positions_path, threshold)
    triggered = bool(not gap.skipped and gap.mean_abs_diff is not None and gap.mean_abs_diff > threshold)
    status = "skipped_no_shadow" if gap.skipped else f"mean_abs_diff={gap.mean_abs_diff}"
    mean_abs_diff = "n/a" if gap.mean_abs_diff is None else gap.mean_abs_diff
    return AlertConditionResult(
        condition_id="A-4",
        condition_name="primary_shadow_alpha_gap",
        triggered=triggered,
        severity="WARNING",
        detail=f"{status}; threshold={threshold}; matched={gap.symbol_count}",
        message=(
            "[FORWARD RECORD] Primary/shadow alpha gap exceeded\n"
            f"Date: {record_date}\n"
            f"Mean abs diff: {mean_abs_diff} (threshold: {threshold})\n"
            f"Top divergent symbols: {gap.top_symbols}"
        ),
        action_required="review_shadow_track_output",
        data=asdict(gap),
    )


def check_data_source_failure(
    record_date: str,
    forward_stats_path: Path,
    log_path: Path,
) -> AlertConditionResult:
    errors: list[str] = []
    stats: dict[str, Any] = {}
    if not forward_stats_path.exists():
        errors.append(f"missing forward_stats: {forward_stats_path}")
    else:
        try:
            stats = json.loads(forward_stats_path.read_text(encoding="utf-8"))
            if stats.get("data_source") == "FAILED":
                errors.append("forward_stats data_source=FAILED")
        except Exception as exc:
            errors.append(f"forward_stats parse error: {exc.__class__.__name__}")
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for marker in ("data_source=FAILED", "RuntimeError"):
            if marker in text:
                errors.append(f"log marker found: {marker}")
    triggered = bool(errors)
    status_title = "Data source failure" if errors else "Data source readable"
    status_line = f"Error: {'; '.join(errors)}" if errors else "Status: data source readable"
    return AlertConditionResult(
        condition_id="A-5",
        condition_name="data_source_failure",
        triggered=triggered,
        severity="CRITICAL",
        detail="; ".join(errors) if errors else "data source readable",
        message=(
            f"[FORWARD RECORD] {status_title}\n"
            f"Date: {record_date}\n"
            f"{status_line}\n"
            "Action: Check parquet cache and upstream data pipeline"
        ),
        action_required="check_parquet_cache_and_upstream_pipeline",
        data={"errors": errors, "data_source": stats.get("data_source")},
    )


def check_review_006b_trigger(
    stats: dict[str, Any],
    previous_alert_log: Path | None = None,
) -> AlertConditionResult:
    ready = bool(stats.get("review_006b_trigger_ready"))
    duplicate = False
    if ready and previous_alert_log and previous_alert_log.exists():
        previous = json.loads(previous_alert_log.read_text(encoding="utf-8"))
        duplicate = any(item.get("condition_id") == "A-6" for item in previous.get("alerts_sent", []))
    triggered = ready and not duplicate
    return AlertConditionResult(
        condition_id="A-6",
        condition_name="review_006b_trigger_ready",
        triggered=triggered,
        severity="INFO",
        detail=f"review_006b_trigger_ready={ready}; duplicate={duplicate}",
        message=(
            "[FORWARD RECORD] REVIEW-006b trigger conditions met\n"
            f"Date: {stats.get('date', '')}\n"
            f"Days elapsed: {stats.get('days_elapsed')}\n"
            f"Sharpe (30d): {stats.get('sharpe_rolling_30d')}\n"
            f"Max DD: {stats.get('max_dd_pct')}\n"
            "Note: Informational only. Paper execution requires explicit Rick approval."
        ),
        action_required="rick_may_initiate_review_006b_process",
        data={"review_006b_trigger_ready": ready, "duplicate": duplicate},
    )


def check_forbidden_field_violation(fields: dict[str, str]) -> AlertConditionResult:
    violations = {key: value for key, value in fields.items() if value != "NOT_ATTEMPTED"}
    return AlertConditionResult(
        condition_id="A-7",
        condition_name="forbidden_field_violation",
        triggered=bool(violations),
        severity="CRITICAL",
        detail=f"violations={violations}",
        message=(
            "[FORWARD RECORD] FORBIDDEN field violation detected\n"
            f"Violations: {violations}\n"
            "Action: IMMEDIATE review required. Do NOT proceed with any execution."
        ),
        action_required="immediate_review_required_no_execution",
        data={"violations": violations},
    )


def _parquet_row_count(path: Path) -> int:
    return int(len(pd.read_parquet(path)))


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_yyyymmdd(text: str) -> str | None:
    stem = Path(text).stem
    match = re.search(r"(?<!\d)(\d{8})(?!\d)", stem)
    if match:
        return match.group(1)
    match = re.search(r"(?<!\d)(\d{8})(?!\d)", text)
    return match.group(1) if match else None
