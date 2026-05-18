from __future__ import annotations

from typing import Any

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.gate_checker import evaluate_gates, review_006b_trigger_ready


def build_forward_stats(
    config: ForwardRecordConfig,
    pnl: dict[str, Any],
    source_position_count: int,
    overlay_pass: bool = True,
    safety_pass: bool = True,
) -> dict[str, Any]:
    days_elapsed = 0 if config.dry_run or not config.clock_started else int(pnl["day_number"])
    stats: dict[str, Any] = {
        "date": config.output_date,
        "variant": pnl["variant"],
        "day_number": int(pnl["day_number"]),
        "days_elapsed": days_elapsed,
        "clock_started": bool(config.clock_started),
        "dry_run": bool(config.dry_run),
        "sharpe_rolling_30d": None,
        "sharpe_cumulative": None,
        "max_dd_pct": 0.0,
        "current_dd_pct": 0.0,
        "tracking_error_vs_baseline_30d": None,
        "calmar_ratio": None,
        "hit_rate": None,
        "annualization": float(config.paper_config.annualization_factor),
        "ddof": 1,
        "status": "DRY_RUN" if config.dry_run else "RECORDING",
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
    }
    gate_result = evaluate_gates(
        stats=stats,
        overlay_false_streak=0 if overlay_pass else 1,
        safety_pass=safety_pass,
        data_gap_days=0,
        universe_count=source_position_count,
        missing_ratio=0.0,
    )
    stats.update(gate_result)
    stats["review_006b_trigger_ready"] = review_006b_trigger_ready(
        stats,
        overlay_always_pass=overlay_pass,
        exception_recorded=False,
    )
    return stats


def build_forward_summary(config: ForwardRecordConfig, stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy": f"prev3y_crypto_{stats['variant']}",
        "runner_version": "task009_v1.0",
        "start_date": None,
        "latest_date": config.output_date,
        "days_elapsed": int(stats["days_elapsed"]),
        "days_required": int(config.paper_config.forward_validation_days),
        "clock_paused": bool(stats["clock_paused"]),
        "pause_reason": _pause_reason(stats),
        "sharpe_rolling_30d": stats["sharpe_rolling_30d"],
        "sharpe_cumulative": stats["sharpe_cumulative"],
        "max_dd_pct": stats["max_dd_pct"],
        "tracking_error_vs_baseline_30d": stats["tracking_error_vs_baseline_30d"],
        "gate_status": {
            "sharpe_pass": None,
            "max_dd_pass": stats["max_dd_pct"] > -0.30,
            "overlay_always_pass": True,
            "no_stop_gate_triggered": not stats["active_stop_gates"],
        },
        "active_warning_gates": stats["active_warning_gates"],
        "active_stop_gates": stats["active_stop_gates"],
        "review_006b_trigger_ready": bool(stats["review_006b_trigger_ready"]),
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
    }


def _pause_reason(stats: dict[str, Any]) -> str | None:
    stops = stats.get("active_stop_gates") or []
    warnings = stats.get("active_warning_gates") or []
    if stops:
        return ",".join(stops)
    if "W-6" in warnings:
        return "W-6_data_gap"
    return None


def baseline_returns(path: str) -> pd.Series:
    frame = pd.read_csv(path)
    if "portfolio_return" not in frame:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame["portfolio_return"], errors="coerce").fillna(0.0)

