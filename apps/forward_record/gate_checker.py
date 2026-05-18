from __future__ import annotations

from typing import Any


def evaluate_gates(
    *,
    stats: dict[str, Any],
    overlay_false_streak: int = 0,
    safety_pass: bool = True,
    data_gap_days: int = 0,
    universe_count: int = 0,
    missing_ratio: float = 0.0,
    monitor_heartbeat_missing_hours: float = 0.0,
) -> dict[str, Any]:
    warnings: list[str] = []
    stops: list[str] = []
    days = int(stats.get("days_elapsed") or 0)
    sharpe = stats.get("sharpe_rolling_30d")
    max_dd = float(stats.get("max_dd_pct") or 0.0)
    tracking = stats.get("tracking_error_vs_baseline_30d")

    if days >= 30 and sharpe is not None and float(sharpe) < 0.5:
        warnings.append("W-1")
    if max_dd <= -0.25:
        warnings.append("W-2")
    if tracking is not None and float(tracking) >= 0.30:
        warnings.append("W-3")
    if overlay_false_streak >= 5:
        warnings.append("W-4")
    if monitor_heartbeat_missing_hours > 2.0:
        warnings.append("W-5")
    if data_gap_days > 1:
        warnings.append("W-6")

    if days >= 10 and sharpe is not None and float(sharpe) < -0.5:
        stops.append("S-1")
    if max_dd <= -0.40:
        stops.append("S-2")
    if tracking is not None and float(tracking) > 0.50 and days >= 5:
        stops.append("S-3")
    if overlay_false_streak >= 10:
        stops.append("S-4")
    if not safety_pass:
        stops.append("S-5")
    if universe_count < 10 or missing_ratio > 0.20:
        stops.append("S-6")

    return {
        "active_warning_gates": warnings,
        "active_stop_gates": stops,
        "clock_paused": bool(stops or "W-6" in warnings),
    }


def review_006b_trigger_ready(stats: dict[str, Any], overlay_always_pass: bool, exception_recorded: bool) -> bool:
    return bool(
        int(stats.get("days_elapsed") or 0) >= 30
        and stats.get("sharpe_rolling_30d") is not None
        and float(stats["sharpe_rolling_30d"]) >= 0.5
        and float(stats.get("max_dd_pct") or 0.0) > -0.30
        and not stats.get("active_stop_gates")
        and (overlay_always_pass or exception_recorded)
    )

