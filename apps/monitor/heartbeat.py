from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from apps.monitor.config import MonitorConfig


def sample_heartbeat(
    config: MonitorConfig,
    timestamp: str | None = None,
    warning_count: int = 0,
    critical_count: int = 0,
) -> dict[str, Any]:
    ts = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": ts,
        "bot_name": config.bot_name,
        "environment": config.environment,
        "status": "OK" if critical_count == 0 and warning_count == 0 else "WARNING",
        "equity": 10_000.0,
        "nav": 10_000.0,
        "active_positions": 0,
        "last_order_timestamp": ts,
        "api_latency_ms": 0.0,
        "process_alive": True,
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
        "warning_count": int(warning_count),
        "critical_count": int(critical_count),
    }


def hook_event_from_heartbeat(row: dict[str, Any]) -> dict[str, Any]:
    from apps.paper_trading.monitor_hook import PaperTradingMonitorHook

    hook = PaperTradingMonitorHook(source="task005_monitor_sample")
    return hook.push_heartbeat(
        timestamp=str(row["timestamp"]),
        nav_usd=float(row["nav"]),
        status=str(row["status"]),
    )


def write_heartbeat_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
