from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class KillSwitchConfig:
    max_drawdown_stop: float = -0.30
    consecutive_losing_cycles_stop: int = 5
    min_nav_usd: float = 7_000.0
    warning_drawdown: float = -0.25
    warning_sharpe: float = 0.5
    stop_sharpe: float = 0.2
    warning_tracking_error: float = 0.05
    stop_tracking_error: float = 0.10
    action: str = "close_all_positions_and_halt"


def evaluate_kill_switches(daily_pnl: pd.DataFrame, config: KillSwitchConfig | None = None) -> list[dict[str, Any]]:
    cfg = config or KillSwitchConfig()
    if daily_pnl.empty:
        return [{
            "event_type": "NO_DAILY_PNL",
            "severity": "CRITICAL",
            "action": cfg.action,
            "details": "daily_pnl input is empty",
        }]
    frame = daily_pnl.copy()
    frame["nav_usd"] = pd.to_numeric(frame["nav_usd"], errors="coerce")
    frame["paper_return"] = pd.to_numeric(frame["paper_return"], errors="coerce").fillna(0.0)
    peak = frame["nav_usd"].cummax()
    drawdown = frame["nav_usd"] / peak - 1.0
    max_dd = float(drawdown.min())
    losses = frame["paper_return"].lt(0)
    max_losing_streak = _max_true_streak(losses)
    min_nav = float(frame["nav_usd"].min())
    events: list[dict[str, Any]] = []
    if max_dd <= cfg.max_drawdown_stop:
        events.append(_event("MAX_DRAWDOWN_STOP", "KILL_SWITCH", cfg.action, {"max_drawdown": max_dd}))
    elif max_dd <= cfg.warning_drawdown:
        events.append(_event("MAX_DRAWDOWN_WARNING", "WARNING", "review_required", {"max_drawdown": max_dd}))
    if max_losing_streak >= cfg.consecutive_losing_cycles_stop:
        events.append(_event("CONSECUTIVE_LOSING_CYCLES_STOP", "KILL_SWITCH", cfg.action, {"losing_cycles": max_losing_streak}))
    if min_nav < cfg.min_nav_usd:
        events.append(_event("MIN_NAV_STOP", "KILL_SWITCH", cfg.action, {"min_nav_usd": min_nav}))
    return events


def evaluate_monthly_review_gates(metrics: dict[str, float], config: KillSwitchConfig | None = None) -> list[dict[str, Any]]:
    cfg = config or KillSwitchConfig()
    events: list[dict[str, Any]] = []
    sharpe = float(metrics.get("paper_sharpe", 0.0))
    max_dd = float(metrics.get("max_drawdown", 0.0))
    tracking_error = float(metrics.get("tracking_error_monthly", 0.0))
    if sharpe < cfg.stop_sharpe:
        events.append(_event("PAPER_SHARPE_STOP", "STOP_PAPER_PENDING_REVIEW", "review_required", {"paper_sharpe": sharpe}))
    elif sharpe < cfg.warning_sharpe:
        events.append(_event("PAPER_SHARPE_WARNING", "WARNING", "review_required", {"paper_sharpe": sharpe}))
    if max_dd <= cfg.max_drawdown_stop:
        events.append(_event("MONTHLY_DRAWDOWN_STOP", "STOP_PAPER_PENDING_REVIEW", "review_required", {"max_drawdown": max_dd}))
    elif max_dd <= cfg.warning_drawdown:
        events.append(_event("MONTHLY_DRAWDOWN_WARNING", "WARNING", "review_required", {"max_drawdown": max_dd}))
    if tracking_error > cfg.stop_tracking_error:
        events.append(_event("TRACKING_ERROR_STOP", "STOP_PAPER_PENDING_REVIEW", "review_required", {"tracking_error": tracking_error}))
    elif tracking_error > cfg.warning_tracking_error:
        events.append(_event("TRACKING_ERROR_WARNING", "WARNING", "review_required", {"tracking_error": tracking_error}))
    return events


def _event(event_type: str, severity: str, action: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "severity": severity,
        "action": action,
        "details": details,
    }


def _max_true_streak(series: pd.Series) -> int:
    best = 0
    current = 0
    for value in series.astype(bool):
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)
